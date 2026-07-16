"""Обработка событий MAX и цикл Long Polling.

`UpdateRouter` — переиспользуемая обработка одного события (Update). Используется
ОБОИМИ режимами приёма:
- `Stage1Poller` — Long Polling (GET /updates с marker);
- webhook-сервер (см. webhook.py).

В MAX нет copyMessage, поэтому репост в личку владельца идёт НАТИВНОЙ ПЕРЕСЫЛКОЙ:
POST /messages с телом `link: {"type": "forward", "mid": <mid>}` (сверено с
docs/max/markdown/docs/chatbots/bots-coding/js.md — link type reply/forward).
Одно событие message_created самодостаточно (вложения уже внутри), сборка
альбомов из отдельных сообщений, как в Telegram, не нужна.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from . import content
from .client import MaxClient, MaxError
from .storage import Storage

log = logging.getLogger(__name__)

# Расширения для скачиваемых медиа (если в url нет суффикса).
_EXT_BY_TYPE = {"image": ".jpg", "video": ".mp4", "audio": ".mp3", "file": ".bin"}
FORWARDED_BUTTON_PAYLOAD = "mesync:button_unavailable"
FORWARDED_BUTTON_NOTICE = "Действие кнопки доступно только в исходном сообщении."


def _copy_payload(m: dict[str, Any]) -> dict[str, Any] | None:
    """Payload вложения для ЧИСТОЙ КОПИИ — переиспользуем token/координаты входящего
    сообщения, чтобы переслать контент как собственное сообщение бота (без пометки
    «переслано»). Проверено вживую: image/video принимают token при отправке.
    None -> это вложение восстановить нельзя (нужен forward всего сообщения)."""
    t = m.get("type")
    if t in ("video", "audio", "file"):
        return {"token": m["token"]} if m.get("token") else None
    if t == "image":
        if m.get("token"):
            return {"token": m["token"]}
        if m.get("url"):
            return {"url": m["url"]}
        return None
    if t == "sticker":
        return {"code": m["code"]} if m.get("code") else None
    if t == "location":
        if m.get("lat") is not None and m.get("lon") is not None:
            return {"lat": m["lat"], "lon": m["lon"]}
        return None
    if t == "share":
        p: dict[str, Any] = {}
        if m.get("url"):
            p["url"] = m["url"]
        if m.get("token"):
            p["token"] = m["token"]
        return p or None
    return None        # contact и прочие типы -> форвардим всё сообщение целиком


def _rebuild_attachments(media_list: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Пересобрать вложения для чистой копии. None, если ХОТЯ БЫ ОДНО вложение нельзя
    восстановить (тогда лучше переслать всё сообщение целиком — ничего не теряем)."""
    out: list[dict[str, Any]] = []
    for m in media_list:
        payload = _copy_payload(m)
        if payload is None:
            return None
        out.append({"type": m.get("type"), "payload": payload})
    return out


# --- сохранение форматирования: markup MAX -> HTML (для format=html) ---
# Соответствие типов сверено вживую round-trip'ом (POST html -> GET markup):
# strong=b, emphasized=i, underline=u, strikethrough=s, monospaced=code,
# preformatted=pre (внутренний тип для TG pre), highlighted=mark, heading=h1, link=a.
# Офсеты markup — в UTF-16 code units.
_MARKUP_TAGS = {
    "strong": ("<b>", "</b>"),
    "emphasized": ("<i>", "</i>"),
    "underline": ("<u>", "</u>"),
    "strikethrough": ("<s>", "</s>"),
    "monospaced": ("<code>", "</code>"),
    "preformatted": ("<pre>", "</pre>"),
    "highlighted": ("<mark>", "</mark>"),
    "heading": ("<h1>", "</h1>"),
    "quote": ("<blockquote>", "</blockquote>"),
}


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(s: str) -> str:
    return _esc(s).replace('"', "&quot;")


def _open_tag(e: dict[str, Any]) -> str:
    t = e.get("type")
    if t == "link":
        return f'<a href="{_esc_attr(str(e.get("url", "")))}">'
    if t in ("user_mention", "mention"):
        uid = e.get("user_id") or e.get("user_link_id") or ""
        return f'<a href="max://user/{_esc_attr(str(uid))}">'
    pair = _MARKUP_TAGS.get(t)
    return pair[0] if pair else ""


def _close_tag(e: dict[str, Any]) -> str:
    t = e.get("type")
    if t in ("link", "user_mention", "mention"):
        return "</a>"
    pair = _MARKUP_TAGS.get(t)
    return pair[1] if pair else ""


def _to_units(text: str) -> list[bytes]:
    b = text.encode("utf-16-le")
    return [b[i:i + 2] for i in range(0, len(b), 2)]


def _units_to_str(units: list[bytes]) -> str:
    return b"".join(units).decode("utf-16-le", errors="replace")


def markup_to_html(text: str, markup: list[dict[str, Any]] | None) -> tuple[str, bool]:
    """Преобразовать (text, markup) в HTML для отправки с format=html.

    Офсеты markup трактуются как UTF-16 code units (как отдаёт MAX). Возвращает
    (html, has_formatting). Алгоритм по границам с диффом стека открытых тегов —
    корректен для вложенных и пересекающихся диапазонов, неизвестные типы entity
    просто не оборачиваются (текст сохраняется как есть). Весь текст экранируется.
    """
    ents = [e for e in (markup or [])
            if isinstance(e, dict) and isinstance(e.get("from"), int)
            and isinstance(e.get("length"), int) and e["length"] > 0]
    if not ents:
        return _esc(text), False
    units = _to_units(text)
    n = len(units)
    points = {0, n}
    for e in ents:
        points.add(max(0, min(n, e["from"])))
        points.add(max(0, min(n, e["from"] + e["length"])))
    points = sorted(points)

    def active_at(i: int) -> list[dict[str, Any]]:
        act = [(e["from"], -(e["from"] + e["length"]), idx, e)
               for idx, e in enumerate(ents) if e["from"] <= i < e["from"] + e["length"]]
        act.sort(key=lambda x: (x[0], x[1], x[2]))
        return [a[3] for a in act]

    out: list[str] = []
    stack: list[dict[str, Any]] = []
    for k in range(len(points) - 1):
        i, j = points[k], points[k + 1]
        cur = active_at(i)
        common = 0
        while common < len(stack) and common < len(cur) and stack[common] is cur[common]:
            common += 1
        for e in reversed(stack[common:]):
            out.append(_close_tag(e))
        for e in cur[common:]:
            out.append(_open_tag(e))
        stack = cur
        out.append(_esc(_units_to_str(units[i:j])))
    for e in reversed(stack):
        out.append(_close_tag(e))
    return "".join(out), True


class UpdateRouter:
    """Обработка одного события MAX. Общая для polling и webhook."""

    def __init__(self, client: MaxClient, storage: Storage, *,
                 download_media: bool, max_download_bytes: int,
                 chat_registry=None, ownership=None, mirror: bool = True,
                 bot_id: int | None = None, rule_router=None, rule_edit_router=None,
                 warn_hide_cb=None, dm_welcome=None) -> None:
        self.client = client
        self.storage = storage
        self.chat_registry = chat_registry
        self.ownership = ownership
        self.mirror = mirror
        self.bot_id = bot_id
        # rule_router(norm): синхронизация по правилам mini-app (control-API).
        # Если задан — заменяет репост-в-личку-владельцу. По умолчанию None.
        self.rule_router = rule_router
        self.rule_edit_router = rule_edit_router
        # dm_welcome(norm) — приветствие с кнопками на ЛЮБОЕ сообщение в диалоге с ботом
        # (кроме /claim — у него собственный ответ с кодом привязки), а также на событие
        # bot_started из документированного диплинка ?start=<payload>. Ставится в run_app.
        self.dm_welcome = dm_welcome
        # warn_hide_cb(messenger, chat_id): «Скрыть» нажато на уведомлении о сбое доставки в
        # чате → ре-армить чат-канал по этой цели (следующий сбой пришлёт заново). None → нет.
        self.warn_hide_cb = warn_hide_cb
        self.download_media = download_media
        self.max_download_bytes = max_download_bytes
        self._mirror_lock = asyncio.Lock()          # репосты строго по одному, в порядке
        self._dl_sem = asyncio.Semaphore(3)         # ограничение фоновых скачиваний
        self._dl_tasks: set[asyncio.Task] = set()

    async def __aenter__(self) -> "UpdateRouter":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        for task in list(self._dl_tasks):
            task.cancel()

    async def process(self, update: dict[str, Any]) -> None:
        """Полная обработка одного события (сырьё сохраняется здесь же)."""
        await self.storage.append_raw(update)
        self._register_dialogs(update)
        if self.ownership is not None:
            try:
                await self.ownership.observe(update)
            except Exception:  # noqa: BLE001
                log.exception("ownership.observe сбой для update_type=%s", update.get("update_type"))
        try:
            await self._dispatch(update)
        except Exception:  # noqa: BLE001 — один сбойный апдейт не должен ронять приём
            log.exception("Ошибка обработки события %s", update.get("update_type"))

    async def _dispatch(self, update: dict[str, Any]) -> None:
        ut = update.get("update_type")
        if ut in ("message_created", "message_edited") and isinstance(update.get("message"), dict):
            norm = content.normalize_message(update["message"], ut)
            if ut == "message_created":
                await self._handle_message(norm)
            else:
                log.info("EDIT  %s", content.message_summary(norm))
                await self.storage.append_content(norm)
                if self.rule_edit_router is not None:
                    try:
                        await self.rule_edit_router(norm)
                    except Exception:  # noqa: BLE001
                        log.warning("on_max_edit сбой", exc_info=True)
            return
        if ut == "message_callback":
            await self._handle_callback(update)
            return
        await self._handle_event(update)

    async def _handle_callback(self, update: dict[str, Any]) -> None:
        """Нажатие inline-кнопки. «Скрыть» (payload=hide_msg или hide_warn:<m>:<chat>) удаляет
        сообщение бота; для hide_warn дополнительно ре-армит уведомление о сбое доставки по цели."""
        cb = update.get("callback") or {}
        payload, callback_id = cb.get("payload") or "", cb.get("callback_id")
        notification = FORWARDED_BUTTON_NOTICE if payload == FORWARDED_BUTTON_PAYLOAD else None
        if payload == "hide_msg" or payload.startswith("hide_warn:"):
            msg = update.get("message") or cb.get("message") or {}
            mid = (msg.get("body") or {}).get("mid")
            if mid is not None:
                try:
                    await self.client.delete_message(mid)
                except MaxError as exc:
                    log.warning("hide: delete mid=%s не удался: %s", mid, exc.description)
            if payload.startswith("hide_warn:") and self.warn_hide_cb is not None:
                parts = payload.split(":", 2)
                if len(parts) == 3:
                    try:
                        self.warn_hide_cb(parts[1], parts[2])
                    except Exception:  # noqa: BLE001
                        log.warning("warn_hide_cb сбой", exc_info=True)
        if callback_id:
            try:
                await self.client.answer_callback(callback_id, notification)
            except MaxError:
                pass

    def _register_dialogs(self, update: dict[str, Any]) -> None:
        """Запомнить диалоги (для отправки логов в личку)."""
        if self.chat_registry is None:
            return
        for user_id, user in content.dialogs_in_update(update):
            if user_id is None:
                continue
            user = user or {}
            uname = user.get("username")
            name = " ".join(p for p in (user.get("first_name"), user.get("last_name")) if p) or None
            if self.chat_registry.add(user_id, username=uname, name=name):
                log.info("Зарегистрирован диалог user_id=%s%s",
                         user_id, f" (@{uname})" if uname else "")

    async def _handle_message(self, norm: dict[str, Any]) -> None:
        log.info("MSG   %s", content.message_summary(norm))
        # команды/привязка через ownership; приветствие — на любое сообщение в диалоге
        if norm.get("sender_id") != self.bot_id:
            ctype = norm.get("chat_type")
            text = (norm.get("text") or "").strip()
            cmd = text.split()[0].lower() if text.startswith("/") else ""
            if ctype == content.DIALOG_TYPE:
                contact = next((a for a in (norm.get("attachments") or [])
                                if (a or {}).get("type") == "contact"), None)
                if contact:
                    # Контакт (шеринг номера): сразу удаляем из диалога — номер телефона
                    # не должен оставаться в переписке. Вход по номеру выполняется только
                    # через mini-app bridge, не через чат-бота. Приветствие не шлём.
                    try:
                        await self.client.delete_message(norm.get("mid"))
                    except Exception:  # noqa: BLE001
                        log.warning("удаление сообщения с контактом не удалось", exc_info=True)
                    return
                elif cmd == "/claim" and self.ownership is not None:
                    await self.ownership.handle_command(norm)   # код привязки — свой ответ
                elif self.dm_welcome is not None:
                    # Любое другое сообщение в личке (включая /start) → приветствие с кнопками.
                    try:
                        await self.dm_welcome(norm)
                    except Exception:  # noqa: BLE001 — приветствие не должно ломать приём
                        log.warning("dm_welcome сбой", exc_info=True)
                elif cmd and self.ownership is not None:
                    await self.ownership.handle_command(norm)   # standalone: старое поведение
            elif content.is_group_like(ctype) and self.ownership is not None:
                await self.ownership.on_chat_message(norm)
        await self.storage.append_content(norm)
        if self.rule_router is not None:
            if norm.get("sender_id") != self.bot_id:   # не синхронизируем свои сообщения
                await self.rule_router(norm)            # маршрутизация по правилам mini-app
        else:
            await self._mirror_message(norm)            # репост СРАЗУ, в порядке прихода
        if self.download_media and norm.get("media"):
            self._spawn_download(norm.get("chat_id"), norm["media"], f"mid{norm.get('mid')}")

    async def _handle_event(self, update: dict[str, Any]) -> None:
        log.info("UPD   %s", content.update_summary(update))
        # В отличие от Telegram, MAX не создаёт видимое сообщение `/start <payload>`:
        # переход по ?start=... приходит отдельным событием bot_started. Приводим его
        # к минимальному norm-контракту dm_welcome, чтобы обе кнопки веб-переходника
        # открывали чат и гарантированно выдавали приветствие с кнопкой mini-app.
        if update.get("update_type") == "bot_started" and self.dm_welcome is not None:
            user = update.get("user") or {}
            user_id = user.get("user_id") or update.get("chat_id")
            if user_id is not None:
                try:
                    await self.dm_welcome({
                        "sender_id": user_id,
                        "chat_id": update.get("chat_id"),
                        "chat_type": content.DIALOG_TYPE,
                        "text": "/start",
                        "start_payload": update.get("payload"),
                        "sender": user,
                    })
                except Exception:  # noqa: BLE001 — приветствие не должно ломать приём
                    log.warning("dm_welcome сбой на bot_started", exc_info=True)
        await self.storage.append_content({
            "kind": "event", "update_type": update.get("update_type"),
            "timestamp": update.get("timestamp"), "raw": update,
        })

    # --- синхронизация в личку владельца чата ---
    async def _mirror_message(self, norm: dict[str, Any]) -> None:
        if not (self.mirror and self.ownership is not None):
            return
        if norm.get("sender_id") == self.bot_id:        # не синхронизируем свои сообщения
            return
        chat_id = norm.get("chat_id")
        owner = self.ownership.owner_of(chat_id)
        if owner is None:
            return
        mid = norm.get("mid")
        if mid is not None:
            await self._repost(owner, mid, original=norm)

    async def _repost(self, owner_user_id: Any, mid: str, *,
                      original: dict[str, Any] | None = None) -> None:
        """Репост владельцу ЧИСТОЙ КОПИЕЙ — как сообщение бота, без пометки «переслано».

        В MAX нет copyMessage, поэтому копию собираем сами: текст + медиа,
        переиспользуя token/координаты входящих вложений (проверено: image/video
        принимают token). Если копию собрать или отправить не удалось — фоллбэк на
        нативную пересылку (link type=forward), чтобы ничего не потерять; если и она
        не прошла — короткая пометка владельцу.
        """
        o = original or {}
        text = o.get("text") or None
        rebuilt = _rebuild_attachments(o.get("media") or [])   # None -> есть невосстановимое медиа
        # Сохраняем форматирование: markup -> HTML, отправляем с format=html.
        send_text, fmt = text, None
        if text and o.get("markup"):
            send_text, has_fmt = markup_to_html(text, o.get("markup"))
            fmt = "html" if has_fmt else None
        async with self._mirror_lock:                          # строго по одному репосту за раз
            if rebuilt is not None and (text or rebuilt):
                try:
                    await self.client.send_message(
                        user_id=owner_user_id, text=send_text, attachments=rebuilt or None, fmt=fmt)
                    return
                except MaxError as exc:
                    log.warning("mirror: чистая копия mid=%s -> %s не удалась (%s); пробую forward",
                                mid, owner_user_id, exc.description)
            try:
                await self.client.send_message(
                    user_id=owner_user_id, link={"type": "forward", "mid": mid})
                return
            except MaxError as exc:
                log.warning("mirror: forward mid=%s -> %s не удался: %s",
                            mid, owner_user_id, exc.description)
            await self._forward_fallback(owner_user_id, original)

    async def _forward_fallback(self, owner_user_id: Any,
                                original: dict[str, Any] | None) -> None:
        o = original or {}
        text = o.get("text")
        media = o.get("media") or []
        note_bits = []
        if media:
            note_bits.append("вложения: " + ", ".join(str(m.get("type")) for m in media))
        note = ("⚠️ Не удалось переслать сообщение из привязанного чата."
                + (f" Текст ниже. ({'; '.join(note_bits)})" if note_bits else ""))
        hide_kb = [{"type": "inline_keyboard", "payload": {
            "buttons": [[{"type": "callback", "text": "Скрыть", "payload": "hide_msg"}]]}}]
        try:
            await self.client.send_message(user_id=owner_user_id,
                                           text=f"{note}\n\n{text}" if text else note,
                                           attachments=hide_kb)
        except MaxError:
            pass

    # --- скачивание медиа (best-effort, в фоне; у вложения должен быть url) ---
    def _spawn_download(self, chat_id: Any, media_list: list[dict[str, Any]], label: str) -> None:
        task = asyncio.create_task(self._download_guarded(chat_id, media_list, label))
        self._dl_tasks.add(task)
        task.add_done_callback(self._dl_tasks.discard)

    async def _download_guarded(self, chat_id: Any, media_list: list[dict[str, Any]],
                                label: str) -> None:
        async with self._dl_sem:
            try:
                await self._download_media(chat_id, media_list, label=label)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("Фоновое скачивание не удалось (%s)", label)

    async def _download_media(self, chat_id: Any, media_list: list[dict[str, Any]],
                              *, label: str) -> None:
        for media in media_list:
            url = media.get("url")
            if not url:
                continue                                # без прямого url скачать нельзя
            order = int(media.get("order_index", 0))
            mtype = str(media.get("type"))
            ext = Path(str(url).split("?")[0]).suffix or _EXT_BY_TYPE.get(mtype, ".bin")
            name = f"{label}__{order:02d}__{mtype}{ext}"
            dest = self.storage.media_path(chat_id, name)
            try:
                written = await self.client.download_file(url, dest)
                log.info("  ↳ %s: %d Б -> %s", mtype, written, dest.name)
            except Exception as exc:  # noqa: BLE001
                log.warning("  ↳ скачивание не удалось (%s): %s", mtype, exc)


class Stage1Poller:
    """Long Polling (GET /updates с marker) поверх общего UpdateRouter."""

    def __init__(self, client: MaxClient, storage: Storage, *,
                 update_types: list[str], timeout: int, limit: int,
                 download_media: bool, max_download_bytes: int,
                 chat_registry=None, ownership=None, mirror: bool = True,
                 bot_id: int | None = None, rule_router=None, rule_edit_router=None,
                 warn_hide_cb=None, dm_welcome=None, health=None) -> None:
        self.client = client
        self.storage = storage
        self.update_types = update_types
        self.timeout = timeout
        self.limit = limit
        self._hb = health   # ops-живость (этап 4.5): лёгкий прокси или None
        self.router = UpdateRouter(
            client, storage, download_media=download_media,
            max_download_bytes=max_download_bytes, chat_registry=chat_registry,
            ownership=ownership, mirror=mirror, bot_id=bot_id, rule_router=rule_router,
            rule_edit_router=rule_edit_router, warn_hide_cb=warn_hide_cb,
            dm_welcome=dm_welcome)

    async def run(self) -> None:
        marker = await self.storage.load_marker()
        log.info("Long Polling: marker=%s, типов событий=%d, скачивание медиа=%s",
                 marker, len(self.update_types), self.router.download_media)
        async with self.router:
            while True:
                try:
                    resp = await self.client.get_updates(
                        marker, timeout=self.timeout, limit=self.limit,
                        types=self.update_types)
                except MaxError as exc:
                    # Активна подписка Webhook → Long Polling недоступен.
                    if self._hb:
                        self._hb.error(exc)
                    log.error("GET /updates ошибка: %s. Пауза 5с.", exc.description)
                    await asyncio.sleep(5)
                    continue
                if self._hb:
                    self._hb.poll()
                updates = resp.get("updates") or []
                if updates and self._hb:
                    self._hb.update()
                for upd in updates:
                    await self.router.process(upd)
                new_marker = resp.get("marker")
                if new_marker is not None:
                    marker = int(new_marker)
                    await self.storage.save_marker(marker)

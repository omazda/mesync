"""Обработка апдейтов Telegram и цикл long polling (Этап 1).

`UpdateRouter` — переиспользуемая обработка одного апдейта (сохранение сырья,
регистрация приватных чатов, разбор контента, сборка альбомов в правильном
порядке, скачивание медиа). Его используют ОБА режима приёма:
- `Stage1Poller` — long polling (getUpdates);
- webhook-сервер (см. webhook.py).

getUpdates/offset сверены с docs/telegram/markdown/04-api-reference.md.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from . import content
from .client import TelegramClient, TelegramError
from .media_group import MediaGroupAggregator
from .storage import Storage

log = logging.getLogger(__name__)

# Какие апдейты считаются НОВЫМ сообщением (их части можно собирать в альбом).
# Для edited_* агрегацию не делаем — это правки отдельных сообщений.
_NEW_MESSAGE_KINDS = {"message", "channel_post", "business_message", "guest_message"}
_EDIT_KINDS = {"edited_message", "edited_channel_post", "edited_business_message"}
FORWARDED_BUTTON_PAYLOAD = "mesync:button_unavailable"
FORWARDED_BUTTON_NOTICE = "Действие кнопки доступно только в исходном сообщении."

# Расширения, если file_path вдруг без суффикса.
_EXT_BY_TYPE = {
    "photo": ".jpg", "video": ".mp4", "animation": ".mp4", "video_note": ".mp4",
    "audio": ".mp3", "voice": ".ogg", "sticker": ".webp",
}


def _chat_label(chat: dict[str, Any] | None) -> str:
    chat = chat or {}
    who = chat.get("title") or chat.get("username") or chat.get("id")
    return f"{chat.get('type')}:{who}"


def _ext_for(mime_type: str | None, media_type: str) -> str:
    if mime_type and "/" in mime_type:
        sub = mime_type.split("/", 1)[1].split(";")[0]
        if sub:
            return "." + {"jpeg": "jpg", "quicktime": "mov", "x-matroska": "mkv"}.get(sub, sub)
    return _EXT_BY_TYPE.get(media_type, ".bin")


def _is_service_message(norm: dict[str, Any]) -> bool:
    """Telegram service Message: join/leave/pin/topic/migration/etc.

    Такие сообщения сохраняем в журнале и используем для служебной логики (например,
    миграция group->supergroup), но не пересылаем пользователям по правилам.
    """
    return bool(norm.get("service"))


class UpdateRouter:
    """Обработка одного апдейта. Общая для polling и webhook.

    Управляет агрегатором медиагрупп — использовать как `async with`.
    """

    def __init__(self, client: TelegramClient, storage: Storage, *,
                 download_media: bool, max_download_bytes: int,
                 media_debounce: float, chat_registry=None, ownership=None,
                 mirror: bool = True, rule_router=None, rule_album=None,
                 rule_edit_router=None, warn_hide_cb=None, dm_welcome=None,
                 contact_cb=None) -> None:
        self.client = client
        self.storage = storage
        self.chat_registry = chat_registry
        self.ownership = ownership
        self.mirror = mirror
        # Синхронизация по правилам mini-app (control-API). Если заданы —
        # заменяют репост-в-личку-владельцу. По умолчанию None (поведение прежнее).
        self.rule_router = rule_router
        self.rule_album = rule_album
        self.rule_edit_router = rule_edit_router
        # dm_welcome(norm) — приветствие с кнопками на ЛЮБОЕ сообщение в личке с ботом
        # (кроме /claim — у него собственный ответ с кодом привязки). Ставится в run_app.
        self.dm_welcome = dm_welcome
        # contact_cb(user_id, phone) — подтверждение номера для auth-flow. Вызывается только
        # для Telegram self-contact: contact.user_id обязан совпасть с Message.from.id.
        self.contact_cb = contact_cb
        # warn_hide_cb(messenger, chat_id): «Скрыть» нажато на уведомлении о сбое доставки в
        # чате → ре-армить чат-канал по этой цели (следующий сбой пришлёт заново). None → нет.
        self.warn_hide_cb = warn_hide_cb
        self.download_media = download_media
        self.max_download_bytes = max_download_bytes
        self.media_debounce = media_debounce
        self._agg: MediaGroupAggregator | None = None
        self._mirror_lock = asyncio.Lock()              # репосты строго по одному, в порядке
        self._dl_sem = asyncio.Semaphore(3)             # ограничение фоновых скачиваний
        self._dl_tasks: set[asyncio.Task] = set()

    async def __aenter__(self) -> "UpdateRouter":
        self._agg = MediaGroupAggregator(self._on_album, debounce=self.media_debounce)
        await self._agg.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        for task in list(self._dl_tasks):
            task.cancel()
        if self._agg is not None:
            await self._agg.__aexit__(*exc)
            self._agg = None

    async def process(self, update: dict[str, Any]) -> None:
        """Полная обработка одного апдейта (сырьё уже сохраняется здесь)."""
        await self.storage.append_raw(update)        # сырой апдейт — ничего не теряем
        self._register_private_chats(update)
        if self.ownership is not None:
            try:
                await self.ownership.observe(update)
            except Exception:  # noqa: BLE001
                log.exception("ownership.observe сбой для update_id=%s", update.get("update_id"))
        try:
            await self._dispatch(update)
        except Exception:  # noqa: BLE001 — один сбойный апдейт не должен ронять приём
            log.exception("Ошибка обработки update_id=%s", update.get("update_id"))

    async def _dispatch(self, update: dict[str, Any]) -> None:
        cq = update.get("callback_query")
        if cq is not None:
            await self._handle_callback(cq)
            return
        for field in content.MESSAGE_UPDATE_FIELDS:
            msg = update.get(field)
            if msg is not None:
                norm = content.normalize_message(msg, field)
                if field in _EDIT_KINDS:
                    await self._handle_edit(norm)
                elif norm.get("media_group_id") and field in _NEW_MESSAGE_KINDS:
                    await self._agg.add(norm)            # часть альбома -> агрегатор
                else:
                    await self._handle_message(norm)
                return
        await self._handle_other(update)

    async def _handle_callback(self, cq: dict[str, Any]) -> None:
        """Нажатие inline-кнопки. «Скрыть» (data=hide_msg или hide_warn:<m>:<chat>) удаляет
        сообщение бота; для hide_warn дополнительно ре-армит уведомление о сбое доставки по цели."""
        data = cq.get("data") or ""
        answer_text = FORWARDED_BUTTON_NOTICE if data == FORWARDED_BUTTON_PAYLOAD else None
        if data == "hide_msg" or data.startswith("hide_warn:"):
            msg = cq.get("message") or {}
            chat_id = (msg.get("chat") or {}).get("id")
            mid = msg.get("message_id")
            if chat_id is not None and mid is not None:
                try:
                    await self.client.delete_message(chat_id, mid)
                except TelegramError as exc:
                    log.warning("hide: delete не удался: %s", exc.description)
            if data.startswith("hide_warn:") and self.warn_hide_cb is not None:
                parts = data.split(":", 2)
                if len(parts) == 3:
                    try:
                        self.warn_hide_cb(parts[1], parts[2])
                    except Exception:  # noqa: BLE001
                        log.warning("warn_hide_cb сбой", exc_info=True)
        cqid = cq.get("id")
        if cqid:
            try:
                await self.client.answer_callback_query(cqid, answer_text)
            except TelegramError:
                pass

    def _register_private_chats(self, update: dict[str, Any]) -> None:
        """Запомнить приватные чаты из апдейта — чтобы слать в них логи."""
        if self.chat_registry is None:
            return
        for chat_id, user in content.private_chats_in_update(update):
            if chat_id is None:
                continue
            user = user or {}
            uname = user.get("username")
            name = " ".join(p for p in (user.get("first_name"), user.get("last_name")) if p) or None
            if self.chat_registry.add(chat_id, username=uname, name=name):
                log.info("Зарегистрирован приватный чат id=%s%s",
                         chat_id, f" (@{uname})" if uname else "")

    async def _handle_message(self, norm: dict[str, Any]) -> None:
        log.info("MSG   %s", content.message_summary(norm))
        _ct = (norm.get("chat") or {}).get("type")
        if _ct == "private":
            text = (norm.get("text") or "").strip()
            cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
            contact = (norm.get("structured") or {}).get("contact")
            if contact:
                # Контакт (шеринг номера при входе в mini-app): сразу удаляем из чата —
                # номер телефона не должен оставаться в переписке/контент-журнале.
                # Чужой контакт нельзя использовать для входа: Bot API у self-contact
                # указывает user_id, совпадающий с отправителем сообщения.
                sender = norm.get("from") or {}
                sender_id = sender.get("id")
                contact_user_id = contact.get("user_id") if isinstance(contact, dict) else None
                phone = contact.get("phone_number") if isinstance(contact, dict) else None
                is_self = (sender_id is not None and contact_user_id is not None
                           and str(sender_id) == str(contact_user_id)
                           and not sender.get("is_bot"))
                if self.contact_cb is not None and is_self and phone:
                    try:
                        await self.contact_cb(sender_id, phone)
                    except Exception:  # noqa: BLE001 — удаление PII всё равно обязательно
                        log.warning("обработка подтверждённого Telegram-контакта не удалась",
                                    exc_info=True)
                elif self.contact_cb is not None:
                    log.warning("Telegram-контакт отклонён: это не self-contact")
                try:
                    await self.client.delete_message(
                        (norm.get("chat") or {}).get("id"), norm.get("message_id"))
                except TelegramError as exc:
                    log.warning("удаление сообщения с контактом не удалось: %s", exc.description)
                return
            elif cmd == "/claim" and self.ownership is not None:
                await self.ownership.handle_command(norm)   # код привязки — свой ответ
            elif self.dm_welcome is not None and not (norm.get("from") or {}).get("is_bot"):
                # Любое другое сообщение в личке (включая /start) → приветствие с кнопками.
                try:
                    await self.dm_welcome(norm)
                except Exception:  # noqa: BLE001 — приветствие не должно ломать приём
                    log.warning("dm_welcome сбой", exc_info=True)
            elif cmd and self.ownership is not None:
                await self.ownership.handle_command(norm)       # standalone: старое поведение
        elif _ct in ("group", "supergroup", "channel") and self.ownership is not None:
            await self.ownership.on_chat_message(norm)
        await self.storage.append_content(norm)
        if _is_service_message(norm):
            return
        if self.rule_router is not None:
            await self.rule_router(norm)              # маршрутизация по правилам mini-app
        else:
            await self._mirror_message(norm)          # репост СРАЗУ (в порядке, не ждёт скачивания)
        if self.download_media and norm["media"]:     # скачивание для хранилища — в фоне
            self._spawn_download(norm["chat"].get("id"), norm["media"], f"msg{norm['message_id']}")

    async def _handle_edit(self, norm: dict[str, Any]) -> None:
        log.info("EDIT  %s", content.message_summary(norm))
        await self.storage.append_content(norm)
        if self.rule_edit_router is not None:
            try:
                await self.rule_edit_router(norm)
            except Exception:  # noqa: BLE001
                log.warning("on_tg_edit сбой", exc_info=True)

    async def _on_album(self, album: dict[str, Any]) -> None:
        log.info("ALBUM [%s] %d медиа в порядке, message_ids=%s",
                 _chat_label(album["chat"]), album["media_count"], album["message_ids"])
        await self.storage.append_content(album)
        if self.rule_album is not None:
            await self.rule_album(album)              # маршрутизация альбома по правилам mini-app
        elif self.rule_router is None:
            await self._mirror_album(album)           # репост СРАЗУ (порядок альбома сохраняется)
        if self.download_media and album["media"]:    # скачивание — в фоне
            self._spawn_download(album["chat"].get("id"), album["media"],
                                 f"album_{album['media_group_id']}")

    async def _handle_other(self, update: dict[str, Any]) -> None:
        kind = next((k for k in update if k != "update_id"), "unknown")
        log.info("UPD   %s (update_id=%s)", kind, update.get("update_id"))
        await self.storage.append_content({
            "kind": "other", "update_kind": kind,
            "update_id": update.get("update_id"), "raw": update,
        })

    # --- скачивание медиа (в фоне, не задерживает репост) ---
    def _spawn_download(self, chat_id: Any, media_list: list[dict[str, Any]], label: str) -> None:
        task = asyncio.create_task(self._download_guarded(chat_id, media_list, label))
        self._dl_tasks.add(task)
        task.add_done_callback(self._dl_tasks.discard)

    async def _download_guarded(self, chat_id: Any, media_list: list[dict[str, Any]], label: str) -> None:
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
            order = int(media.get("album_order", media.get("order_index", 0)))
            targets: list[tuple[str, dict[str, Any]]] = []
            if media.get("type") == "paid_media":
                for sub in ("photo", "video"):
                    fd = media.get(sub)
                    if isinstance(fd, dict) and fd.get("file_id"):
                        targets.append((sub, fd))
            elif media.get("file_id"):
                targets.append((str(media.get("type")), media))
            for sub_idx, (mtype, fd) in enumerate(targets):
                await self._download_one(chat_id, fd, mtype, order, sub_idx, label)

    async def _download_one(self, chat_id: Any, fd: dict[str, Any], mtype: str,
                            order: int, sub_idx: int, label: str) -> None:
        file_id = fd.get("file_id")
        size = fd.get("file_size")
        if size and int(size) > self.max_download_bytes:
            log.warning("  ↳ пропуск %s: %d Б > лимита %d Б (нужен Local Bot API server)",
                        mtype, int(size), self.max_download_bytes)
            return
        try:
            info = await self.client.get_file(file_id)
        except TelegramError as exc:
            log.warning("  ↳ getFile не удался (%s): %s", mtype, exc.description)
            return
        file_path = info.get("file_path")
        if not file_path:
            log.warning("  ↳ getFile без file_path (%s)", mtype)
            return
        ext = Path(file_path).suffix or _ext_for(fd.get("mime_type"), mtype)
        name = f"{label}__{order:02d}_{sub_idx}__{mtype}{ext}"
        dest = self.storage.media_path(chat_id, name)
        try:
            written = await self.client.download_file(file_path, dest)
        except Exception as exc:  # noqa: BLE001
            log.warning("  ↳ скачивание не удалось (%s): %s", mtype, exc)
            return
        log.info("  ↳ %s: %d Б -> %s", mtype, written, dest.name)

    # --- синхронизация в личку владельца чата ---
    async def _mirror_message(self, norm: dict[str, Any]) -> None:
        if not (self.mirror and self.ownership is not None):
            return
        chat = norm.get("chat") or {}
        owner = self.ownership.owner_of(chat.get("id"))
        if owner is None:
            return
        # чисто сервисные сообщения копировать нельзя — пропускаем
        if norm.get("service") and not norm.get("text") and not norm.get("media") and not norm.get("structured"):
            return
        src, mid = chat.get("id"), norm.get("message_id")
        if src is not None and mid is not None:
            await self._repost(owner, src, [int(mid)], original=norm.get("raw"))

    async def _mirror_album(self, album: dict[str, Any]) -> None:
        if not (self.mirror and self.ownership is not None):
            return
        chat = album.get("chat") or {}
        owner = self.ownership.owner_of(chat.get("id"))
        if owner is None:
            return
        src = chat.get("id")
        mids = sorted({int(m) for m in album.get("message_ids", []) if m is not None})
        if src is not None and mids:
            await self._repost(owner, src, mids)

    async def _repost(self, target: Any, from_chat: Any, message_ids: list[int],
                      *, original: dict[str, Any] | None = None) -> None:
        """Репост в чат target ТОЛЬКО копированием (без пересылки).

        copyMessage/copyMessages не оставляют пометки «переслано» и ссылки на источник.
        Если копия невозможна — пытаемся ПЕРЕСОЗДАТЬ что можем (опрос -> sendPoll),
        иначе шлём владельцу короткую пометку (платное медиа/giveaway/invoice).
        """
        single = len(message_ids) == 1
        method = "copyMessage" if single else "copyMessages"
        id_param = {"message_id": message_ids[0]} if single else {"message_ids": message_ids}
        params = {"chat_id": target, "from_chat_id": from_chat, **id_param}
        async with self._mirror_lock:                 # строго по одному репосту за раз
            try:
                await self.client.call(method, params)
                return
            except TelegramError as exc:
                log.warning("mirror: %s -> %s не удался: %s", method, target, exc.description)
            if isinstance(original, dict) and isinstance(original.get("poll"), dict):
                if await self._recreate_poll(target, original["poll"]):
                    return
            await self._uncopyable_note(target, original)

    async def _recreate_poll(self, target: Any, poll: dict[str, Any]) -> bool:
        """Пересоздать опрос через sendPoll (викторину без correct_option_ids — как обычный)."""
        question = poll.get("question")
        options = [{"text": str(o.get("text", ""))} for o in (poll.get("options") or [])
                   if isinstance(o, dict)]
        if not question or len(options) < 2:
            return False
        coids = poll.get("correct_option_ids")
        is_quiz = poll.get("type") == "quiz" and bool(coids)
        params: dict[str, Any] = {
            "chat_id": target, "question": str(question)[:300], "options": options[:12],
            "is_anonymous": poll.get("is_anonymous", True),
            "type": "quiz" if is_quiz else "regular",
            "allows_multiple_answers": bool(poll.get("allows_multiple_answers", False)) and not is_quiz,
        }
        if is_quiz:
            params["correct_option_ids"] = coids
            if poll.get("explanation"):
                params["explanation"] = str(poll["explanation"])[:200]
        try:
            await self.client.call("sendPoll", params)
            log.info("mirror: опрос пересоздан в %s (type=%s, вариантов=%d)",
                     target, params["type"], len(options))
            return True
        except TelegramError as exc:
            log.warning("mirror: пересоздание опроса не удалось: %s", exc.description)
            return False

    async def _uncopyable_note(self, target: Any, original: dict[str, Any] | None) -> None:
        o = original or {}
        kind = "сообщение особого типа"
        if o.get("poll"):
            kind = "опрос"
        elif o.get("paid_media"):
            kind = "платное медиа"
        elif o.get("giveaway") or o.get("giveaway_winners"):
            kind = "розыгрыш (giveaway)"
        elif o.get("invoice"):
            kind = "счёт (invoice)"
        try:
            await self.client.call("sendMessage", {"chat_id": target,
                "text": f"⚠️ В привязанном чате опубликован тип, который нельзя скопировать "
                        f"({kind}). Пересылку не использую, поэтому сообщение пропущено.",
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Скрыть", "callback_data": "hide_msg"}]]}})
        except TelegramError:
            pass


class Stage1Poller:
    """Long polling getUpdates поверх общего UpdateRouter."""

    def __init__(self, client: TelegramClient, storage: Storage, *,
                 allowed_updates: list[str], timeout: int, limit: int,
                 download_media: bool, max_download_bytes: int,
                 media_debounce: float, chat_registry=None, ownership=None,
                 mirror: bool = True, rule_router=None, rule_album=None,
                 rule_edit_router=None, warn_hide_cb=None, dm_welcome=None,
                 contact_cb=None, health=None) -> None:
        self.client = client
        self.storage = storage
        self.allowed_updates = allowed_updates
        self.timeout = timeout
        self.limit = limit
        self._hb = health   # ops-живость (этап 4.5): лёгкий прокси или None
        self.router = UpdateRouter(
            client, storage, download_media=download_media,
            max_download_bytes=max_download_bytes, media_debounce=media_debounce,
            chat_registry=chat_registry, ownership=ownership, mirror=mirror,
            rule_router=rule_router, rule_album=rule_album,
            rule_edit_router=rule_edit_router, warn_hide_cb=warn_hide_cb,
            dm_welcome=dm_welcome, contact_cb=contact_cb)

    async def run(self) -> None:
        offset = await self.storage.load_offset()
        log.info("Long polling: offset=%s, allowed_updates=%d типов, скачивание медиа=%s",
                 offset, len(self.allowed_updates), self.router.download_media)
        async with self.router:
            while True:
                try:
                    updates = await self.client.get_updates(
                        offset, timeout=self.timeout, limit=self.limit,
                        allowed_updates=self.allowed_updates)
                except TelegramError as exc:
                    if self._hb:
                        self._hb.error(exc)
                    if exc.error_code == 409:
                        log.error("409 Conflict — установлен webhook или запущен другой "
                                  "экземпляр getUpdates. Пауза 5с. (%s)", exc.description)
                        await asyncio.sleep(5)
                        continue
                    raise
                if self._hb:
                    self._hb.poll()
                if not updates:
                    continue
                if self._hb:
                    self._hb.update()
                for upd in updates:
                    offset = int(upd["update_id"]) + 1
                    await self.router.process(upd)
                await self.storage.save_offset(offset)

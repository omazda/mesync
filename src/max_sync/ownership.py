"""Привязка чата к пользователю («принадлежность бота») для MAX.

Флоу (аналог telegram_sync.ownership):
1) Пользователь добавляет бота в группу/канал (бот должен стать администратором,
   иначе MAX не присылает события чата).
2) В личке шлёт /claim — бот выдаёт уникальный 4-значный код (10 минут).
3) Пользователь отправляет код СООБЩЕНИЕМ в чат (мгновенно, через message_created)
   ИЛИ вписывает в КОНЕЦ описания чата (запасной путь — фоновый свипер читает
   описание через GET /chats/{chatId}).
4) При совпадении чат привязывается к пользователю; проверяются права бота
   (GET /chats/{chatId}/members/me → is_admin + permissions) → владельцу уходит
   «успешно» либо «недостаточно прав».

Состояние персистится в data/max/ownership.json. Методы сверены с docs/max/.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import time
from pathlib import Path
from typing import Any

from . import content
from .client import MaxClient, MaxError

log = logging.getLogger(__name__)

CODE_TTL = 600                       # срок жизни кода, секунды (10 минут)
SWEEP_STEP = 10                      # свип описаний на отметках :00/:10/.../:50
_TRAILING_CODE = re.compile(r"(?<!\d)(\d{4})\s*$")   # ровно 4 цифры в КОНЦЕ описания
# Право, позволяющее боту читать все сообщения чата/канала.
# Техническое сообщение для проверки права на ОТПРАВКУ при привязке (шлём и сразу удаляем).
_CONNECT_PROBE_TEXT = "✅ Бот успешно подключён"


HELP_TEXT = (
    "Привет! Я связываю ваши группы и каналы с вами.\n\n"
    "Как привязать чат:\n"
    "1) Добавьте меня в нужную группу или канал и сделайте администратором "
    "(иначе MAX не присылает сообщения чата боту).\n"
    "2) Пришлите сюда /claim — выдам код из 4 цифр (действует 10 минут).\n"
    "3) Отправьте код сообщением в этот чат (мгновенно) ИЛИ впишите в конец описания.\n"
    "4) Я найду код и пришлю результат.\n\n"
    "Команды: /claim — получить код, /status — мои чаты, /unlink — отвязать чат (бот выйдет из него)."
)


class OwnershipManager:
    """Хранит коды/чаты/владения и крутит фоновый свипер описаний."""

    def __init__(self, client: MaxClient, path: Path, *,
                 bot_id: int | None = None, code_ttl: int = CODE_TTL,
                 raw_updates_file: Path | None = None,
                 extra_codes_provider=None, on_external_claim=None,
                 on_removed=None) -> None:
        self.client = client
        self.path = Path(path)
        self.bot_id = bot_id
        self.code_ttl = code_ttl
        self.raw_updates_file = Path(raw_updates_file) if raw_updates_file else None
        # Хуки mini-app: коды привязки, выданные через control-API, и колбэк после
        # привязки по такому коду. По умолчанию None → поведение не меняется.
        self.extra_codes_provider = extra_codes_provider
        self.on_external_claim = on_external_claim
        # Хук удаления источника: on_removed(chat_id, title) — control-store чистит правила,
        # account_sources и pending-коды при bot_removed или /unlink.
        self.on_removed = on_removed
        self._chats: dict[str, dict[str, Any]] = {}    # chat_id -> {type,title}
        self._owners: dict[str, dict[str, Any]] = {}   # chat_id -> {user_id,title,rights_ok,claimed_at}
        self._pending: dict[str, dict[str, Any]] = {}  # user_id -> {code,expires_at}
        self._lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._stop = asyncio.Event()
        self._sweeper: asyncio.Task[None] | None = None
        self._load()
        if self.raw_updates_file:
            self._seed_chats_from_raw(self.raw_updates_file)

    # ---------- персист ----------
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return
        self._chats = data.get("chats", {})
        self._owners = data.get("owners", {})
        self._pending = data.get("pending", {})

    def title_of(self, chat_id: Any) -> str | None:
        """Название чата/канала по chat_id (для подписи постов каналов). In-memory, без сети."""
        key = str(chat_id)
        return ((self._owners.get(key) or {}).get("title")
                or (self._chats.get(key) or {}).get("title"))

    def _save_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"chats": self._chats, "owners": self._owners, "pending": self._pending}
        # Атомарно (tmp + replace): control-API читает этот файл конкурентно (list_sources),
        # частичная запись дала бы временно пустой owners и «исчезновение» всех источников.
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    async def _save(self) -> None:
        await asyncio.to_thread(self._save_sync)

    def _seed_chats_from_raw(self, raw_path: Path) -> None:
        """Подтянуть группы/каналы из истории событий, чтобы свипать и те чаты,
        куда бот добавлен ранее, не дожидаясь нового события."""
        if not raw_path.exists():
            return
        try:
            lines = raw_path.read_text(encoding="utf-8").splitlines()
        except Exception:  # noqa: BLE001
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                upd = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            for chat in content.chats_in_update(upd):
                cid = chat.get("chat_id")
                if cid is not None:
                    rec = self._chats.get(str(cid), {})
                    rec["type"] = chat.get("type") or rec.get("type")
                    if chat.get("title"):
                        rec["title"] = chat.get("title")
                    self._chats[str(cid)] = rec

    # ---------- лайфцикл ----------
    async def __aenter__(self) -> "OwnershipManager":
        self._sweeper = asyncio.create_task(self._sweeper_loop())
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._sweeper is not None:
            try:
                await asyncio.wait_for(self._sweeper, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._sweeper.cancel()
            self._sweeper = None

    # ---------- коды ----------
    def _purge_expired(self) -> None:
        now = time.time()
        for uid in [u for u, v in self._pending.items() if v.get("expires_at", 0) <= now]:
            del self._pending[uid]

    def _active_codes(self) -> dict[str, Any]:
        """code -> user_id для всех непросроченных кодов.

        Дополнительно подмешивает коды, выданные из mini-app (control-API): их
        значение — маркер {'external': True, ...}, привязка идёт к ОТПРАВИТЕЛЮ кода.
        """
        self._purge_expired()
        out: dict[str, Any] = {v["code"]: v.get("user_id", _as_int(uid)) for uid, v in self._pending.items()}
        if self.extra_codes_provider is not None:
            try:
                for code, marker in (self.extra_codes_provider() or {}).items():
                    out.setdefault(str(code), {"external": True, **(marker or {})})
            except Exception:  # noqa: BLE001
                log.warning("extra_codes_provider сбой", exc_info=True)
        return out

    def _issue_code(self, user_id: Any) -> tuple[str, int]:
        self._purge_expired()
        existing = self._pending.get(str(user_id))
        if existing and existing.get("expires_at", 0) > time.time():
            return existing["code"], existing["expires_at"]
        taken = {v["code"] for v in self._pending.values()}
        code = None
        for _ in range(20000):
            candidate = f"{secrets.randbelow(10000):04d}"
            if candidate not in taken:
                code = candidate
                break
        if code is None:
            raise RuntimeError("Свободных кодов нет (все 10000 заняты)")
        expires = int(time.time()) + self.code_ttl
        self._pending[str(user_id)] = {"code": code, "expires_at": expires, "user_id": user_id}
        return code, expires

    # ---------- наблюдение за событиями ----------
    def owner_of(self, chat_id: Any) -> Any | None:
        rec = self._owners.get(str(chat_id))
        return rec.get("user_id") if rec else None

    async def observe(self, update: dict[str, Any]) -> None:
        """Зарегистрировать чаты бота и обработать удаление бота из чата."""
        changed = False
        for chat in content.chats_in_update(update):
            cid = str(chat.get("chat_id"))
            rec = dict(self._chats.get(cid, {}))
            is_new = cid not in self._chats
            rec["type"] = chat.get("type") or rec.get("type")
            if chat.get("title"):
                rec["title"] = chat.get("title")
            if self._chats.get(cid) != rec:
                self._chats[cid] = rec
                changed = True
            if is_new:
                log.info("ownership: бот теперь отслеживает чат %s", cid)
                if self._active_codes():
                    self._wake.set()

        ut = update.get("update_type")
        if ut == "bot_removed" and update.get("chat_id") is not None:
            cid = str(update.get("chat_id"))
            owner = self._owners.get(cid)
            if self._chats.pop(cid, None) is not None:
                changed = True
            title = (owner or {}).get("title") or cid
            if owner:
                self._owners.pop(cid, None)
                changed = True
                if owner.get("user_id") is not None:
                    await self._reply(owner["user_id"], f"⚠️ Меня удалили из «{title}» — привязка снята.")
            await self._notify_removed(cid, title)
        elif ut == "bot_added" and update.get("chat_id") is not None:
            # бот добавлен — если есть активные коды, проверим описание сразу
            if self._active_codes():
                self._wake.set()
        if changed:
            await self._save()

    async def _notify_removed(self, chat_id: Any, title: Any = None) -> None:
        if self.on_removed is None:
            return
        try:
            await self.on_removed(str(chat_id), title)
        except Exception:  # noqa: BLE001
            log.warning("on_removed сбой для чата %s", chat_id, exc_info=True)

    # ---------- команды ----------
    async def handle_command(self, norm: dict[str, Any]) -> None:
        uid = norm.get("sender_id")
        text = (norm.get("text") or "").strip()
        cmd = text.split()[0].split("@")[0].lower() if text else ""
        if uid is None:
            return
        if cmd in ("/start", "/help"):
            await self._reply(uid, HELP_TEXT, hide=False)   # приветствие — без «Скрыть»
        elif cmd == "/claim":
            async with self._lock:
                code, _exp = self._issue_code(uid)
                await self._save()
            self._wake.set()
            log.info("ownership: выдан код пользователю %s; известных чатов: %d",
                     uid, len(self._chats))
            await self._reply(uid,
                f"Ваш код: {code}\n\n"
                "Быстро: отправьте этот код сообщением в группу/канал, куда меня добавили — привяжу за секунды.\n"
                "Либо впишите код в КОНЕЦ описания чата.\n"
                "Код действует 10 минут.")
        elif cmd == "/status":
            mine = self._user_chats(uid)
            if not mine:
                await self._reply(uid, "У вас пока нет привязанных чатов. Команда /claim — чтобы привязать.")
            else:
                lines = ["Ваши чаты:"]
                for i, (cid, o) in enumerate(mine, 1):
                    mark = "✅ права ок" if o.get("rights_ok") else "⚠️ не хватает прав (нужен админ)"
                    lines.append(f"{i}. {o.get('title') or cid} — {mark}")
                lines.append("\nОтвязать: /unlink <номер> — бот выйдет из чата.")
                await self._reply(uid, "\n".join(lines))
        elif cmd == "/unlink":
            await self._handle_unlink(text, uid)

    async def on_chat_message(self, norm: dict[str, Any]) -> None:
        """Мгновенная привязка: код прислан СООБЩЕНИЕМ в группу/канал."""
        cid = str(norm.get("chat_id"))
        # Пересланный пост — это репост, а не ввод кода (его текст теперь виден после
        # нормализации link.message); код привязки вводят сообщением, поэтому форварды
        # в сопоставлении кодов не участвуют (иначе число в новостном посте, равное
        # активному коду, могло бы ложно перепривязать чат).
        if norm.get("is_forward"):
            return
        text = norm.get("text") or ""
        if not text:
            return
        existing = self._owners.get(cid)
        # Уже привязан к реальному пользователю — пропускаем; «осиротевший» чат
        # (owner=None, каналы без отправителя) переобрабатываем для привязки к аккаунту.
        if existing and existing.get("user_id") is not None:
            return
        active = self._active_codes()
        if not active:
            return
        for match in re.finditer(r"(?<!\d)(\d{4})(?!\d)", text):
            code = match.group(1)
            uid = active.get(code)
            if uid is None:
                continue
            try:
                full = await self.client.get_chat(norm.get("chat_id"))
            except MaxError:
                full = {"chat_id": norm.get("chat_id"), "type": norm.get("chat_type")}
            if isinstance(uid, dict) and uid.get("external"):
                # Код mini-app: привязываем чат к отправителю и уведомляем control-API.
                sender = norm.get("sender_id")
                await self._claim(full, sender, notify=False)  # лаконичное сообщение шлёт on_external_claim
                if self.on_external_claim is not None:
                    try:
                        await self.on_external_claim(code, sender, full, uid)
                    except Exception:  # noqa: BLE001
                        log.warning("on_external_claim сбой", exc_info=True)
            else:
                await self._claim(full, uid)
            return

    async def _reply(self, user_id: Any, text: str, *, hide: bool = True) -> None:
        """Служебное сообщение бота в диалог. hide=True — inline-кнопка «Скрыть» (колбэк
        hide_msg, бот удаляет сообщение); False — только у приветствия HELP_TEXT."""
        attachments = None
        if hide:
            attachments = [{"type": "inline_keyboard", "payload": {
                "buttons": [[{"type": "callback", "text": "Скрыть", "payload": "hide_msg"}]]}}]
        try:
            await self.client.send_message(user_id=user_id, text=text, attachments=attachments)
        except MaxError as exc:
            log.warning("ownership: не отправил сообщение user=%s: %s", user_id, exc.description)

    # ---------- свипер описаний ----------
    async def _sweeper_loop(self) -> None:
        try:
            while not self._stop.is_set():
                active = self._active_codes()
                if not active:
                    self._wake.clear()
                    await self._wake.wait()
                    continue
                await self._sweep_once(active)
                if self._stop.is_set():
                    break
                self._wake.clear()
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=self._seconds_to_boundary())
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass

    def _seconds_to_boundary(self) -> float:
        now = time.time()
        return max(0.1, (int(now) // SWEEP_STEP + 1) * SWEEP_STEP - now)

    async def _sweep_once(self, active: dict[str, str]) -> None:
        if not active:
            return
        log.debug("Свип описаний: чатов=%d, активных кодов=%d", len(self._chats), len(active))
        for cid in list(self._chats.keys()):
            if self._stop.is_set() or not active:
                break
            if cid in self._owners:
                continue
            try:
                chat = await self.client.get_chat(int(cid))
            except (MaxError, ValueError) as exc:
                log.debug("getChat(%s) не удался: %s", cid, exc)
                continue
            desc = (chat.get("description") or "").strip()
            m = _TRAILING_CODE.search(desc)
            if not m:
                continue
            uid = active.get(m.group(1))
            if uid and not (isinstance(uid, dict) and uid.get("external")):
                # Коды mini-app (external) привязываются только по сообщению
                # (нужен отправитель), через описание — нет.
                await self._claim(chat, uid)
                active = self._active_codes()

    async def _claim(self, chat: dict[str, Any], user_id: Any, *, notify: bool = True) -> None:
        cid = str(chat.get("chat_id"))
        title = chat.get("title") or cid
        rights_ok = await self._probe_write_rights(cid)
        self._owners[cid] = {"user_id": user_id, "title": title, "type": chat.get("type"),
                             "rights_ok": rights_ok, "claimed_at": int(time.time())}
        self._pending.pop(str(user_id), None)
        # обновим тип/название чата в реестре
        rec = dict(self._chats.get(cid, {}))
        rec["type"] = chat.get("type") or rec.get("type")
        if chat.get("title"):
            rec["title"] = chat.get("title")
        self._chats[cid] = rec
        await self._save()
        if not notify or user_id is None:
            pass  # привязка из mini-app шлёт лаконичное сообщение сама; канал — без личут
        elif rights_ok:
            await self._reply(user_id, f"✅ Готово! Чат «{title}» привязан к вам.")
        else:
            await self._reply(user_id,
                f"⚠️ Нашёл код в «{title}», но не смог отправить туда сообщение. "
                "Назначьте бота администратором с правом отправлять сообщения.")
        log.info("ownership: чат %s («%s») привязан к user=%s, права=%s",
                 cid, title, user_id, "ок" if rights_ok else "недостаточно")

    async def _probe_write_rights(self, chat_id: Any) -> bool:
        """Проверка права на ОТПРАВКУ при привязке: шлём техническое сообщение и сразу его
        удаляем. Право на ЧТЕНИЕ отдельно НЕ запрашиваем — факт получения кода уже доказывает,
        что бот читает сообщения чата (в MAX события приходят боту только при read_all_messages).
        Так избегаем лишних запросов к MAX API: при тысячах каналов (лимит ~30 rps) проверка
        идёт только в момент привязки, без периодических опросов; потерю прав в рантайме ловим
        реактивно по ошибке доставки (см. RuleDispatcher)."""
        try:
            res = await self.client.send_message(chat_id=int(chat_id), text=_CONNECT_PROBE_TEXT)
        except (MaxError, ValueError) as exc:
            log.warning("ownership: тест-отправка в чат %s не удалась (нет права на отправку?): %s",
                        chat_id, exc)
            return False
        mid = ((res or {}).get("message") or {}).get("body", {}).get("mid")
        if mid:
            try:
                await self.client.delete_message(mid)
            except (MaxError, ValueError) as exc:
                log.warning("ownership: тест-сообщение в %s не удалось удалить: %s", chat_id, exc)
        return True

    def _user_chats(self, uid: Any) -> list[tuple[str, dict[str, Any]]]:
        items = [(cid, o) for cid, o in self._owners.items() if str(o.get("user_id")) == str(uid)]
        items.sort(key=lambda x: (x[1].get("claimed_at", 0), x[0]))
        return items

    async def _handle_unlink(self, text: str, uid: Any) -> None:
        mine = self._user_chats(uid)
        if not mine:
            await self._reply(uid, "У вас нет привязанных чатов.")
            return
        parts = text.split()
        if len(parts) < 2:
            if len(mine) == 1:
                await self._unlink(mine[0][0], uid)
            else:
                lines = ["Какой чат отвязать? Отправьте /unlink <номер>:"]
                for i, (cid, o) in enumerate(mine, 1):
                    lines.append(f"{i}. {o.get('title') or cid}")
                await self._reply(uid, "\n".join(lines))
            return
        try:
            idx = int(parts[1])
        except ValueError:
            idx = -1
        if 1 <= idx <= len(mine):
            await self._unlink(mine[idx - 1][0], uid)
        else:
            await self._reply(uid, "Неверный номер. Отправьте /unlink, чтобы увидеть список.")

    async def unbind(self, chat_id: Any) -> bool:
        """Снять привязку чата и выйти из него (вызов из mini-app при удалении источника).
        В отличие от _unlink — без проверки владельца (control-API уже проверил владение)
        и без ответа пользователю (mini-app шлёт своё уведомление). Удаляет запись из
        ownership.json, чтобы источник СРАЗУ исчез из списка. Возвращает True, если запись была."""
        cid = str(chat_id)
        existed = cid in self._owners
        owner = self._owners.pop(cid, None)
        title = (owner or {}).get("title") or cid
        self._chats.pop(cid, None)
        await self._save()
        await self._notify_removed(cid, title)
        await self._leave_chat(cid)
        return existed

    async def _unlink(self, cid: str, uid: Any) -> None:
        owner = self._owners.get(cid)
        if not owner or str(owner.get("user_id")) != str(uid):
            await self._reply(uid, "Это не ваш чат или он не привязан.")
            return
        title = owner.get("title") or cid
        # Снимаем привязку ДО выхода, чтобы bot_removed не задублировал уведомление.
        self._owners.pop(cid, None)
        self._chats.pop(cid, None)
        await self._save()
        await self._notify_removed(cid, title)
        left = await self._leave_chat(cid)
        if left:
            await self._reply(uid, f"Отвязал «{title}» и вышел из чата.")
        else:
            await self._reply(uid, f"Отвязал «{title}». Выйти из чата не удалось (возможно, меня там уже нет).")
        log.info("ownership: чат %s отвязан пользователем %s (leave=%s)", cid, uid, left)

    async def _leave_chat(self, cid: str) -> bool:
        try:
            await self.client.leave_chat(int(cid))
            return True
        except (MaxError, ValueError) as exc:
            log.warning("ownership: leaveChat(%s) не удался: %s", cid, exc)
            return False


def _as_int(value: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value

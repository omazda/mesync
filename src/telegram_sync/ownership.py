"""Привязка чата к пользователю («принадлежность бота»).

Флоу:
1) Пользователь добавляет бота в группу/канал.
2) В личке шлёт /claim — бот выдаёт уникальный 4-значный код (действует 10 минут).
3) Пользователь дописывает код в КОНЕЦ описания чата.
4) Фоновый свипер (раз в 10 c, выровнен на :00/:10/.../:50; на ПАУЗЕ, если активных
   кодов нет) читает описания всех чатов бота (getChat) и ищет код в конце.
5) При совпадении чат привязывается к пользователю; проверяются права бота
   (администратор?) → пользователю уходит «успешно» либо «недостаточно прав».

Состояние персистится в data/ownership.json. Методы сверены с
docs/telegram/markdown/04-api-reference.md (getChat→ChatFullInfo.description,
getChatMember→ChatMember.status).
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
from .client import TelegramClient, TelegramError

log = logging.getLogger(__name__)

CODE_TTL = 600                       # срок жизни кода, секунды (10 минут)
SWEEP_STEP = 10                      # свип на отметках :00/:10/.../:50
_TRAILING_CODE = re.compile(r"(?<!\d)(\d{4})\s*$")   # ровно 4 цифры в КОНЦЕ описания
SWEEPABLE_TYPES = {"group", "supergroup", "channel"}
_ADMIN_STATUSES = {"administrator", "creator"}

def _as_int(value: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _rights_ok_from(member: dict[str, Any], chat: dict[str, Any], bot_can_read_all: bool = True) -> bool:
    """Достаточно ли у бота прав для синхронизации.

    - Группа/супергруппа: особые права НЕ нужны. Бот и так пишет как участник и читает
      сообщения (при выключенном Privacy Mode — глобальная настройка бота в BotFather).
      Поэтому участник (не покинувший/не забаненный) считается готовым.
    - Канал: нужен администратор с правом публикации `can_post_messages` (для синхронизации
      правок/удалений рекомендуются также can_edit_messages/can_delete_messages — их
      отсутствие не блокирует базовую пересылку постов).
    - Личный чат: всегда ок.

    (`bot_can_read_all` оставлен для совместимости сигнатуры; для групп теперь не требуется.)
    """
    status = (member or {}).get("status")
    if status in ("left", "kicked"):
        return False
    chat_type = (chat or {}).get("type")
    if chat_type in ("group", "supergroup"):
        return True
    if chat_type == "channel":
        if status == "creator":
            return True
        if status != "administrator":
            return False
        return bool(member.get("can_post_messages"))
    return True


def _bot_can_read(member: dict[str, Any], chat_type: Any) -> bool:
    """Может ли бот ЧИТАТЬ сообщения чата (роль ИСТОЧНИКА в правиле).

    - Канал: посты приходят боту обновлениями ТОЛЬКО если он администратор (любые права) —
      поэтому для чтения нужен статус administrator/creator.
    - Группа/супергруппа: участник читает сообщения (Privacy Mode — глобальная настройка бота
      в BotFather, не право конкретного чата), поэтому достаточно не быть покинувшим/забаненным.
    - Личный чат: всегда.
    Сверено с docs/telegram/.../04-api-reference.md (ChatMember статусы; channel_post для админов).
    """
    status = (member or {}).get("status")
    if status in ("left", "kicked"):
        return False
    if chat_type == "channel":
        return status in _ADMIN_STATUSES
    return True


def _bot_can_write(member: dict[str, Any], chat_type: Any) -> bool:
    """Может ли бот ПИСАТЬ в чат (роль ПРИЁМНИКА в правиле).

    - Канал: нужен creator ИЛИ administrator с правом публикации `can_post_messages`.
    - Группа/супергруппа: писать может любой неограниченный участник; ограничение
      (ChatMemberRestricted) снимает право, если `can_send_messages` = false.
    - Личный чат: всегда.
    Поля сверены с docs/telegram (ChatMemberAdministrator.can_post_messages,
    ChatMemberRestricted.can_send_messages).
    """
    status = (member or {}).get("status")
    if status in ("left", "kicked"):
        return False
    if chat_type == "channel":
        if status == "creator":
            return True
        return status == "administrator" and bool(member.get("can_post_messages"))
    if status == "restricted":
        return bool(member.get("can_send_messages"))
    return True


def _missing_rights_reason(member: dict[str, Any], chat_type: Any, *,
                           read: bool, write: bool) -> str:
    """Человекочитаемое название изъятого значимого права — для просьбы вернуть его.
    Вызывается, только когда чего-то не хватает (read и/или write = False). Формулировки
    совпадают с инструкцией привязки в mini-app (web/src/screens/sources.jsx)."""
    status = (member or {}).get("status")
    if chat_type == "channel":
        if status not in _ADMIN_STATUSES:
            return "права администратора канала (с правом «Публикация сообщений»)"
        return "право «Публикация сообщений»"
    return "право отправлять сообщения"


HELP_TEXT = (
    "Привет! Я связываю ваши группы и каналы с вами.\n\n"
    "Как привязать чат:\n"
    "1) Добавьте меня в нужную группу или канал.\n"
    "2) Пришлите сюда /claim — выдам код из 4 цифр (действует 10 минут).\n"
    "3) Отправьте код сообщением в этот чат (мгновенно) ИЛИ впишите в конец описания (до ~минуты).\n"
    "4) Я найду код и пришлю результат.\n\n"
    "Команды: /claim — получить код, /status — мои чаты, /unlink — отвязать чат (бот выйдет из него)."
)


class OwnershipManager:
    """Хранит коды/чаты/владения и крутит фоновый свипер описаний."""

    def __init__(self, client: TelegramClient, path: Path, *,
                 bot_id: int | None = None, code_ttl: int = CODE_TTL,
                 raw_updates_file: Path | None = None,
                 bot_can_read_all: bool = False,
                 extra_codes_provider=None, on_external_claim=None,
                 on_rights_change=None, on_chat_migrated=None,
                 on_removed=None) -> None:
        self.client = client
        self.path = Path(path)
        self.bot_id = bot_id
        self.code_ttl = code_ttl
        self.bot_can_read_all = bot_can_read_all   # глобальный Privacy Mode выключен?
        self.raw_updates_file = Path(raw_updates_file) if raw_updates_file else None
        # Хуки mini-app (control-API): коды привязки и колбэк после привязки.
        # По умолчанию None → поведение бота не меняется.
        self.extra_codes_provider = extra_codes_provider
        self.on_external_claim = on_external_claim
        # Хук изменения прав бота в чате (из my_chat_member): on_rights_change(chat_id, can_read,
        # can_write, reason) — диспетчер поднимает/снимает warning по правилам этого чата. БЕЗ него
        # реакции на смену прав нет (поведение прежнее).
        self.on_rights_change = on_rights_change
        # Хук миграции группа→супергруппа: on_chat_migrated(old_id, new_id) — координатор в run_app
        # переносит владение (migrate_chat) и перепривязывает правила. БЕЗ него миграция не ловится
        # проактивно (но реактивный self-heal по ошибке доставки всё равно сработает).
        self.on_chat_migrated = on_chat_migrated
        # Хук удаления источника: on_removed(chat_id, title) — control-store чистит правила,
        # account_sources и pending-коды, когда бота удалили из чата или пользователь сделал /unlink.
        self.on_removed = on_removed
        self._chats: dict[str, dict[str, Any]] = {}    # chat_id -> {type,title,username}
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
        if key not in self._owners and key not in self._chats and ":" in key:
            key = key.split(":", 1)[0]
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
        """Подтянуть группы/каналы из истории сырых апдейтов, чтобы свипать и те
        чаты, куда бот добавлен ранее, не дожидаясь нового апдейта."""
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
                if chat.get("type") in SWEEPABLE_TYPES and chat.get("id") is not None:
                    self._chats[str(chat["id"])] = {
                        "type": chat.get("type"), "title": chat.get("title"),
                        "username": chat.get("username"), "is_forum": chat.get("is_forum")}

    # ---------- лайфцикл ----------
    async def __aenter__(self) -> "OwnershipManager":
        self._sweeper = asyncio.create_task(self._sweeper_loop())
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        self._stop.set()
        self._wake.set()  # разбудить свипер, если он ждёт коды
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
        """code -> user_id (исходного типа) для всех непросроченных кодов.

        Дополнительно подмешивает коды mini-app (control-API) маркером
        {'external': True, ...}; привязка по такому коду идёт к ОТПРАВИТЕЛЮ.
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
            return existing["code"], existing["expires_at"]      # уже есть валидный
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

    # ---------- наблюдение за апдейтами ----------
    def owner_of(self, chat_id: Any) -> Any | None:
        """user_id владельца привязанного чата, либо None."""
        rec = self._owners.get(str(chat_id))
        return rec.get("user_id") if rec else None

    async def observe(self, update: dict[str, Any]) -> None:
        """Зарегистрировать чаты бота и обработать повышение прав."""
        changed = False
        for chat in content.chats_in_update(update):
            if chat.get("type") in SWEEPABLE_TYPES:
                cid = str(chat.get("id"))
                rec = {"type": chat.get("type"), "title": chat.get("title"),
                       "username": chat.get("username"), "is_forum": chat.get("is_forum")}
                is_new = cid not in self._chats
                if self._chats.get(cid) != rec:
                    self._chats[cid] = rec
                    changed = True
                if is_new:
                    log.info("ownership: бот теперь отслеживает чат %s («%s»)", cid, chat.get("title"))
                    if self._active_codes():
                        self._wake.set()      # есть активный код — проверить новый чат сразу

        mcm = update.get("my_chat_member")
        if isinstance(mcm, dict) and self.bot_id is not None:
            new = mcm.get("new_chat_member") or {}
            if (new.get("user") or {}).get("id") == self.bot_id:
                chat_obj = mcm.get("chat") or {}
                cid = str(chat_obj.get("id"))
                status = new.get("status")
                owner = self._owners.get(cid)
                title = (owner or {}).get("title") or chat_obj.get("title") or cid
                if status in ("left", "kicked"):              # бота удалили/забанили → снять привязку
                    if self._chats.pop(cid, None) is not None:
                        changed = True
                    if owner:
                        self._owners.pop(cid, None)
                        changed = True
                        if owner.get("user_id") is not None:
                            await self._reply(owner["user_id"],
                                              f"⚠️ Меня удалили из «{title}» — привязка снята.")
                    await self._notify_removed(cid, title)
                else:
                    # Изменение прав (НЕ удаление): источник/правило НЕ отключаем (rights_ok НЕ
                    # трогаем — источник остаётся «ок»). Если изменилась способность ЧИТАТЬ/ПИСАТЬ —
                    # зовём хук: диспетчер поднимет/снимет тот же warning, что и в MAX (баннер
                    # mini-app + сообщение владельцу с просьбой вернуть право). Полное отслеживание
                    # изменений прав по событию my_chat_member (аналога в MAX нет — там реактивно).
                    await self._observe_rights_change(cid, chat_obj.get("type"),
                                                      mcm.get("old_chat_member") or {}, new)
        if changed:
            await self._save()
        # Миграция группа→супергруппа ПОСЛЕ регистрации чатов: если сигнал пришёл из старой группы,
        # её id уже зарегистрирован выше — migrate_chat перенесёт его на новый, не оставив дубля.
        await self._observe_migration(update)

    async def _observe_rights_change(self, cid: str, chat_type: Any,
                                     old: dict[str, Any], new: dict[str, Any]) -> None:
        """Сменились права бота в чате (my_chat_member, не удаление). Если изменилась способность
        ЧИТАТЬ (роль источника) или ПИСАТЬ (роль приёмника) — зовём on_rights_change; диспетчер
        решает по правилам этого чата, поднять или снять warning. rights_ok НЕ меняем — источник
        не отключается, мы только предупреждаем (и просим вернуть изъятое право)."""
        if self.on_rights_change is None:
            return
        read_new, write_new = _bot_can_read(new, chat_type), _bot_can_write(new, chat_type)
        if (read_new, write_new) == (_bot_can_read(old, chat_type), _bot_can_write(old, chat_type)):
            return                                            # значимые способности не изменились
        reason = _missing_rights_reason(new, chat_type, read=read_new, write=write_new)
        try:
            await self.on_rights_change(cid, read_new, write_new, reason)
        except Exception:  # noqa: BLE001
            log.warning("on_rights_change сбой для чата %s", cid, exc_info=True)

    async def _observe_migration(self, update: dict[str, Any]) -> None:
        """Группа повышена до супергруппы → Telegram сменил chat_id. Сигнал приходит сервисным
        сообщением: в СТАРОЙ группе с `migrate_to_chat_id` (новый id), в НОВОЙ супергруппе с
        `migrate_from_chat_id` (старый id) — оба дают пару old→new. Зовём хук-координатор (он
        перенесёт владение и перепривяжет правила). Идемпотентно: сигнал приходит дважды."""
        if self.on_chat_migrated is None:
            return
        msg = update.get("message")
        if not isinstance(msg, dict):
            msg = update.get("edited_message")
        if not isinstance(msg, dict):
            return
        chat_id = (msg.get("chat") or {}).get("id")
        to_id = msg.get("migrate_to_chat_id")
        from_id = msg.get("migrate_from_chat_id")
        if to_id is not None:                 # мы в СТАРОЙ группе: chat_id(old) → to_id(new)
            old_id, new_id = chat_id, to_id
        elif from_id is not None:             # мы в НОВОЙ супергруппе: from_id(old) → chat_id(new)
            old_id, new_id = from_id, chat_id
        else:
            return
        if old_id is None or new_id is None or str(old_id) == str(new_id):
            return
        try:
            await self.on_chat_migrated(str(old_id), str(new_id))
        except Exception:  # noqa: BLE001
            log.warning("on_chat_migrated сбой %s→%s", old_id, new_id, exc_info=True)

    async def _notify_removed(self, chat_id: Any, title: Any = None) -> None:
        if self.on_removed is None:
            return
        try:
            await self.on_removed(str(chat_id), title)
        except Exception:  # noqa: BLE001
            log.warning("on_removed сбой для чата %s", chat_id, exc_info=True)

    async def migrate_chat(self, old_chat_id: Any, new_chat_id: Any) -> bool:
        """Перенести владение/запись чата со старого id на новый (группа повышена до супергруппы).
        Идемпотентно: повторный вызов (сигнал миграции приходит дважды / из реактивного пути) —
        no-op. Возвращает True, если что-то перенесли. rights_ok сохраняем как был."""
        old_id, new_id = str(old_chat_id), str(new_chat_id)
        if old_id == new_id:
            return False
        moved = False
        async with self._lock:
            owner = self._owners.pop(old_id, None)
            if owner is not None:
                owner["type"] = "supergroup"
                owner["is_forum"] = True
                self._owners.setdefault(new_id, owner)
                moved = True
            rec = self._chats.pop(old_id, None)
            if rec is not None:
                rec["type"] = "supergroup"
                rec["is_forum"] = True
                self._chats.setdefault(new_id, rec)   # тип обновится при следующем апдейте/свипе
                moved = True
            if moved:
                await self._save()
        if moved:
            log.info("ownership: чат %s повышен до супергруппы %s — владение перенесено на новый id",
                     old_id, new_id)
        return moved

    # ---------- команды ----------
    async def handle_command(self, norm: dict[str, Any]) -> None:
        user = norm.get("from") or {}
        uid = user.get("id")
        chat_id = (norm.get("chat") or {}).get("id")
        text = (norm.get("text") or "").strip()
        cmd = text.split()[0].split("@")[0].lower() if text else ""
        if uid is None or chat_id is None:
            return
        if cmd in ("/start", "/help"):
            await self._reply(chat_id, HELP_TEXT, hide=False)   # приветствие — без «Скрыть»
        elif cmd == "/claim":
            async with self._lock:
                code, _exp = self._issue_code(uid)
                await self._save()
            self._wake.set()  # разбудить свипер (немедленный свип)
            log.info("ownership: выдан код пользователю %s; известных чатов для поиска: %d",
                     uid, len(self._chats))
            await self._reply(chat_id,
                f"Ваш код: {code}\n\n"
                "Быстро: отправьте этот код сообщением в группу/канал, куда меня добавили — привяжу за секунды.\n"
                "Либо впишите код в КОНЕЦ описания чата (тогда до ~минуты — из-за кэша Telegram).\n"
                "Код действует 10 минут.")
        elif cmd == "/status":
            mine = self._user_chats(uid)
            if not mine:
                await self._reply(chat_id, "У вас пока нет привязанных чатов. Команда /claim — чтобы привязать.")
            else:
                lines = ["Ваши чаты:"]
                for i, (cid, o) in enumerate(mine, 1):
                    mark = "✅ права ок" if o.get("rights_ok") else "⚠️ не хватает прав читать/писать"
                    lines.append(f"{i}. {o.get('title') or cid} — {mark}")
                lines.append("\nОтвязать: /unlink <номер> — бот выйдет из чата.")
                await self._reply(chat_id, "\n".join(lines))
        elif cmd == "/unlink":
            await self._handle_unlink(text, uid, chat_id)

    async def on_chat_message(self, norm: dict[str, Any]) -> None:
        """Мгновенная привязка: код прислан СООБЩЕНИЕМ в группу/канал (без кэша getChat)."""
        chat = norm.get("chat") or {}
        cid = str(chat.get("id"))
        thread_id = norm.get("message_thread_id")
        is_topic = chat.get("type") == "supergroup" and thread_id is not None
        text = norm.get("text") or ""
        if not text:
            return
        existing = self._owners.get(cid)
        # Уже привязан к РЕАЛЬНОМУ пользователю — не трогаем. Но «осиротевший» чат
        # (owner=None, как у каналов без отправителя) переобрабатываем, чтобы привязать
        # его к аккаунту по коду mini-app. Код в Telegram-теме создаёт отдельный
        # topic-источник, поэтому базовый owner супергруппы не блокирует обработку.
        if existing and existing.get("user_id") is not None and not is_topic:
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
                full = await self.client.call("getChat", {"chat_id": chat.get("id")})
            except (TelegramError, ValueError):
                full = {"id": chat.get("id"), "type": chat.get("type"), "title": chat.get("title")}
            if is_topic:
                full["message_thread_id"] = thread_id
                full["is_topic_message"] = True
            if isinstance(uid, dict) and uid.get("external"):
                sender = (norm.get("from") or {}).get("id")
                # Тему привязывает к аккаунту on_external_claim; здесь не выдаём весь форум
                # как отдельный источник, только запоминаем чат и права.
                await self._claim(full, sender, notify=False, claim_owner=not is_topic)
                if self.on_external_claim is not None:
                    try:
                        await self.on_external_claim(code, sender, full, uid)
                    except Exception:  # noqa: BLE001
                        log.warning("on_external_claim сбой", exc_info=True)
            else:
                await self._claim(full, uid)
            return

    async def _reply(self, chat_id: Any, text: str, *, hide: bool = True) -> None:
        """Служебное сообщение бота в личку. hide=True — inline-кнопка «Скрыть» (колбэк
        hide_msg, бот удаляет сообщение); False — только у приветствия HELP_TEXT."""
        params: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if hide:
            params["reply_markup"] = {
                "inline_keyboard": [[{"text": "Скрыть", "callback_data": "hide_msg"}]]}
        try:
            await self.client.call("sendMessage", params)
        except TelegramError as exc:
            log.warning("ownership: не отправил сообщение %s: %s", chat_id, exc.description)

    # ---------- свипер описаний ----------
    async def _sweeper_loop(self) -> None:
        try:
            while not self._stop.is_set():
                active = self._active_codes()
                if not active:
                    self._wake.clear()
                    await self._wake.wait()           # пауза: ждём выдачи кода
                    continue
                await self._sweep_once(active)         # проверяем СРАЗУ (отзывчивость)
                if self._stop.is_set():
                    break
                # до следующей отметки :00/:10/...; просыпаемся раньше при новом коде/чате
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
                continue                              # чат уже привязан
            try:
                chat = await self.client.call("getChat", {"chat_id": int(cid)})
            except (TelegramError, ValueError) as exc:
                log.debug("getChat(%s) не удался: %s", cid, exc)
                continue
            desc = (chat.get("description") or "").strip()
            m = _TRAILING_CODE.search(desc)
            if not m:
                continue
            uid = active.get(m.group(1))
            if uid and not (isinstance(uid, dict) and uid.get("external")):
                # Коды mini-app (external) — только по сообщению (нужен отправитель).
                await self._claim(chat, uid)
                active = self._active_codes()         # код израсходован

    async def _claim(self, chat: dict[str, Any], user_id: Any, *, notify: bool = True,
                     claim_owner: bool = True) -> None:
        cid = str(chat.get("id"))
        title = chat.get("title") or chat.get("username") or cid
        rights_ok = await self._compute_rights_ok(cid, chat=chat)
        self._chats[cid] = {"type": chat.get("type"), "title": title, "username": chat.get("username"),
                            "is_forum": chat.get("is_forum")}
        rec = {"user_id": user_id if claim_owner else None, "title": title, "type": chat.get("type"),
               "rights_ok": rights_ok, "claimed_at": int(time.time())}
        if claim_owner or cid not in self._owners:
            self._owners[cid] = rec
        else:
            # Topic-привязка не должна затирать владельца базовой супергруппы, если он уже есть.
            self._owners[cid].update({"title": title, "type": chat.get("type"), "rights_ok": rights_ok})
        self._pending.pop(str(user_id), None)          # код использован
        await self._save()
        if not notify or user_id is None:
            pass  # привязка из mini-app шлёт лаконичное сообщение сама; канал — без личут
        elif rights_ok:
            await self._reply(user_id, f"✅ Готово! Чат «{title}» привязан к вам.")
        else:
            await self._reply(user_id,
                f"⚠️ Нашёл код в «{title}», но мне не хватает прав читать/писать.\n"
                "Дайте боту право отправлять сообщения (и чтобы он видел сообщения чата).")
        log.info("ownership: чат %s («%s») привязан к user=%s, права=%s",
                 cid, title, user_id, "ок" if rights_ok else "недостаточно")

    async def _compute_rights_ok(self, chat_id: Any, *, member: dict[str, Any] | None = None,
                                 chat: dict[str, Any] | None = None) -> bool:
        """Может ли бот читать и писать в чате (без обязательной админки)."""
        try:
            if chat is None:
                chat = await self.client.call("getChat", {"chat_id": int(chat_id)})
            if member is None:
                if self.bot_id is None:
                    return False
                member = await self.client.call(
                    "getChatMember", {"chat_id": int(chat_id), "user_id": self.bot_id})
        except (TelegramError, ValueError) as exc:
            log.warning("ownership: проверка прав чата %s не удалась: %s", chat_id, exc)
            return False
        return _rights_ok_from(member, chat, self.bot_can_read_all)

    def _user_chats(self, uid: Any) -> list[tuple[str, dict[str, Any]]]:
        items = [(cid, o) for cid, o in self._owners.items() if str(o.get("user_id")) == str(uid)]
        items.sort(key=lambda x: (x[1].get("claimed_at", 0), x[0]))
        return items

    async def _handle_unlink(self, text: str, uid: Any, chat_id: Any) -> None:
        mine = self._user_chats(uid)
        if not mine:
            await self._reply(chat_id, "У вас нет привязанных чатов.")
            return
        parts = text.split()
        if len(parts) < 2:
            if len(mine) == 1:
                await self._unlink(mine[0][0], uid, chat_id)
            else:
                lines = ["Какой чат отвязать? Отправьте /unlink <номер>:"]
                for i, (cid, o) in enumerate(mine, 1):
                    lines.append(f"{i}. {o.get('title') or cid}")
                await self._reply(chat_id, "\n".join(lines))
            return
        try:
            idx = int(parts[1])
        except ValueError:
            idx = -1
        if 1 <= idx <= len(mine):
            await self._unlink(mine[idx - 1][0], uid, chat_id)
        else:
            await self._reply(chat_id, "Неверный номер. Отправьте /unlink, чтобы увидеть список.")

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

    async def _unlink(self, cid: str, uid: Any, reply_chat_id: Any) -> None:
        owner = self._owners.get(cid)
        if not owner or str(owner.get("user_id")) != str(uid):
            await self._reply(reply_chat_id, "Это не ваш чат или он не привязан.")
            return
        title = owner.get("title") or cid
        # Снимаем привязку ДО выхода, чтобы my_chat_member(left) не задублировал уведомление.
        self._owners.pop(cid, None)
        self._chats.pop(cid, None)
        await self._save()
        await self._notify_removed(cid, title)
        left = await self._leave_chat(cid)
        if left:
            await self._reply(reply_chat_id, f"Отвязал «{title}» и вышел из чата.")
        else:
            await self._reply(reply_chat_id,
                              f"Отвязал «{title}». Выйти из чата не удалось (возможно, меня там уже нет).")
        log.info("ownership: чат %s отвязан пользователем %s (leave=%s)", cid, uid, left)

    async def _leave_chat(self, cid: str) -> bool:
        try:
            await self.client.call("leaveChat", {"chat_id": int(cid)})
            return True
        except (TelegramError, ValueError) as exc:
            log.warning("ownership: leaveChat(%s) не удался: %s", cid, exc)
            return False

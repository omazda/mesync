"""Жалобы на пересланный контент (модерация, этап 3).

Читатель в целевом чате/канале видит под копией ссылку «Пожаловаться» — диплинк,
открывающий mini-app бота на площадке читателя на лёгком экране жалобы. Ссылка несёт
подписанный HMAC-токен координат ИСХОДНОГО сообщения (мессенджер, chat_id, mid) + rule_id,
а после отправки копии best-effort обновляется координатами видимого сообщения-копии.
Токен нельзя подделать/перебрать; он самопроверяемый (стор при компоновке подписи не
трогаем — важно для масштаба: тысячи сообщений без лишних записей).

Жалоба уходит в `POST /api/report` (валидация подписи initData жалобщика + антиспам),
пишется в стор (persist) и ставится в ОДНОПОТОЧНУЮ очередь (бережём квоту MiniMax, без
всплеска запросов; переживает рестарт — очередь наполняется из стора при старте).

Обработчик одной жалобы:
  1) перечитывает АКТУАЛЬНЫЙ текст сообщения СО СТОРОНЫ MAX, если она есть. У Telegram Bot API
     нет метода чтения сообщения по id, поэтому для Telegram-only копий используем bounded
     snapshot из message_map — текст, который бот видел при доставке/последней успешной правке.
     Нет текста (удалено/нет MAX-стороны и нет snapshot) → жалоба неактуальна;
  2) дедуп: повторная жалоба на НЕИЗМЕНЁННЫЙ, уже проверенный текст — без ИИ (учитываем
     счётчик повторов у прежней записи);
  3) классифицирует через ИИ (общий синглтон ModerationAI); при исчерпании квоты окна
     Token Plan (2056) очередь встаёт на паузу до сброса окна;
  4) violation → скрываем свои копии (message_map) + уведомляем владельца правила + карточка
     оператору; ok/unsure/unavailable → карточка оператору (по требованию «прошло проверку —
     всё равно показать»).

Богатая карточка в отдельную админ-TG-группу с inline-кнопками и автопауза по страйкам —
этап 4 (здесь карточка деградирует до сервисного лог-канала; вердикты-нарушения в сторе
служат журналом страйков для этапа 4). Гейт: вся функция за MESYNC_MODERATION_REPORTS.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import html
import logging
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Any, Awaitable, Callable

from . import config

log = logging.getLogger("control.reports")

# --- Токен жалобы (self-verifying HMAC) ---
# Диплинк startapp принимает только [A-Za-z0-9_-] (сверено docs/max и docs/telegram) —
# поэтому токен строго base64url БЕЗ разделителей-точек: тело + подпись фиксированной длины.
_SIG_BYTES = 12                               # 96-битный усечённый HMAC-тег
_TOKEN_PREFIX = "r_"                          # startapp=r_<token>; mini-app роутит по префиксу
_MSN_CODE = {"tg": "t", "max": "x"}
_MSN_DECODE = {"t": "tg", "x": "max"}
_TOKEN_V2 = "2"
_TOKEN_V3 = "3"
_TOKEN_V4 = "4"
HIDDEN_VIOLATION_TEXT = "Данное сообщение скрыто, по причине нарушения правил."

# Кэш секрета подписи: session_secret() читает файл — не делаем это на каждое сообщение.
_secret_cache: bytes | None = None


def _hmac_key() -> bytes:
    global _secret_cache
    if _secret_cache is None:
        _secret_cache = config.session_secret().encode()
    return _secret_cache


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload: bytes) -> bytes:
    # Доменное разделение "report:" — токен нельзя переиспользовать как сессию и наоборот.
    return hmac.new(_hmac_key(), b"report:" + payload, hashlib.sha256).digest()[:_SIG_BYTES]


_SIG_LEN = len(_b64url(b"\0" * _SIG_BYTES))   # 16 символов для 12 байт


def _dedup_strs(values: Any) -> list[str]:
    if values is None:
        return []
    raw = values if isinstance(values, (list, tuple)) else [values]
    out: list[str] = []
    seen: set[str] = set()
    for value in raw:
        if value is None:
            continue
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _common_prefix(values: list[str]) -> str:
    if not values:
        return ""
    prefix = values[0]
    for value in values[1:]:
        i = 0
        max_i = min(len(prefix), len(value))
        while i < max_i and prefix[i] == value[i]:
            i += 1
        prefix = prefix[:i]
        if not prefix:
            break
    return prefix


def _encode_mid_list(mids: list[str]) -> str:
    """Компактная строка copy_mid[] для v3 token.

    MAX mid у частей одного split-сообщения часто имеют длинный общий префикс. Prefix packing
    удерживает startapp-токен в разумной длине без внешнего стора.
    """
    raw = ",".join(mids)
    if len(mids) < 2:
        return raw
    prefix = _common_prefix(mids)
    if not prefix:
        return raw
    packed = prefix + "*" + ",".join(mid[len(prefix):] for mid in mids)
    return packed if len(packed) < len(raw) else raw


def _decode_mid_list(value: str) -> list[str]:
    if not value:
        return []
    if "*" in value:
        prefix, _, suffixes = value.partition("*")
        return _dedup_strs([prefix + suffix for suffix in suffixes.split(",")])
    return _dedup_strs(value.split(","))


def make_report_token(messenger: str, chat_id: Any, mid: Any, rule_id: Any, *,
                      copy_messenger: str | None = None,
                      copy_chat_id: Any = None,
                      copy_mid: Any = None,
                      copy_thread_id: Any = None,
                      copy_mids: list[Any] | tuple[Any, ...] | None = None,
                      has_media: bool = False) -> str:
    """Подписанный токен координат ИСХОДНОГО сообщения. Поля не содержат '|' (числовые id,
    mid вида mid.<hash>, rule_<hex>) — разделитель безопасен; всё тело base64url-кодируется.

    Если известен id копии, добавляем и координаты ВИДИМОГО сообщения. Это делает ссылку
    самодостаточной для ручного поиска/скрытия копии даже после потери message_map."""
    m = _MSN_CODE.get(messenger, messenger)
    if copy_mids is None:
        mids = _dedup_strs(copy_mid)
    else:
        mids = _dedup_strs([copy_mid, *list(copy_mids)] if copy_mid is not None else copy_mids)
    if has_media:
        cm = _MSN_CODE.get(copy_messenger or "", copy_messenger or "")
        payload = "|".join([
            _TOKEN_V4,
            m, str(chat_id), str(mid), str(rule_id or ""),
            cm, str(copy_chat_id or ""), _encode_mid_list(mids), str(copy_thread_id or ""),
            "1",
        ]).encode("utf-8")
    elif not mids:
        payload = "|".join([m, str(chat_id), str(mid), str(rule_id or "")]).encode("utf-8")
    elif len(mids) == 1:
        cm = _MSN_CODE.get(copy_messenger or "", copy_messenger or "")
        payload = "|".join([
            _TOKEN_V2,
            m, str(chat_id), str(mid), str(rule_id or ""),
            cm, str(copy_chat_id or ""), mids[0], str(copy_thread_id or ""),
        ]).encode("utf-8")
    else:
        cm = _MSN_CODE.get(copy_messenger or "", copy_messenger or "")
        payload = "|".join([
            _TOKEN_V3,
            m, str(chat_id), str(mid), str(rule_id or ""),
            cm, str(copy_chat_id or ""), _encode_mid_list(mids), str(copy_thread_id or ""),
        ]).encode("utf-8")
    return _b64url(payload) + _b64url(_sign(payload))


def parse_report_token(token: Any) -> dict[str, Any] | None:
    """Проверить подпись и вернуть {messenger, chat_id, mid, rule_id} или None."""
    if not token or not isinstance(token, str):
        return None
    if token.startswith(_TOKEN_PREFIX):
        token = token[len(_TOKEN_PREFIX):]
    if len(token) <= _SIG_LEN:
        return None
    body, sig = token[:-_SIG_LEN], token[-_SIG_LEN:]
    try:
        payload = _b64url_decode(body)
        expected = _b64url(_sign(payload))
    except Exception:  # noqa: BLE001 — битый base64/UTF → недействительный токен
        return None
    if not hmac.compare_digest(expected, sig):
        return None
    parts = payload.decode("utf-8", "replace").split("|")
    if len(parts) == 4:
        m, chat_id, mid, rule_id = parts
        copy = {}
    elif len(parts) == 9 and parts[0] == _TOKEN_V2:
        _, m, chat_id, mid, rule_id, cm, cchat, cmid, cthread = parts
        copy_messenger = _MSN_DECODE.get(cm)
        if copy_messenger is None or not cchat or not cmid:
            return None
        copy = {
            "copy_messenger": copy_messenger,
            "copy_chat": cchat,
            "copy_mid": cmid,
            "copy_thread": cthread or None,
        }
    elif len(parts) == 9 and parts[0] == _TOKEN_V3:
        _, m, chat_id, mid, rule_id, cm, cchat, cmids, cthread = parts
        copy_messenger = _MSN_DECODE.get(cm)
        copy_mids = _decode_mid_list(cmids)
        if copy_messenger is None or not cchat or not copy_mids:
            return None
        copy = {
            "copy_messenger": copy_messenger,
            "copy_chat": cchat,
            "copy_mid": copy_mids[0],
            "copy_mids": copy_mids,
            "copy_thread": cthread or None,
        }
    elif len(parts) == 10 and parts[0] == _TOKEN_V4:
        _, m, chat_id, mid, rule_id, cm, cchat, cmids, cthread, media = parts
        copy = {"has_media": media == "1"}
        if cm or cchat or cmids:
            copy_messenger = _MSN_DECODE.get(cm)
            copy_mids = _decode_mid_list(cmids)
            if copy_messenger is None or not cchat or not copy_mids:
                return None
            copy.update({
                "copy_messenger": copy_messenger,
                "copy_chat": cchat,
                "copy_mid": copy_mids[0],
                "copy_thread": cthread or None,
            })
            if len(copy_mids) > 1:
                copy["copy_mids"] = copy_mids
    else:
        return None
    messenger = _MSN_DECODE.get(m)
    if messenger is None or not chat_id or not mid:
        return None
    return {"messenger": messenger, "chat_id": chat_id, "mid": mid,
            "rule_id": rule_id or None, **copy}


def report_deeplink(target_messenger: str, token: str) -> str | None:
    """Диплинк, открывающий mini-app бота НА ПЛОЩАДКЕ ЧИТАТЕЛЯ на экране жалобы.
    Площадка = мессенджер копии (там, где читатель видит сообщение)."""
    base_url = config.BOT_URLS.get(target_messenger)
    if not base_url:
        return None
    param = _TOKEN_PREFIX + token
    try:
        parts = urlsplit(base_url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["startapp"] = param
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
    except ValueError:
        return None


class ReportError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


REPORT_BOT_LEFT_MESSAGE = (
    "Бот больше не обслуживает эту группу. Чтобы подать жалобу, обратитесь к администратору."
)


class _ResolvedTextParts:
    """Collect text from all known copies of one source message.

    ``found`` tracks known textless messages separately from missing/unreadable ones, so
    media-only content can still produce a precise "no text" reason.
    """

    def __init__(self) -> None:
        self.found = False
        self.parts: list[str] = []
        self._seen: set[str] = set()

    def add(self, text: Any) -> None:
        if text is None:
            return
        self.found = True
        value = str(text)
        if not value.strip():
            return
        key = value.strip()
        if key in self._seen:
            return
        self._seen.add(key)
        self.parts.append(value)

    def result(self) -> str | None:
        if self.parts:
            return "\n\n".join(self.parts)
        return "" if self.found else None


class _StaticVerdict:
    def __init__(self, category: str, reason: str) -> None:
        self.category = category
        self.reason = reason


class Reports:
    """Приём и однопоточная обработка жалоб. I/O-зависимости — колбэками (тестируемо):
      fetch_text(messenger, chat_id, mid) -> str|None — перечитать текст сообщения;
      hide_copy(messenger, chat_id, mid) -> bool       — скрыть свою копию;
      delete_copy(messenger, chat_id, mid) -> bool     — legacy alias для hide_copy;
      notify_owner(account_id, category, reason)       — уведомить владельца правила.
      chat_member_ok(messenger, chat_id) -> bool|None  — бот всё ещё обслуживает чат.
      source_admin_ok(messenger, chat_id, user_id) -> bool — жалобщик админ источника.
    message_map — объект с .lookup(); moderation — ModerationAI (или None); service_log —
    ServiceLog (или None)."""

    def __init__(self, store: Any, *,
                 moderation: Any = None,
                 message_map: Any = None,
                 fetch_text: Callable[..., Awaitable[Any]] | None = None,
                 delete_copy: Callable[..., Awaitable[Any]] | None = None,
                 hide_copy: Callable[..., Awaitable[Any]] | None = None,
                 notify_owner: Callable[..., Awaitable[Any]] | None = None,
                 chat_member_ok: Callable[..., Awaitable[Any]] | None = None,
                 source_admin_ok: Callable[..., Awaitable[Any]] | None = None,
                 service_log: Any = None,
                 settings: Any = None,
                 stoplist: Any = None,
                 hold_cb: Callable[..., Awaitable[Any]] | None = None,
                 clock: Callable[[], float] = time.time,
                 report_max: int | None = None,
                 report_window: int | None = None,
                 quota_cooldown: float | None = None) -> None:
        self.store = store
        self._moderation = moderation
        self._message_map = message_map
        self._fetch_text = fetch_text
        self._hide_copy = hide_copy or delete_copy
        self._notify_owner = notify_owner
        self._chat_member_ok = chat_member_ok
        self._source_admin_ok = source_admin_ok
        self._service_log = service_log
        # settings — порог автопаузы; stoplist — для classify-test; hold_cb — уведомление
        # владельца при автопаузе правила (модерация, этап 4.2).
        self._settings = settings
        self._stoplist = stoplist
        self._hold_cb = hold_cb
        self.clock = clock
        self._report_max = report_max if report_max is not None else config.MODERATION_REPORT_MAX
        self._report_window = (report_window if report_window is not None
                               else config.MODERATION_REPORT_WINDOW)
        self._quota_cooldown = (quota_cooldown if quota_cooldown is not None
                                else config.MODERATION_QUOTA_COOLDOWN)
        self._attempts: dict[str, list[float]] = {}   # reporter -> метки обращений (антиспам)
        self._queue: "asyncio.Queue[str]" = asyncio.Queue()
        self._enqueued: set[str] = set()              # защита от двойной постановки id
        # ops-счётчики (этап 4.5): in-memory, сбрасываются при рестарте («с момента запуска»).
        self._processed_total = 0
        self._error_total = 0
        self._last_processed_ts: float | None = None
        self._paused_until: float | None = None
        self._inflight = False

    def _ai_enabled(self) -> bool:
        """Runtime-флаг ИИ-классификации из settings-store плюс фактическая доступность AI."""
        if self._settings is not None:
            try:
                if not bool(self._settings.get("moderation_ai_enabled")):
                    return False
            except Exception:  # noqa: BLE001
                pass
        return self._moderation is not None and getattr(self._moderation, "enabled", False)

    # ---------- приём (вызывается из API-обработчика) ----------
    _ATTEMPTS_SWEEP_AT = 1024   # чистим протухшие ключи, когда словарь разросся

    async def check(self, token: Any) -> dict[str, Any]:
        """Лёгкая preflight-проверка для экрана жалобы до ввода текста."""
        parsed = parse_report_token(token)
        if parsed is None:
            raise ReportError(400, "bad_token", "Ссылка жалобы недействительна или устарела.")
        if not await self._ensure_target_chat_active(parsed):
            raise ReportError(410, "bot_not_in_chat", REPORT_BOT_LEFT_MESSAGE)
        return {"ok": True}

    async def _ensure_target_chat_active(self, parsed: dict[str, Any]) -> bool:
        """Проверить чат, где читатель видит копию. Для старых source-only ссылок координат
        копии нет; тогда проверяем только Telegram-источник, если он известен, иначе не
        блокируем жалобу."""
        if self._chat_member_ok is None:
            return True
        messenger = parsed.get("copy_messenger")
        chat_id = parsed.get("copy_chat")
        if not messenger or not chat_id:
            messenger = parsed.get("messenger")
            chat_id = parsed.get("chat_id")
        if messenger != "tg" or not chat_id:
            return True
        try:
            res = await self._chat_member_ok(messenger, chat_id)
        except Exception:  # noqa: BLE001
            log.warning("жалоба: не проверить членство бота в %s:%s", messenger, chat_id,
                        exc_info=True)
            return True
        return res is not False

    @staticmethod
    def _reporter_identity(reporter: Any) -> tuple[str | None, str | None]:
        messenger, sep, user_id = str(reporter or "").partition(":")
        if not sep or messenger not in ("tg", "max") or not user_id:
            return None, None
        return messenger, user_id

    async def _is_source_admin_reporter(self, parsed: dict[str, Any],
                                        reporter: str) -> bool:
        """True only when the reporter is an admin of the source in the same messenger.

        Cross-messenger identity is not reliable here: a TG admin clicking a MAX copy has a MAX
        user_id, not the TG user_id. In that case the report stays on the normal moderation path.
        """
        if self._source_admin_ok is None:
            return False
        reporter_messenger, user_id = self._reporter_identity(reporter)
        if reporter_messenger is None or reporter_messenger != parsed.get("messenger"):
            return False
        try:
            return bool(await self._source_admin_ok(
                parsed["messenger"], parsed["chat_id"], user_id))
        except Exception:  # noqa: BLE001 — не доказали админство → обычная жалоба
            log.warning("жалоба: не проверить админа источника %s:%s user=%s",
                        parsed.get("messenger"), parsed.get("chat_id"), user_id,
                        exc_info=True)
            return False

    @staticmethod
    def _copy_mids_from_record(rec: dict[str, Any]) -> list[str]:
        mids = _dedup_strs(rec.get("copy_mids"))
        copy_mid = rec.get("copy_mid")
        if copy_mid is not None:
            mids = _dedup_strs([copy_mid, *mids])
        return mids

    @classmethod
    def _copy_targets_from_record(cls, rec: dict[str, Any]) -> list[tuple[Any, Any, str]]:
        messenger = rec.get("copy_messenger")
        chat_id = rec.get("copy_chat")
        if not messenger or not chat_id:
            return []
        return [(messenger, chat_id, mid) for mid in cls._copy_mids_from_record(rec)]

    @staticmethod
    def _review_patch(reason: str, *, has_media: bool = False) -> dict[str, Any]:
        patch: dict[str, Any] = {
            "review_required": True,
            "reviewed": False,
            "review_reason": reason,
        }
        if has_media:
            patch["has_media"] = True
        return patch

    def _register_attempt(self, reporter: str) -> None:
        now = self.clock()
        # Долгоживущий процесс: без чистки словарь копил бы по записи на каждого жалобщика
        # навсегда. Периодически (когда разросся) выметаем ключи, у которых все метки протухли.
        if len(self._attempts) > self._ATTEMPTS_SWEEP_AT:
            self._attempts = {k: v for k, v in self._attempts.items()
                              if any(now - t < self._report_window for t in v)}
        recent = [t for t in self._attempts.get(reporter, ()) if now - t < self._report_window]
        if len(recent) >= self._report_max:
            self._attempts[reporter] = recent
            wait_min = max(1, int((self._report_window - (now - recent[0])) // 60) + 1)
            raise ReportError(429, "too_many_reports",
                              f"Слишком много жалоб. Попробуйте через {wait_min} мин.")
        recent.append(now)
        self._attempts[reporter] = recent

    async def submit(self, token: Any, description: Any, *, reporter: str) -> dict[str, Any]:
        """Антиспам → проверка токена → запись в стор + очередь. Быстро возвращает {'ok': True}.
        Тяжёлая работа (перечитать текст, ИИ, скрытие) — в фоновом воркере."""
        self._register_attempt(reporter)
        parsed = parse_report_token(token)
        if parsed is None:
            raise ReportError(400, "bad_token", "Ссылка жалобы недействительна или устарела.")
        if not await self._ensure_target_chat_active(parsed):
            raise ReportError(410, "bot_not_in_chat", REPORT_BOT_LEFT_MESSAGE)
        rule_id = parsed.get("rule_id")
        rule = self.store.rule(rule_id) if rule_id else None
        if rule and rule.get("report_muted"):
            return {"ok": True}   # жалобы по этому правилу заглушены админом — тихо принимаем
        account_id = (rule or {}).get("account_id")
        desc = str(description or "").strip()[:config.MODERATION_REPORT_MAX_DESC]
        src_key = f"{parsed['messenger']}:{parsed['chat_id']}:{parsed['mid']}"
        source_admin_report = await self._is_source_admin_reporter(parsed, reporter)
        record = {
            "src_messenger": parsed["messenger"], "src_chat": parsed["chat_id"],
            "src_mid": parsed["mid"], "src_key": src_key, "rule_id": rule_id,
            "account_id": account_id, "reporter": reporter, "description": desc,
            "status": "queued",
        }
        if source_admin_report:
            record["source_admin_report"] = True
        if parsed.get("copy_mid"):
            copy_mids = _dedup_strs([parsed.get("copy_mid"), *(
                parsed.get("copy_mids") if isinstance(parsed.get("copy_mids"), list) else []
            )])
            record.update({
                "copy_messenger": parsed.get("copy_messenger"),
                "copy_chat": parsed.get("copy_chat"),
                "copy_mid": parsed.get("copy_mid"),
                "copy_thread": parsed.get("copy_thread"),
            })
            if len(copy_mids) > 1:
                record["copy_mids"] = copy_mids
        if parsed.get("has_media"):
            record["has_media"] = True
        rec = await self.store.add_report(record)
        if source_admin_report:
            reason = "жалоба администратора источника: сообщение скрыто без ИИ-проверки"
            patch = {
                "status": "done", "verdict": "violation", "category": "source_admin",
                "reason": reason, "reviewed": True, "source_admin_report": True,
            }
            await self.store.update_report(rec["id"], patch)
            rec = {**rec, **patch}
            hidden = await self._hide_all_copies(rec)
            verdict = _StaticVerdict("source_admin", reason)
            await self._notify(rec, verdict)
            await self._service_card(rec, verdict="violation", reason=reason,
                                     category="source_admin", text="", hidden=hidden)
            await self._maybe_autopause(rec)
            log.info("жалоба %s авто-блокирована админом источника (src=%s rule=%s)",
                     rec["id"], src_key, rule_id)
            return {"ok": True, "id": rec["id"], "auto_blocked": True}
        self._enqueue(rec["id"])
        log.info("жалоба %s принята (src=%s rule=%s)", rec["id"], src_key, rule_id)
        return {"ok": True, "id": rec["id"]}

    def _enqueue(self, report_id: str) -> None:
        if report_id in self._enqueued:
            return
        self._enqueued.add(report_id)
        self._queue.put_nowait(report_id)

    def load_pending(self) -> int:
        """Наполнить очередь жалобами, оставшимися в статусе queued (переживает рестарт)."""
        ids = self.store.queued_report_ids()
        for rid in ids:
            self._enqueue(rid)
        if ids:
            log.info("жалобы: восстановлено из стора в очередь: %d", len(ids))
        return len(ids)

    # ---------- воркер ----------
    async def run(self) -> None:
        """Однопоточный обработчик: по одной жалобе за раз (бережём квоту, без всплеска)."""
        log.info("жалобы: воркер очереди запущен")
        while True:
            report_id = await self._queue.get()
            self._enqueued.discard(report_id)
            self._inflight = True
            try:
                if await self._process(report_id) != "paused":
                    # quota-пауза (жалоба возвращена в очередь) не считается обработкой.
                    self._processed_total += 1
                    self._last_processed_ts = self.clock()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 — одна жалоба не должна ронять воркер
                self._error_total += 1
                log.warning("жалоба %s: сбой обработки", report_id, exc_info=True)
                try:
                    await self.store.update_report(report_id, {"status": "error"})
                except Exception:  # noqa: BLE001
                    pass
            finally:
                self._inflight = False
                self._queue.task_done()

    def stats(self) -> dict[str, Any]:
        """Состояние очереди жалоб для ops-обзора (этап 4.5). Всё in-process / O(1)."""
        now = self.clock()
        return {
            "running": True,
            "depth": self._queue.qsize(),                               # в памяти
            "persistedDepth": len(self.store.queued_report_ids()),      # переживает рестарт
            "inflight": self._inflight,
            "processedTotal": self._processed_total,                    # с момента запуска
            "errorTotal": self._error_total,
            "lastProcessedTs": self._last_processed_ts,
            "paused": self._paused_until is not None and self._paused_until > now,
            "pausedUntil": self._paused_until,
        }

    async def _process(self, report_id: str) -> str | None:
        rec = self.store.report(report_id)
        if rec is None or rec.get("status") == "done":
            return  # уже обработана (идемпотентность при рестарте/повторной постановке)
        src_key = rec.get("src_key") or f"{rec['src_messenger']}:{rec['src_chat']}:{rec['src_mid']}"
        has_media = bool(rec.get("has_media"))

        # 1) Актуальный текст — MAX, если можно перечитать; иначе snapshot для TG-only.
        text = await self._resolve_text(rec)
        if text is None:
            if has_media:
                reason = "есть медиа-вложения; текст недоступен для ИИ"
                patch = {
                    "status": "done", "verdict": "unsure", "category": "other",
                    "reason": reason, **self._review_patch(reason, has_media=True)}
                await self.store.update_report(report_id, patch)
                rec = {**rec, **patch}
                await self._service_card(rec, verdict="unsure", reason=reason,
                                         category="other", text="")
                return
            await self.store.update_report(report_id, {
                "status": "done", "verdict": "unavailable", "reason": "сообщение недоступно"})
            await self._service_card(rec, verdict="unavailable",
                                     reason="сообщение недоступно (удалено или нет MAX-стороны)",
                                     category="", text="")
            return
        if not str(text).strip():
            reason = "в сообщении нет текста для ИИ-модерации; нужна ручная проверка"
            patch = {
                "status": "done", "verdict": "unsure", "category": "other",
                "reason": reason, **self._review_patch(reason, has_media=True)}
            await self.store.update_report(report_id, patch)
            rec = {**rec, **patch}
            await self._service_card(rec, verdict="unsure", reason=reason,
                                     category="other", text="")
            return
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        # 2) Дедуп: повтор на уже проверенный неизменённый текст — без ИИ.
        prior = self.store.find_processed_report(src_key, text_hash)
        if prior is not None and prior.get("id") != report_id:
            n = await self.store.bump_report_repeat(prior["id"])
            repeat_patch = {
                "status": "done", "text_hash": text_hash, "verdict": prior.get("verdict"),
                "category": prior.get("category"), "reason": prior.get("reason"),
                "repeat_of": prior["id"]}
            for key in ("review_required", "review_reason", "has_media", "reviewed"):
                if key in prior:
                    repeat_patch[key] = prior.get(key)
            await self.store.update_report(report_id, repeat_patch)
            rec = {**rec, **repeat_patch}
            await self._service_card(rec, verdict=prior.get("verdict"), reason=prior.get("reason"),
                                     category=prior.get("category"), text=text, repeat=n)
            return

        # 3) Классификация.
        if not self._ai_enabled():
            await self.store.update_report(report_id, {
                "status": "done", "text_hash": text_hash, "verdict": "unsure",
                "reason": "ИИ-модерация недоступна"})
            await self._service_card(rec, verdict="unsure", reason="ИИ-модерация недоступна",
                                     category="", text=text)
            return
        verdict = await self._moderation.classify(text)
        if getattr(verdict, "quota_exhausted", False):
            # Квота окна Token Plan исчерпана → пауза воркера, жалоба остаётся queued.
            self._enqueue(report_id)
            self._paused_until = self.clock() + self._quota_cooldown
            log.info("жалобы: квота ИИ исчерпана — пауза очереди на %sс", self._quota_cooldown)
            try:
                await self.store.add_event(kind="quota_pause",
                                           title="Пауза очереди жалоб: квота ИИ исчерпана",
                                           detail={"cooldownSec": self._quota_cooldown})
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(self._quota_cooldown)
            self._paused_until = None
            return "paused"

        # 4) Решение по вердикту.
        final_verdict = verdict.verdict
        final_category = verdict.category
        final_reason = verdict.reason
        review_patch: dict[str, Any] = {}
        if final_verdict == "unsure":
            final_reason = final_reason or "ИИ не уверен, нужна ручная проверка"
            review_patch = self._review_patch(final_reason, has_media=has_media)
        elif has_media and final_verdict == "ok":
            final_verdict = "unsure"
            final_category = "other"
            final_reason = "текст не нарушает, но есть медиа-вложения"
            review_patch = self._review_patch(final_reason, has_media=True)
        elif has_media and final_verdict == "unavailable":
            final_verdict = "unsure"
            final_category = "other"
            final_reason = "есть медиа-вложения; ИИ недоступен для проверки текста"
            review_patch = self._review_patch(final_reason, has_media=True)
        elif has_media and final_verdict == "violation":
            review_patch = self._review_patch("нарушение в тексте и есть медиа-вложения",
                                              has_media=True)
        patch = {
            "status": "done", "text_hash": text_hash, "verdict": final_verdict,
            "category": final_category, "reason": final_reason, **review_patch}
        await self.store.update_report(report_id, patch)
        rec = {**rec, **patch}
        if verdict.is_violation:
            hidden = await self._hide_all_copies(rec)
            await self._notify(rec, verdict)
            await self._service_card(rec, verdict="violation", reason=final_reason,
                                     category=final_category, text=text, hidden=hidden)
            await self._maybe_autopause(rec)
        else:
            await self._service_card(rec, verdict=final_verdict, reason=final_reason,
                                     category=final_category, text=text)

    async def _resolve_text(self, rec: dict[str, Any]) -> str | None:
        """Текст жалуемой копии.

        MAX можно перечитать по id. Telegram — нельзя, поэтому для TG-only правил используем
        текстовый снимок, записанный в message_map при доставке/успешной правке. Если одно
        исходное сообщение разложено на несколько copy-сообщений, собираем текст всех
        доступных частей по source->targets mapping.
        """
        messenger = rec["src_messenger"]
        chat_id = rec["src_chat"]
        mid = rec["src_mid"]
        if self._fetch_text is not None and messenger == "max":
            text = await self._fetch_text("max", chat_id, mid)
            if text is not None:
                return text

        parts = _ResolvedTextParts()
        fetched: set[tuple[str, str, str]] = set()

        async def add_fetched(fetch_messenger: str, fetch_chat: Any, fetch_mid: Any) -> None:
            if self._fetch_text is None or fetch_chat is None or fetch_mid is None:
                return
            key = (str(fetch_messenger), str(fetch_chat), str(fetch_mid))
            if key in fetched:
                return
            fetched.add(key)
            parts.add(await self._fetch_text(fetch_messenger, fetch_chat, fetch_mid))

        # Источник TG читать через Bot API по id нельзя; если есть MAX-копии, перечитываем
        # каждую часть одного source-сообщения, а не только первую попавшуюся.
        if self._fetch_text is not None and self._message_map is not None:
            for tgt in self._message_map.lookup(messenger, chat_id, mid):
                tgt_m, tgt_chat, tgt_mid = tgt
                if tgt_m == "max":
                    await add_fetched("max", tgt_chat, tgt_mid)
        # Если message_map потерян/истёк, но ссылка уже была обновлена после отправки,
        # в токене есть координаты видимой копии. Текст можно перечитать только у MAX.
        if self._fetch_text is not None:
            for copy_m, copy_chat, copy_mid in self._copy_targets_from_record(rec):
                if copy_m == "max":
                    await add_fetched("max", copy_chat, copy_mid)
        if self._message_map is not None:
            text_getter = getattr(self._message_map, "text_snapshot", None)
            if callable(text_getter):
                parts.add(text_getter(messenger, chat_id, mid))
                for copy_m, copy_chat, copy_mid in self._copy_targets_from_record(rec):
                    parts.add(text_getter(copy_m, copy_chat, copy_mid))
        if parts.parts:
            return parts.result()
        # Последний fallback для старых TG-only копий: локальный normalized content log, если
        # бот видел исходный update до появления snapshot в message_map. Это НЕ Telegram API read.
        if self._fetch_text is not None and messenger == "tg":
            parts.add(await self._fetch_text("tg", chat_id, mid))
        return parts.result()

    async def _hide_all_copies(self, rec: dict[str, Any]) -> int:
        """Скрыть свои копии этого источника (запрещённый контент — везде). Возвращает число."""
        if self._hide_copy is None:
            return 0
        targets: list[tuple[Any, Any, Any]] = []
        if self._message_map is not None:
            targets.extend(self._message_map.lookup(rec["src_messenger"], rec["src_chat"],
                                                    rec["src_mid"]))
        for copy in self._copy_targets_from_record(rec):
            if all(copy) and copy not in targets:
                targets.append(copy)
        n = 0
        seen: set[tuple[str, str, str]] = set()
        for tgt in targets:
            tgt_m, tgt_chat, tgt_mid = tgt
            key = (str(tgt_m), str(tgt_chat), str(tgt_mid))
            if key in seen:
                continue
            seen.add(key)
            try:
                if await self._hide_copy(tgt_m, tgt_chat, tgt_mid):
                    n += 1
            except Exception:  # noqa: BLE001
                log.warning("жалоба: не скрыть копию %s:%s:%s", tgt_m, tgt_chat, tgt_mid,
                            exc_info=True)
        return n

    async def _notify(self, rec: dict[str, Any], verdict: Any) -> None:
        account_id = rec.get("account_id")
        if not account_id or self._notify_owner is None:
            return
        try:
            await self._notify_owner(account_id, verdict.category, verdict.reason)
        except Exception:  # noqa: BLE001
            log.warning("жалоба %s: уведомление владельцу не удалось", rec.get("id"), exc_info=True)

    async def _service_card(self, rec: dict[str, Any], *, verdict: Any, reason: Any,
                            category: Any, text: str, hidden: int = 0, repeat: int = 0) -> None:
        """Карточка жалобы оператору (сервисный лог-канал; этап 4 заменит богатой карточкой с
        кнопками в отдельной админ-группе). Динамику в lines экранируем сами (ServiceLog.report
        экранирует только title/quote/error)."""
        svc = self._service_log
        if svc is None or not getattr(svc, "enabled", False):
            return
        def esc(v: Any) -> str:
            return html.escape(str(v)) if v not in (None, "") else "—"
        lines = [
            f"Вердикт: <b>{esc(verdict)}</b>"
            + (f" · категория: {esc(category)}" if verdict == "violation" else ""),
            f"{'Причина' if rec.get('source_admin_report') else 'Причина ИИ'}: {esc(reason)}",
            f"Источник: {esc(rec.get('src_messenger'))} chat={esc(rec.get('src_chat'))}"
            f" mid={esc(rec.get('src_mid'))}",
            f"Правило: {esc(rec.get('rule_id'))} · аккаунт: {esc(rec.get('account_id'))}",
            f"Жалобщик: {esc(rec.get('reporter'))}",
        ]
        if rec.get("copy_mid"):
            copy_mids = self._copy_mids_from_record(rec)
            mid_label = rec.get("copy_mid")
            if len(copy_mids) > 1:
                mid_label = "[" + ", ".join(copy_mids) + "]"
            lines.append(
                f"Копия: {esc(rec.get('copy_messenger'))} chat={esc(rec.get('copy_chat'))}"
                f" mid={esc(mid_label)}"
                + (f" thread={esc(rec.get('copy_thread'))}" if rec.get("copy_thread") else "")
            )
        if rec.get("has_media"):
            lines.append("Медиа: <b>есть вложения/альбом</b>")
        if rec.get("review_required"):
            lines.append(f"Ручная проверка: {esc(rec.get('review_reason') or 'нужна проверка')}")
        if rec.get("description"):
            lines.append(f"Текст жалобы: {esc(rec.get('description'))}")
        if verdict == "violation":
            lines.append(f"Скрыто копий: {hidden}")
        if repeat:
            lines.append(f"Повторная жалоба №{repeat} (контент уже проверялся)")
        try:
            await svc.report("🚩 Жалоба на контент", lines, quote=str(text or "")[:400])
        except Exception:  # noqa: BLE001
            log.warning("жалоба: карточка в сервисный канал не удалась", exc_info=True)

    async def _maybe_autopause(self, rec: dict[str, Any]) -> None:
        """Автопауза правила по страйкам: N подтверждённых нарушений (уникальных сообщений)
        за 24 ч → moderation_hold + аудит + уведомление владельца (модерация, этап 4.2)."""
        rule_id = rec.get("rule_id")
        if not rule_id:
            return
        threshold = 3
        if self._settings is not None:
            try:
                threshold = int(self._settings.get("moderation_autopause_strikes"))
            except Exception:  # noqa: BLE001
                pass
        since = int(self.clock()) - 24 * 3600
        count = self.store.count_rule_violations_since(rule_id, since)
        if count < threshold:
            return
        rule = self.store.rule(rule_id)
        if rule is None or rule.get("moderation_hold"):
            return  # правила нет или уже на паузе
        await self.store.update_rule(rule_id, {"moderation_hold": True})
        try:
            await self.store.add_audit(action="auto_pause", target=rule_id,
                                       details={"violations_24h": count, "threshold": threshold},
                                       ip="auto")
        except Exception:  # noqa: BLE001
            pass
        log.info("модерация: правило %s на автопаузе (%d нарушений/24ч ≥ %d)",
                 rule_id, count, threshold)
        if self._hold_cb is not None:
            try:
                await self._hold_cb(rule_id, rec.get("account_id"), count)
            except Exception:  # noqa: BLE001
                log.warning("автопауза: уведомление владельца не удалось", exc_info=True)

    # ---------- операции админ-панели (этап 4.2) ----------
    async def classify_test(self, text: Any) -> dict[str, Any]:
        """Тест-классификатор для панели: стоп-хиты + вердикт ИИ по произвольному тексту."""
        text = str(text or "")
        hits = sorted(self._stoplist.match(text)) if self._stoplist is not None else []
        verdict = None
        if self._ai_enabled() and text.strip():
            v = await self._moderation.classify(text)
            verdict = {"verdict": v.verdict, "category": v.category, "reason": v.reason,
                       "confidence": v.confidence, "quota_exhausted": v.quota_exhausted}
        return {"hits": hits, "verdict": verdict}

    async def admin_delete_copies(self, report_id: str) -> int:
        """Скрыть свои копии сообщения по жалобе (ручное действие оператора).

        Имя метода legacy: внешний action `delete_copies` сохранён для совместимости.
        """
        rec = self.store.report(report_id)
        if rec is None:
            return 0
        n = await self._hide_all_copies(rec)
        await self.store.update_report(report_id, {"copies_hidden": n})
        return n

    async def admin_reclassify(self, report_id: str) -> dict[str, Any] | None:
        """Перечитать текст и переклассифицировать жалобу (ручное действие оператора)."""
        rec = self.store.report(report_id)
        if rec is None:
            return None
        text = await self._resolve_text(rec)
        if text is None:
            await self.store.update_report(report_id, {
                "verdict": "unavailable", "reason": "сообщение недоступно"})
            return {"verdict": "unavailable"}
        if not self._ai_enabled():
            return {"verdict": "unsure", "reason": "ИИ-модерация недоступна"}
        v = await self._moderation.classify(text)
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        await self.store.update_report(report_id, {
            "status": "done", "text_hash": text_hash, "verdict": v.verdict,
            "category": v.category, "reason": v.reason})
        return {"verdict": v.verdict, "category": v.category, "reason": v.reason}

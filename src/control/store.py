"""Персистентное хранилище control-API (PostgreSQL/JSON, async I/O, общий lock).

В Docker основное состояние хранится одним JSONB-документом в PostgreSQL. Такая схема
сохраняет существующий API стора и атомарность полного снимка без рискованной миграции
десятков связанных сущностей. При первом подключении к пустой БД начальным снимком
становится существующий ``control.json``. Без настроенного PostgreSQL остаётся прежний
файловый backend.

Таблицы:
- accounts:      account_id -> {id, phone, created_at, rules_seq, profiles?,
                 legal_acceptance?, legal_history?}
                 (rules_seq — монотонный счётчик порядковых номеров правил аккаунта;
                  legal_acceptance/legal_history — текущий и исторический акцепт оферты)
- identities:    "max:<uid>"|"tg:<uid>" -> account_id
- rules:         rule_id -> {id, account_id, number, a, b, dir, sign_ab, sign_ba, status, created_at}
                 (number — порядковый номер у пользователя, присваивается при создании (+1);
                  sign_ab — подпись A→B, sign_ba — B→A; старые правила хранят единое signature)
                 a/b = {messenger, chat_id[, thread_id]} для Telegram-тем
- traffic:       account_id -> {used_bytes, topup_bytes, period_start}
                 (used_bytes — расход текущего месячного периода; topup_bytes —
                  бессрочный остаток добавочного трафика, который тратится только
                  на байты сверх месячного лимита)
- subscriptions: account_id -> {status, plan, renew_at, created_at}
- notifications: notif_id -> {id, account_id, type, title, subtitle, ts, read, link}
- source_meta:   "<messenger>:<chat_id>[:thread_id]" -> {tone, title?, title_ts?, icon_url?, photo_id?}
- pending_codes: code -> {account_id, messenger, expires_at, bound[]}
- otp:           phone -> {code, expires_at, attempts, sent_at}
- activation_codes: "XXXX-XXXX-XXXX" -> {created_at, expires_at, used_by, used_at, revoked_at?}
                 (одноразовые коды активации подписки на месяц, срок ввода 30 дней)
- registration_leads: "messenger:user_id" -> {messenger, user_id, chat_id, first_seen_at,
                 last_seen_at, payload_history[], reminders_sent[], stage, account_id?}
                 (переходы по bot deep link; без номера телефона — телефон живёт
                  только в accounts после платформенного подтверждения)
- market_orders: "<campaign_id>:<order_id>" -> состояние автоматической выдачи
                 цифровых кодов Яндекс Маркета (персистентная идемпотентная очередь)
- reports:        report_id -> {id, src_messenger, src_chat, src_mid, src_key, rule_id,
                 account_id, reporter, description, ts, status, text_hash, verdict,
                 category, reason, repeat_count, repeat_of,
                 copy_messenger?, copy_chat?, copy_mid?, copy_thread?}
                 (жалобы на пересланный контент; однопоточная очередь, см. control.reports)

Идентификаторы источников в API: "<messenger>:<chat_id>" для обычных чатов/каналов,
"tg:<chat_id>:<message_thread_id>" для темы Telegram-форума.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import secrets
import time
from pathlib import Path
from typing import Any

from . import config, tariffs
from .source_ids import endpoint_source_id, make_source_id, parse_source_id

_TABLES = ("accounts", "identities", "rules", "traffic", "subscriptions",
           "notifications", "source_meta", "pending_codes", "otp", "account_sources",
           "activation_codes", "registration_leads", "market_orders", "reports",
           "settings", "admin_audit", "events", "broadcasts")

# Код можно ввести в течение 30 суток с генерации. Сама активированная подписка
# по-прежнему длится календарный месяц (это отдельный срок в control.activation).
ACTIVATION_CODE_TTL = 30 * 86400
BACKUP_MAX_BYTES = 50 * 1024 * 1024

_RESTORE_FORMAT = "mesync-control-restore-v1"

log = logging.getLogger("control.store")

_CREATE_STATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mesync_control_state (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
_INSERT_INITIAL_STATE_SQL = """
INSERT INTO mesync_control_state (id, payload)
VALUES (1, $1::jsonb)
ON CONFLICT (id) DO NOTHING
RETURNING id
"""
_SELECT_STATE_SQL = "SELECT payload FROM mesync_control_state WHERE id = 1"
_UPSERT_STATE_SQL = """
INSERT INTO mesync_control_state (id, payload, updated_at)
VALUES (1, $1::jsonb, NOW())
ON CONFLICT (id) DO UPDATE
SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at
"""


async def _create_postgres_pool(**options: Any) -> Any:
    """Ленивый импорт оставляет файловый запуск независимым от инициализации драйвера."""
    import asyncpg

    return await asyncpg.create_pool(min_size=1, max_size=4, command_timeout=30, **options)


def _now() -> int:
    return int(time.time())


def _empty_state() -> dict[str, dict[str, Any]]:
    return {table: {} for table in _TABLES}


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"В JSON повторяется ключ {key[:80]!r}.")
        obj[key] = value
    return obj


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Недопустимое JSON-значение {value}.")


def _decode_json_bytes(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8-sig")
        return json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Файл не является корректным UTF-8 JSON.") from exc


def _validate_backup_data(data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(data, dict):
        raise ValueError("Корень резервной копии должен быть JSON-объектом.")
    missing = sorted(set(_TABLES) - set(data))
    unknown = sorted(set(data) - set(_TABLES))
    if missing:
        raise ValueError(f"В резервной копии отсутствуют таблицы: {', '.join(missing)}.")
    if unknown:
        raise ValueError(f"Резервная копия содержит неизвестные таблицы: {', '.join(unknown)}.")
    for table_name in _TABLES:
        if not isinstance(data[table_name], dict):
            raise ValueError(f"Таблица {table_name!r} должна быть JSON-объектом.")
    return data


def _state_bytes(data: dict[str, dict[str, Any]], *, pretty: bool) -> bytes:
    text = json.dumps(
        data,
        ensure_ascii=False,
        allow_nan=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )
    return (text + "\n").encode("utf-8")


def _backup_summary(data: dict[str, dict[str, Any]], raw: bytes) -> dict[str, Any]:
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "tables": len(_TABLES),
        "counts": {table: len(data[table]) for table in _TABLES},
    }


def _has_restore_marker(data: Any, restore_id: str) -> bool:
    if not isinstance(data, dict):
        return False
    audit = data.get("admin_audit")
    return isinstance(audit, dict) and any(
        isinstance(record, dict)
        and record.get("action") == "database:restore"
        and record.get("target") == restore_id
        for record in audit.values()
    )


class ControlStore:
    def __init__(self, path: Path | None = None, *, database_url: str | None = None) -> None:
        explicit_path = path is not None
        self.path = Path(path or config.STATE_FILE)
        self.restore_pending_path = self.path.with_name(f"{self.path.stem}.restore.pending.json")
        self.restore_previous_path = self.path.with_name(f"{self.path.stem}.restore.previous.json")
        self._lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        # Все операции, где подтверждённый телефон может связать/слить две identity,
        # сериализуем отдельно. Это не даёт двум одновременным contact/OTP-запросам
        # создать два аккаунта с одним номером между отдельными сохранениями JSON.
        self._phone_lock = asyncio.Lock()
        self._data: dict[str, dict[str, Any]] = {t: {} for t in _TABLES}
        self._pool: Any | None = None
        self._started = False
        self._file_loaded = False
        self._file_load_error: Exception | None = None
        self._postgres_options: dict[str, Any] | None = None
        if database_url is not None:
            if database_url.strip():
                self._postgres_options = {"dsn": database_url.strip()}
        elif not explicit_path:
            if config.DATABASE_URL:
                self._postgres_options = {"dsn": config.DATABASE_URL}
            elif config.POSTGRES_HOST:
                self._postgres_options = {
                    "host": config.POSTGRES_HOST,
                    "port": config.POSTGRES_PORT,
                    "database": config.POSTGRES_DB,
                    "user": config.POSTGRES_USER,
                    "password": config.POSTGRES_PASSWORD,
                }
        self._load()

    # ---------- персист ----------
    @property
    def backend(self) -> str:
        return "postgresql" if self._postgres_options else "json"

    def _replace_data(self, data: Any, *, strict: bool = False) -> None:
        if not isinstance(data, dict):
            if strict:
                raise ValueError("PostgreSQL state payload must be a JSON object")
            return
        loaded: dict[str, dict[str, Any]] = {t: {} for t in _TABLES}
        for table_name in _TABLES:
            if table_name not in data:
                continue
            table = data.get(table_name)
            if isinstance(table, dict):
                loaded[table_name] = table
            elif strict:
                raise ValueError(f"PostgreSQL state table {table_name!r} must be an object")
        self._data = loaded

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._replace_data(data, strict=bool(self._postgres_options))
        except Exception as exc:  # noqa: BLE001
            self._file_load_error = exc
            return
        self._file_loaded = True

    def _json_payload(self, *, pretty: bool = False) -> str:
        return json.dumps(
            self._data,
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        )

    def _backup_bytes(self) -> bytes:
        return _state_bytes(self._data, pretty=True)

    @staticmethod
    def _write_private_json_sync(path: Path, data: Any, *, pretty: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        text = json.dumps(
            data,
            ensure_ascii=False,
            allow_nan=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        )
        tmp.write_text(text + "\n", encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(path)

    def _inspect_backup_sync(
            self, raw: bytes) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        if not raw:
            raise ValueError("Файл резервной копии пуст.")
        if len(raw) > BACKUP_MAX_BYTES:
            raise ValueError("Файл резервной копии превышает допустимые 50 МБ.")
        data = _validate_backup_data(_decode_json_bytes(raw))
        return data, _backup_summary(data, raw)

    def _read_pending_restore_sync(self) -> dict[str, Any] | None:
        if not self.restore_pending_path.exists():
            return None
        wrapper = _decode_json_bytes(self.restore_pending_path.read_bytes())
        if not isinstance(wrapper, dict) or wrapper.get("format") != _RESTORE_FORMAT:
            raise ValueError("Неизвестный формат подготовленного восстановления.")
        restore_id = str(wrapper.get("restore_id") or "")
        source_sha256 = str(wrapper.get("source_sha256") or "")
        payload_sha256 = str(wrapper.get("payload_sha256") or "")
        if not restore_id.startswith("rst_") or len(restore_id) > 64:
            raise ValueError("Некорректный идентификатор подготовленного восстановления.")
        if len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
            raise ValueError("Некорректная контрольная сумма исходной резервной копии.")
        payload = _validate_backup_data(wrapper.get("payload"))
        actual_payload_sha256 = hashlib.sha256(_state_bytes(payload, pretty=False)).hexdigest()
        if not secrets.compare_digest(payload_sha256, actual_payload_sha256):
            raise ValueError("Подготовленный файл восстановления повреждён.")
        if not _has_restore_marker(payload, restore_id):
            raise ValueError("В подготовленном восстановлении отсутствует audit-marker.")
        return {
            "restore_id": restore_id,
            "source_sha256": source_sha256,
            "payload": payload,
            "payload_json": _state_bytes(payload, pretty=False).decode("utf-8"),
        }

    def _write_previous_restore_sync(self, data: Any) -> None:
        self._write_private_json_sync(self.restore_previous_path, data, pretty=True)

    def _remove_pending_restore_sync(self) -> None:
        try:
            self.restore_pending_path.unlink()
        except FileNotFoundError:
            pass

    async def _remove_pending_restore(self) -> None:
        try:
            await asyncio.to_thread(self._remove_pending_restore_sync)
        except OSError:
            # Marker уже записан в восстановленное состояние, поэтому повторного применения
            # не будет; следующий старт ещё раз попробует удалить staging-файл.
            log.warning("Не удалось удалить %s", self.restore_pending_path, exc_info=True)

    async def _apply_pending_json_restore(self) -> str | None:
        pending = await asyncio.to_thread(self._read_pending_restore_sync)
        if pending is None:
            return None
        restore_id = pending["restore_id"]
        async with self._lock:
            if _has_restore_marker(self._data, restore_id):
                await self._remove_pending_restore()
                return f"restore {restore_id} already applied"
            previous = self._data
            await asyncio.to_thread(self._write_previous_restore_sync, previous)
            self._data = pending["payload"]
            try:
                await asyncio.to_thread(self._save_sync)
            except BaseException:
                self._data = previous
                raise
        await self._remove_pending_restore()
        return f"restore {restore_id}"

    def _save_sync(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(self._json_payload(pretty=True), encoding="utf-8")
        tmp.replace(self.path)

    async def _save(self) -> None:
        if self._postgres_options:
            if self._pool is None:
                raise RuntimeError("PostgreSQL store is not started; call await store.start()")
            payload = await asyncio.to_thread(self._json_payload)
            await self._pool.execute(_UPSERT_STATE_SQL, payload)
            return
        await asyncio.to_thread(self._save_sync)

    async def start(self) -> None:
        """Загрузить storage и до запуска воркеров применить подготовленный restore."""
        if self._started:
            return
        async with self._start_lock:
            if self._started:
                return
            if not self._postgres_options:
                source = await self._apply_pending_json_restore()
                self._started = True
                if source:
                    log.warning("ControlStore: состояние загружено из %s", source)
                return

            pending = await asyncio.to_thread(self._read_pending_restore_sync)
            seed_path_exists = await asyncio.to_thread(self.path.exists)
            pool = await _create_postgres_pool(**self._postgres_options)
            remove_pending = False
            try:
                source = "database"
                async with pool.acquire() as connection:
                    async with connection.transaction():
                        await connection.execute(_CREATE_STATE_TABLE_SQL)
                        payload = await connection.fetchval(_SELECT_STATE_SQL)
                        if isinstance(payload, str):
                            payload = json.loads(payload)

                        if pending is not None:
                            restore_id = pending["restore_id"]
                            if _has_restore_marker(payload, restore_id):
                                source = f"database (restore {restore_id} already applied)"
                            else:
                                previous = payload if payload is not None else _empty_state()
                                await asyncio.to_thread(
                                    self._write_previous_restore_sync, previous)
                                await connection.execute(
                                    _UPSERT_STATE_SQL, pending["payload_json"])
                                payload = pending["payload"]
                                source = f"restore {restore_id}"
                            remove_pending = True
                        elif payload is None:
                            if seed_path_exists and self._file_load_error is not None:
                                raise RuntimeError(
                                    f"Cannot initialize PostgreSQL from unreadable {self.path}"
                                ) from self._file_load_error
                            seed_payload = await asyncio.to_thread(self._json_payload)
                            inserted = await connection.fetchval(
                                _INSERT_INITIAL_STATE_SQL, seed_payload)
                            if inserted is not None:
                                source = "control.json" if self._file_loaded else "empty state"
                            else:
                                # Другой экземпляр успел создать singleton-строку между SELECT
                                # и INSERT; его снимок имеет приоритет над нашим seed.
                                payload = await connection.fetchval(_SELECT_STATE_SQL)
                                if payload is None:
                                    raise RuntimeError("PostgreSQL state row was not initialized")
                                if isinstance(payload, str):
                                    payload = json.loads(payload)
                        if payload is not None:
                            self._replace_data(payload, strict=True)
                self._pool = pool
                self._started = True
                if remove_pending:
                    await self._remove_pending_restore()
            except BaseException:
                await pool.close()
                raise
        log.info("ControlStore: PostgreSQL подключён, состояние загружено из %s", source)

    async def close(self) -> None:
        pool, self._pool = self._pool, None
        self._started = False
        if pool is not None:
            await pool.close()

    async def healthcheck(self) -> bool:
        if not self._postgres_options:
            return True
        if self._pool is None:
            return False
        try:
            async with asyncio.timeout(2):
                return await self._pool.fetchval("SELECT 1") == 1
        except Exception:  # noqa: BLE001
            return False

    async def export_backup(self) -> bytes:
        """Сформировать согласованный логический снимок, совместимый с control.json."""
        async with self._lock:
            return await asyncio.to_thread(self._backup_bytes)

    async def inspect_backup(self, raw: bytes) -> dict[str, Any]:
        """Проверить загруженный снимок без изменения текущего состояния."""
        _data, summary = await asyncio.to_thread(self._inspect_backup_sync, raw)
        return summary

    async def stage_restore(self, raw: bytes, *, expected_sha256: str,
                            ip: str | None = None) -> dict[str, Any]:
        """Подготовить валидный снимок к атомарному применению на следующем старте."""
        data, summary = await asyncio.to_thread(self._inspect_backup_sync, raw)
        if not expected_sha256 or not secrets.compare_digest(
                summary["sha256"], expected_sha256.lower()):
            raise ValueError("Файл изменился после проверки. Выберите его заново.")

        restore_id = "rst_" + secrets.token_hex(8)
        audit_id = "aud_" + secrets.token_hex(6)
        audit = data["admin_audit"]
        audit[audit_id] = {
            "id": audit_id,
            "ts": int(time.time() * 1000),
            "action": "database:restore",
            "target": restore_id,
            "details": {
                "backend": self.backend,
                "source_sha256": summary["sha256"],
            },
            "ip": ip,
        }
        if len(audit) > 5000:
            for key in sorted(
                    (key for key in audit if key != audit_id),
                    key=lambda k: audit[k].get("ts", 0)
                    if isinstance(audit[k], dict) else 0)[:len(audit) - 5000]:
                audit.pop(key, None)

        wrapper = {
            "format": _RESTORE_FORMAT,
            "restore_id": restore_id,
            "source_sha256": summary["sha256"],
            "payload_sha256": hashlib.sha256(_state_bytes(data, pretty=False)).hexdigest(),
            "created_at": _now(),
            "payload": data,
        }
        async with self._lock:
            if await asyncio.to_thread(self.restore_pending_path.exists):
                raise ValueError(
                    "Другое восстановление уже подготовлено. Дождитесь перезапуска сервиса.")
            await asyncio.to_thread(
                self._write_private_json_sync, self.restore_pending_path, wrapper)
        return {**summary, "restoreId": restore_id}

    def table(self, name: str) -> dict[str, Any]:
        return self._data[name]

    # ---------- аккаунты / идентичности ----------
    async def get_or_create_account(self, messenger: str, user_id: Any, phone: str | None) -> dict[str, Any]:
        """Найти аккаунт по идентичности (messenger,user_id) или создать новый.

        Ключ — идентичность мессенджера. Объединение MAX+TG по номеру делается ТОЛЬКО
        через подтверждённый вход по номеру (OTP, link_identity), а НЕ по присланному
        клиентом телефону (иначе можно угнать чужой аккаунт неподтверждённым номером)."""
        async with self._lock:
            ident = f"{messenger}:{user_id}"
            accounts = self._data["accounts"]
            identities = self._data["identities"]
            acc_id = identities.get(ident)
            if acc_id is None:
                acc_id = "acc_" + secrets.token_hex(6)
                accounts[acc_id] = {"id": acc_id, "phone": _norm_phone(phone) if phone else None,
                                    "created_at": _now()}
                self._data["subscriptions"].setdefault(acc_id, _default_subscription())
                self._data["traffic"].setdefault(acc_id, {"used_bytes": 0, "topup_bytes": 0, "period_start": _now()})
            else:
                if phone and not accounts.get(acc_id, {}).get("phone"):
                    accounts[acc_id]["phone"] = _norm_phone(phone)
            identities[ident] = acc_id
            await self._save()
            return dict(accounts[acc_id])

    def account(self, acc_id: str) -> dict[str, Any] | None:
        a = self._data["accounts"].get(acc_id)
        return dict(a) if a else None

    async def update_identity_profile(self, messenger: str, user_id: Any,
                                      user: dict[str, Any] | None) -> dict[str, Any] | None:
        """Сохранить безопасный снимок профиля identity для админки.

        Профиль не участвует в auth/merge-логике: это только отображаемые имя и аватар.
        Для аккаунта с MAX+TG приоритет выбора делается при чтении (MAX, затем TG).
        """
        if not isinstance(user, dict):
            return None
        ident = f"{messenger}:{user_id}"
        async with self._lock:
            acc_id = self._data["identities"].get(ident)
            acc = self._data["accounts"].get(acc_id) if acc_id else None
            if acc is None:
                return None
            profile = _clean_identity_profile(messenger, user_id, user)
            if not profile:
                return dict(acc)
            profiles = acc.setdefault("profiles", {})
            profiles[ident] = profile
            await self._save()
            return dict(acc)

    def identity_profile(self, messenger: str, user_id: Any) -> dict[str, Any] | None:
        acc = self.find_account_by_identity(messenger, user_id)
        if not acc:
            return None
        prof = (acc.get("profiles") or {}).get(f"{messenger}:{user_id}")
        return dict(prof) if isinstance(prof, dict) else None

    def account_profile_summary(self, acc_id: str) -> dict[str, Any]:
        """Отображаемый профиль аккаунта с приоритетом MAX → Telegram."""
        acc = self._data["accounts"].get(acc_id) or {}
        profiles = acc.get("profiles") if isinstance(acc.get("profiles"), dict) else {}
        identities = self.identities_by_messenger(acc_id)

        def prof(messenger: str) -> dict[str, Any]:
            uid = identities.get(messenger)
            if uid is None:
                return {}
            p = profiles.get(f"{messenger}:{uid}")
            return p if isinstance(p, dict) else {}

        max_p, tg_p = prof("max"), prof("tg")
        name_p = max_p if max_p.get("name") else tg_p
        tg_uid = identities.get("tg")
        avatar_p = max_p if (max_p.get("avatar_url") or max_p.get("full_avatar_url")) else tg_p
        name = name_p.get("name") or None
        username = name_p.get("username") or None
        messenger = name_p.get("messenger") or (avatar_p.get("messenger") if avatar_p else None)
        has_tg_avatar_probe = bool(tg_uid and not (
            max_p.get("avatar_url") or max_p.get("full_avatar_url")))
        has_avatar = bool(
            avatar_p.get("avatar_url") or avatar_p.get("full_avatar_url")
            or avatar_p.get("messenger") == "tg"
            or has_tg_avatar_probe
        )
        if has_tg_avatar_probe and not messenger:
            messenger = "tg"
        return {
            "name": name,
            "username": username,
            "messenger": messenger,
            "hasAvatar": has_avatar,
            "avatarVersion": avatar_p.get("updated_at") or (f"tg-{tg_uid}" if has_tg_avatar_probe else None),
        }

    async def mark_account_flag(self, acc_id: str, flag: str) -> dict[str, Any] | None:
        """Выставить одноразовый UI-флаг аккаунта (показанные подсказки и т.п.). Идемпотентно."""
        async with self._lock:
            a = self._data["accounts"].get(acc_id)
            if a is None:
                return None
            flags = a.setdefault("ui_flags", {})
            if not flags.get(flag):
                flags[flag] = True
                await self._save()
            return dict(a)

    async def upsert_registration_lead(self, messenger: str, user_id: Any, *,
                                       chat_id: Any = None, payload: Any = None,
                                       user: dict[str, Any] | None = None,
                                       stage: str = "started",
                                       account_id: str | None = None) -> dict[str, Any]:
        """Сохранить точку входа пользователя из bot deep link без создания аккаунта.

        `bot_started` фиксирует начало регистрации, а воркер напоминает только тем,
        кто не появился в identities. Номер телефона
        здесь намеренно не хранится.
        """
        key = f"{messenger}:{user_id}"
        payload_s = _clean_lead_payload(payload)
        now = _now()
        async with self._lock:
            leads = self._data["registration_leads"]
            rec = leads.setdefault(key, {
                "messenger": str(messenger),
                "user_id": str(user_id),
                "first_seen_at": now,
                "stage": "started",
            })
            rec["last_seen_at"] = now
            if chat_id is not None:
                rec["chat_id"] = str(chat_id)
            if payload_s:
                rec["last_payload"] = payload_s
                hist = rec.get("payload_history")
                if not isinstance(hist, list):
                    hist = []
                if not hist or hist[-1].get("payload") != payload_s:
                    hist.append({"payload": payload_s, "ts": now})
                rec["payload_history"] = hist[-10:]
            if isinstance(user, dict):
                username = _clean_lead_payload(user.get("username"), limit=64)
                name = _clean_lead_payload(
                    " ".join(p for p in (user.get("first_name"), user.get("last_name")) if p)
                    or user.get("name"), limit=96)
                if username:
                    rec["username"] = username
                if name:
                    rec["name"] = name
            if _lead_stage_rank(stage) >= _lead_stage_rank(str(rec.get("stage") or "")):
                rec["stage"] = str(stage or "started")
            if account_id:
                rec["account_id"] = str(account_id)
            await self._save()
            return dict(rec)

    def registration_lead(self, messenger: str, user_id: Any) -> dict[str, Any] | None:
        rec = self._data["registration_leads"].get(f"{messenger}:{user_id}")
        return dict(rec) if rec else None

    async def due_registration_reminders(self, messenger: str, delays: tuple[float, ...] | list[float],
                                         *, now: int | None = None, limit: int = 50
                                         ) -> list[dict[str, Any]]:
        """Вернуть лиды, которым пора отправить follow-up регистрации.

        Лид считается завершённым, если для его messenger:user_id уже есть аккаунт с
        подтверждённым телефоном. В этом случае запись помечается `registered`, чтобы воркер
        больше её не трогал. Телефон в lead не копируется.
        """
        now_i = _now() if now is None else int(now)
        schedule: list[int] = []
        for raw_delay in delays:
            try:
                delay = int(float(raw_delay))
            except (TypeError, ValueError):
                continue
            if delay >= 0:
                schedule.append(delay)
        if not schedule:
            return []
        due: list[dict[str, Any]] = []
        changed = False
        async with self._lock:
            leads = self._data["registration_leads"]
            for key, rec in leads.items():
                if str(rec.get("messenger") or "") != str(messenger):
                    continue
                user_id = str(rec.get("user_id") or key.split(":", 1)[-1])
                ident = f"{messenger}:{user_id}"
                acc_id = rec.get("account_id") or self._data["identities"].get(ident)
                account = self._data["accounts"].get(str(acc_id)) if acc_id else None
                if account and _valid_phone(_norm_phone(account.get("phone"))):
                    if rec.get("account_id") != account.get("id") or rec.get("stage") != "registered":
                        rec["account_id"] = account["id"]
                        rec["stage"] = "registered"
                        rec["registered_at"] = now_i
                        changed = True
                    continue
                if _lead_stage_rank(str(rec.get("stage") or "")) >= _lead_stage_rank("registered"):
                    continue

                sent_raw = rec.get("reminders_sent")
                sent = sent_raw if isinstance(sent_raw, list) else []
                sent_idx = {int(x.get("index", -1)) for x in sent if isinstance(x, dict)}
                base_ts = int(rec.get("first_seen_at") or rec.get("last_seen_at") or now_i)
                for idx, delay in enumerate(schedule):
                    if idx in sent_idx:
                        continue
                    if now_i - base_ts >= delay:
                        item = dict(rec)
                        item["reminder_index"] = idx
                        item["reminder_delay"] = delay
                        due.append(item)
                        break
                if len(due) >= max(1, int(limit)):
                    break
            if changed:
                await self._save()
        return due

    async def mark_registration_reminder_sent(self, messenger: str, user_id: Any,
                                              reminder_index: int, *, now: int | None = None
                                              ) -> dict[str, Any] | None:
        now_i = _now() if now is None else int(now)
        key = f"{messenger}:{user_id}"
        async with self._lock:
            rec = self._data["registration_leads"].get(key)
            if rec is None:
                return None
            sent = rec.get("reminders_sent")
            if not isinstance(sent, list):
                sent = []
            idx = int(reminder_index)
            if not any(isinstance(x, dict) and int(x.get("index", -1)) == idx for x in sent):
                sent.append({"index": idx, "ts": now_i})
            rec["reminders_sent"] = sent
            rec["last_reminder_at"] = now_i
            if _lead_stage_rank(str(rec.get("stage") or "")) < _lead_stage_rank("reminded"):
                rec["stage"] = "reminded"
            await self._save()
            return dict(rec)

    async def accept_legal(self, acc_id: str, *, terms_version: str, privacy_version: str,
                           source: str = "miniapp", messenger: str | None = None,
                           user_id: Any = None) -> dict[str, Any] | None:
        """Зафиксировать явный акцепт текущих юридических документов.

        Храним текущий снимок и короткую историю: этого достаточно для повторного акцепта
        при смене редакции и для последующего аудита без раздувания control.json.
        """
        async with self._lock:
            a = self._data["accounts"].get(acc_id)
            if a is None:
                return None
            rec: dict[str, Any] = {
                "terms_version": str(terms_version),
                "privacy_version": str(privacy_version),
                "accepted_at": _now(),
                "source": str(source or "miniapp")[:64],
            }
            if messenger:
                rec["messenger"] = str(messenger)[:16]
            if user_id is not None:
                rec["user_id"] = str(user_id)
            a["legal_acceptance"] = dict(rec)
            hist = a.get("legal_history")
            if not isinstance(hist, list):
                hist = []
            hist.append(dict(rec))
            a["legal_history"] = hist[-20:]
            await self._save()
            return dict(a)

    def find_account_by_phone(self, phone: str, exclude: str | None = None) -> dict[str, Any] | None:
        np = _norm_phone(phone)
        for a in self._data["accounts"].values():
            if a["id"] == exclude:
                continue
            if a.get("phone") and _norm_phone(a["phone"]) == np:
                return dict(a)
        return None

    def find_account_by_identity(self, messenger: str, user_id: Any) -> dict[str, Any] | None:
        """Найти аккаунт по идентичности мессенджера (messenger,user_id) БЕЗ создания.
        Для тихого восстановления сессии: вернувшийся пользователь есть → отдаём аккаунт,
        нового (нет идентичности) НЕ создаём (он пройдёт обычный вход)."""
        acc_id = self._data["identities"].get(f"{messenger}:{user_id}")
        a = self._data["accounts"].get(acc_id) if acc_id else None
        return dict(a) if a else None

    async def link_identity(self, messenger: str, user_id: Any, acc_id: str) -> None:
        """Привязать messenger-логин к аккаунту (идемпотентно)."""
        async with self._lock:
            self._data["identities"].setdefault(f"{messenger}:{user_id}", acc_id)
            await self._save()

    async def confirm_identity_phone(self, messenger: str, user_id: Any,
                                     phone: str) -> dict[str, Any]:
        """Применить КРИПТОГРАФИЧЕСКИ/ПЛАТФОРМЕННО подтверждённый номер к identity.

        Вызов допустим только после проверки MAX requestContact либо Telegram self-contact.
        Новая identity получает существующий аккаунт с этим номером или создаёт новый.
        Legacy-аккаунт без телефона сливается с найденным по номеру; при слиянии сохраняем
        более старый account id, чтобы без необходимости не инвалидировать старые сессии.

        Уже полноценный аккаунт с телефоном не переименовываем по номеру другой identity:
        объединение аккаунтов с разными номерами выполняется только явным OTP-входом.
        """
        normalized = _norm_phone(phone)
        if not _valid_phone(normalized):
            raise ValueError("invalid phone")
        ident = f"{messenger}:{user_id}"

        async with self._phone_lock:
            current = self.find_account_by_identity(messenger, user_id)
            if current and _valid_phone(_norm_phone(current.get("phone"))):
                return current

            by_phone = self.find_account_by_phone(normalized)
            if current and by_phone and current["id"] != by_phone["id"]:
                keep, drop = ((current, by_phone)
                              if int(current.get("created_at", 0)) <= int(by_phone.get("created_at", 0))
                              else (by_phone, current))
                await self.merge_account(drop["id"], keep["id"])
                resolved = self.find_account_by_identity(messenger, user_id)
                if resolved and _valid_phone(_norm_phone(resolved.get("phone"))):
                    return resolved
                raise RuntimeError("account merge failed")

            if current:
                async with self._lock:
                    acc = self._data["accounts"].get(current["id"])
                    if acc is None:
                        raise RuntimeError("account disappeared")
                    if not _valid_phone(_norm_phone(acc.get("phone"))):
                        acc["phone"] = normalized
                        await self._save()
                    return dict(acc)

            if by_phone:
                async with self._lock:
                    if by_phone["id"] not in self._data["accounts"]:
                        raise RuntimeError("account disappeared")
                    self._data["identities"][ident] = by_phone["id"]
                    await self._save()
                    return dict(self._data["accounts"][by_phone["id"]])

            # Единственная разрешённая точка создания auth-аккаунта: сюда попадает только
            # уже подтверждённый номер, поэтому аккаунт никогда не рождается без телефона.
            return await self.get_or_create_account(messenger, user_id, normalized)

    async def link_identity_to_account(self, messenger: str, user_id: Any,
                                       dst_id: str) -> dict[str, Any]:
        """После успешного OTP привязать текущую host-identity к целевому аккаунту.

        Если из-за старого auth-flow у identity уже есть отдельный аккаунт, переносим его
        данные в подтверждённый OTP аккаунт и удаляем дубль. Целевой аккаунт обязан иметь
        телефон: OTP не может легализовать legacy-аккаунт без номера.
        """
        async with self._phone_lock:
            target = self.account(dst_id)
            if target is None or not _valid_phone(_norm_phone(target.get("phone"))):
                raise ValueError("target account has no confirmed phone")
            current = self.find_account_by_identity(messenger, user_id)
            if current and current["id"] != dst_id:
                if not await self.merge_account(current["id"], dst_id):
                    raise RuntimeError("account merge failed")
            elif current is None:
                async with self._lock:
                    if dst_id not in self._data["accounts"]:
                        raise RuntimeError("account disappeared")
                    self._data["identities"][f"{messenger}:{user_id}"] = dst_id
                    await self._save()
            linked = self.find_account_by_identity(messenger, user_id)
            if linked is None or linked["id"] != dst_id:
                raise RuntimeError("identity link failed")
            return linked

    async def merge_account(self, src_id: str, dst_id: str) -> bool:
        """Слить аккаунт src в dst и удалить src. Переносит идентичности, источники
        (account_sources), правила, активные коды, уведомления и жалобы (reports); суммирует
        трафик; переносит подписку, если она активнее dst; заполняет телефон dst при отсутствии.
        Возвращает False, если src==dst или какого-то аккаунта нет.

        Используется при объединении MAX+TG по ПОДТВЕРЖДЁННОМУ номеру (см. auth_contact)."""
        async with self._lock:
            accs = self._data["accounts"]
            if src_id == dst_id or src_id not in accs or dst_id not in accs:
                return False
            # идентичности
            for ident, aid in list(self._data["identities"].items()):
                if aid == src_id:
                    self._data["identities"][ident] = dst_id
            # источники, привязанные к аккаунту напрямую (каналы)
            srcs = self._data["account_sources"]
            if srcs.get(src_id):
                merged = list(dict.fromkeys((srcs.get(dst_id) or []) + srcs[src_id]))
                srcs[dst_id] = merged
            srcs.pop(src_id, None)
            # правила, активные коды, уведомления — переносим владельца
            for r in self._data["rules"].values():
                if r.get("account_id") == src_id:
                    r["account_id"] = dst_id
            # Дедуп одинаковых пар источников у dst (после переноса src-правил): иначе
            # диспетчер (targets_for) переслал бы каждое сообщение дважды и дважды списал
            # трафик. Оставляем по одному правилу на пару (приоритет активному, затем старшему).
            seen_pairs: dict[frozenset, str] = {}
            dst_rules = sorted(
                (r for r in self._data["rules"].values() if r.get("account_id") == dst_id),
                key=lambda r: (r.get("status") != "active", int(r.get("created_at", 0))))
            for r in dst_rules:
                a, b = r.get("a") or {}, r.get("b") or {}
                key = frozenset({make_source_id(a.get("messenger"), a.get("chat_id"), a.get("thread_id")),
                                 make_source_id(b.get("messenger"), b.get("chat_id"), b.get("thread_id"))})
                if key in seen_pairs:
                    self._data["rules"].pop(r["id"], None)   # дубль пары — удаляем
                else:
                    seen_pairs[key] = r["id"]
            for rec in self._data["pending_codes"].values():
                if rec.get("account_id") == src_id:
                    rec["account_id"] = dst_id
            for n in self._data["notifications"].values():
                if n.get("account_id") == src_id:
                    n["account_id"] = dst_id
            # жалобы (модерация, этап 3): переносим владельца, иначе запись осиротеет на
            # удалённом аккаунте, а уведомление владельцу по жалобе «в полёте» уйдёт в никуда.
            for rep in self._data["reports"].values():
                if rep.get("account_id") == src_id:
                    rep["account_id"] = dst_id
            # трафик — суммируем (включая разбивку по правилам per_rule, иначе она
            # перестала бы сходиться с used_bytes и потеряла бы историю перенесённых правил)
            st = self._data["traffic"].pop(src_id, None)
            if st:
                dt = self._data["traffic"].setdefault(
                    dst_id, {"used_bytes": 0, "topup_bytes": 0, "period_start": st.get("period_start", _now())})
                dt["used_bytes"] = int(dt.get("used_bytes", 0)) + int(st.get("used_bytes", 0))
                dt["topup_bytes"] = int(dt.get("topup_bytes", 0)) + int(st.get("topup_bytes", 0))
                dpr = dt.setdefault("per_rule", {})
                for rid, used in (st.get("per_rule") or {}).items():
                    dpr[rid] = int(dpr.get(rid, 0)) + int(used)
            # подписка — берём ту, что «лучше» для пользователя: активную приоритетнее
            # неактивной, при обеих активных — с более поздним renew_at (не теряем оплаченное)
            ss = self._data["subscriptions"].pop(src_id, None)
            ds = self._data["subscriptions"].get(dst_id)
            if ss:
                src_active = ss.get("status") == "active"
                dst_active = bool(ds) and ds.get("status") == "active"
                # Пробный период — один на пользователя: использованный триал любой
                # из половинок переживает слияние.
                trial_used = bool(ss.get("trial_used")) or bool(ds and ds.get("trial_used"))
                if not ds:
                    self._data["subscriptions"][dst_id] = ss
                elif src_active and not dst_active:
                    self._data["subscriptions"][dst_id] = ss
                elif src_active and dst_active and str(ss.get("renew_at") or "") > str(ds.get("renew_at") or ""):
                    # renew_at — ISO-дата ("YYYY-MM-DD"), сравнивается лексикографически
                    self._data["subscriptions"][dst_id] = ss
                self._data["subscriptions"][dst_id]["trial_used"] = trial_used
            # телефон в dst, если его там не было
            if not accs[dst_id].get("phone") and accs[src_id].get("phone"):
                accs[dst_id]["phone"] = accs[src_id]["phone"]
            # Профили identities (имя/аватар для админки) тоже относятся к identity,
            # поэтому переживают объединение MAX+TG.
            src_profiles = accs[src_id].get("profiles") if isinstance(accs[src_id].get("profiles"), dict) else {}
            if src_profiles:
                dst_profiles = accs[dst_id].setdefault("profiles", {})
                for ident, profile in src_profiles.items():
                    if isinstance(profile, dict):
                        dst_profiles.setdefault(ident, dict(profile))
            # одноразовые UI-флаги (показанные подсказки): «видел любой из половинок»
            src_flags = accs[src_id].get("ui_flags") or {}
            if src_flags:
                dst_flags = accs[dst_id].setdefault("ui_flags", {})
                for k, v in src_flags.items():
                    if v:
                        dst_flags[k] = True
            # Юридические акцепты: объединяем историю и сохраняем последний известный снимок.
            legal_rows: list[dict[str, Any]] = []
            for aid in (dst_id, src_id):
                cur = accs[aid].get("legal_acceptance")
                if isinstance(cur, dict):
                    legal_rows.append(dict(cur))
                hist = accs[aid].get("legal_history")
                if isinstance(hist, list):
                    legal_rows.extend(dict(x) for x in hist if isinstance(x, dict))
            if legal_rows:
                def _legal_sort_key(x: dict[str, Any]) -> tuple[int, bool]:
                    current = (x.get("terms_version") == config.LEGAL_TERMS_VERSION
                               and x.get("privacy_version") == config.LEGAL_PRIVACY_VERSION)
                    return int(x.get("accepted_at") or 0), current
                legal_rows.sort(key=_legal_sort_key)
                accs[dst_id]["legal_history"] = legal_rows[-20:]
                accs[dst_id]["legal_acceptance"] = dict(legal_rows[-1])
            accs.pop(src_id, None)
            await self._save()
            return True

    # ---------- источники аккаунта, привязанные через mini-app ----------
    # Нужно для каналов: пост в канале не содержит отправителя (from), поэтому
    # привязку нельзя связать с messenger-пользователем — связываем с АККАУНТОМ.
    def account_source_ids(self, acc_id: str) -> list[str]:
        return list(self._data["account_sources"].get(acc_id, []))

    async def add_account_source(self, acc_id: str, source_id: str) -> None:
        async with self._lock:
            lst = self._data["account_sources"].setdefault(acc_id, [])
            if source_id and source_id not in lst:
                lst.append(source_id)
                await self._save()

    async def remove_account_source(self, acc_id: str, source_id: str) -> None:
        async with self._lock:
            lst = self._data["account_sources"].get(acc_id, [])
            if source_id in lst:
                lst.remove(source_id)
                await self._save()

    async def remove_source_from_codes(self, source_id: str) -> None:
        """Убрать source_id из bound всех активных кодов привязки — чтобы удалённый
        источник не висел в статусе привязки и не «возвращался» тем же кодом."""
        async with self._lock:
            changed = False
            for rec in self._data["pending_codes"].values():
                bound = rec.get("bound")
                if isinstance(bound, list) and source_id in bound:
                    rec["bound"] = [s for s in bound if s != source_id]
                    changed = True
            if changed:
                await self._save()

    async def delete_source_references(self, messenger: str, chat_id: Any,
                                       thread_id: Any | None = None) -> dict[str, Any]:
        """Удалить все ссылки control-store на источник.

        Используется и явным DELETE /api/sources, и автоматическим снятием привязки, когда
        бота удалили из чата. Для удаления базового Telegram-чата (`thread_id is None`)
        чистим также все topic-источники этого чата: после удаления бота из супергруппы ни
        одна тема больше не является рабочим источником/приёмником.
        """
        chat_s = str(chat_id)
        thread_s = str(thread_id).strip() if thread_id is not None else None
        source_id = make_source_id(messenger, chat_s, thread_s)

        def matches_ep(ep: dict[str, Any] | None) -> bool:
            if not isinstance(ep, dict):
                return False
            if ep.get("messenger") != messenger or str(ep.get("chat_id")) != chat_s:
                return False
            if thread_s is not None:
                return str(ep.get("thread_id")) == thread_s
            return True if messenger == "tg" else ep.get("thread_id") is None

        def matches_sid(sid: Any) -> bool:
            parsed = parse_source_id(str(sid or ""))
            if not parsed:
                return False
            if parsed.get("messenger") != messenger or str(parsed.get("chat_id")) != chat_s:
                return False
            if thread_s is not None:
                return str(parsed.get("thread_id")) == thread_s
            return True if messenger == "tg" else parsed.get("thread_id") is None

        async with self._lock:
            changed = False
            removed_rules: list[str] = []
            for rid, rule in list(self._data["rules"].items()):
                if matches_ep(rule.get("a")) or matches_ep(rule.get("b")):
                    self._data["rules"].pop(rid, None)
                    removed_rules.append(rid)
                    changed = True

            removed_sources: dict[str, list[str]] = {}
            for acc_id, srcs in list(self._data["account_sources"].items()):
                if not isinstance(srcs, list):
                    continue
                keep = []
                gone = []
                for sid in srcs:
                    if matches_sid(sid):
                        gone.append(str(sid))
                    else:
                        keep.append(sid)
                if gone:
                    self._data["account_sources"][acc_id] = keep
                    removed_sources[acc_id] = gone
                    changed = True

            removed_from_codes: list[str] = []
            for code, rec in self._data["pending_codes"].items():
                if matches_sid(rec.get("source_id")):
                    rec.pop("source_id", None)
                    removed_from_codes.append(code)
                    changed = True
                bound = rec.get("bound")
                if isinstance(bound, list):
                    keep = [sid for sid in bound if not matches_sid(sid)]
                    if len(keep) != len(bound):
                        rec["bound"] = keep
                        removed_from_codes.append(code)
                        changed = True

            removed_meta: list[str] = []
            for sid in list(self._data["source_meta"].keys()):
                if matches_sid(sid):
                    self._data["source_meta"].pop(sid, None)
                    removed_meta.append(sid)
                    changed = True

            if changed:
                await self._save()
            return {
                "source_id": source_id,
                "removed_rules": removed_rules,
                "removed_sources": removed_sources,
                "removed_codes": sorted(set(removed_from_codes)),
                "removed_meta": removed_meta,
            }

    def identities_of(self, acc_id: str) -> list[tuple[str, str]]:
        """[(messenger, user_id)] всех логинов аккаунта."""
        out: list[tuple[str, str]] = []
        for ident, aid in self._data["identities"].items():
            if aid == acc_id and ":" in ident:
                m, uid = ident.split(":", 1)
                out.append((m, uid))
        return out

    def identities_by_messenger(self, acc_id: str) -> dict[str, str]:
        """Первая identity аккаунта в каждом мессенджере: {"max": uid, "tg": uid}. Для
        рассылки уведомлений во ВСЕ привязанные мессенджеры (если привязаны оба)."""
        out: dict[str, str] = {}
        for m, uid in self.identities_of(acc_id):
            out.setdefault(m, uid)
        return out

    # ---------- подписка ----------
    def subscription(self, acc_id: str) -> dict[str, Any]:
        return dict(self._data["subscriptions"].get(acc_id) or _default_subscription())

    async def set_subscription(self, acc_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            sub = self._data["subscriptions"].setdefault(acc_id, _default_subscription())
            sub.update(patch)
            await self._save()
            return dict(sub)

    async def disable_subscription(self, acc_id: str) -> dict[str, Any]:
        """Полностью отключить подписку администратором, не возвращая право на триал."""
        async with self._lock:
            sub = self._data["subscriptions"].setdefault(acc_id, _default_subscription())
            sub.update({
                "status": "inactive",
                "renew_at": None,
                "paid_until": 0,
                "trial": False,
                "autopay": False,
                "payment_method_id": None,
                "payment_method_title": None,
                "pending": None,
                "renew_attempts": 0,
                "renew_retry_at": 0,
                "last_error": None,
            })
            await self._save()
            return dict(sub)

    async def disable_autopay(self, acc_id: str, *, now: int | None = None) -> tuple[dict[str, Any], bool]:
        """Отключить только автопродление/привязку. Оплаченный период сохраняется."""
        async with self._lock:
            sub = self._data["subscriptions"].setdefault(acc_id, _default_subscription())
            current = int(now if now is not None else _now())
            annulled = bool(sub.get("trial") and sub.get("status") == "active")
            patch: dict[str, Any] = {
                "autopay": False,
                "payment_method_id": None,
                "payment_method_title": None,
                "pending": None,
                "renew_attempts": 0,
                "renew_retry_at": 0,
                "last_error": None,
            }
            if annulled:
                # Триал держится на привязке способа оплаты: без неё он завершается сразу.
                patch.update({
                    "status": "inactive",
                    "trial": False,
                    "paid_until": current,
                    "renew_at": time.strftime("%Y-%m-%d", time.gmtime(current)),
                })
            sub.update(patch)
            await self._save()
            return dict(sub), annulled

    # ---------- коды активации подписки ----------
    async def add_activation_codes(self, codes: list[str], *, created_at: int | None = None) -> None:
        """Зарегистрировать новые (сгенерированные админом) коды активации."""
        async with self._lock:
            table = self._data["activation_codes"]
            now = int(created_at if created_at is not None else _now())
            for code in codes:
                table.setdefault(str(code), {
                    "created_at": now,
                    "expires_at": now + ACTIVATION_CODE_TTL,
                    "used_by": None,
                    "used_at": None,
                    "revoked_at": None,
                })
            await self._save()

    @staticmethod
    def _activation_code_expiry(rec: dict[str, Any]) -> int:
        explicit = int(rec.get("expires_at") or 0)
        if explicit > 0:
            return explicit
        # Миграция без переписывания control.json: старым кодам, созданным до появления
        # expires_at, срок считается от уже сохранённого created_at.
        return int(rec.get("created_at") or 0) + ACTIVATION_CODE_TTL

    async def claim_activation_code(self, code: str, acc_id: str, *, now: int | None = None) -> str:
        """Атомарно проверить и потратить код.

        Возвращает `used`, `expired` или `unavailable` (нет/уже использован). Раздельный
        статус нужен, чтобы пользователь видел понятную причину, но проверка и пометка
        остаются под одним локом — параллельные запросы не применят код дважды.
        """
        async with self._lock:
            rec = self._data["activation_codes"].get(str(code))
            if rec is None or rec.get("used_by") or rec.get("revoked_at"):
                return "unavailable"
            current = int(now if now is not None else _now())
            expires_at = self._activation_code_expiry(rec)
            if current >= expires_at:
                return "expired"
            rec.setdefault("expires_at", expires_at)
            rec["used_by"] = acc_id
            rec["used_at"] = current
            await self._save()
            return "used"

    async def use_activation_code(self, code: str, acc_id: str) -> bool:
        """Совместимый bool-wrapper для внутренних/старых вызовов."""
        return await self.claim_activation_code(code, acc_id) == "used"

    async def revoke_activation_code(self, code: str, *, now: int | None = None) -> str:
        """Аннулировать свободный код активации.

        Возвращает `revoked`, `not_found`, `used`, `expired` или `already_revoked`.
        Историю записи сохраняем, чтобы админка показывала факт аннулирования.
        """
        async with self._lock:
            rec = self._data["activation_codes"].get(str(code))
            if rec is None:
                return "not_found"
            if rec.get("used_by"):
                return "used"
            current = int(now if now is not None else _now())
            if rec.get("revoked_at"):
                return "already_revoked"
            expires_at = self._activation_code_expiry(rec)
            if current >= expires_at:
                if rec.get("expires_at") != expires_at:
                    rec["expires_at"] = expires_at
                    await self._save()
                return "expired"
            rec.setdefault("expires_at", expires_at)
            rec["revoked_at"] = current
            await self._save()
            return "revoked"

    def activation_codes_stats(self, *, now: int | None = None) -> dict[str, Any]:
        """Сводка для админа: свободные, использованные, истёкшие и аннулированные коды."""
        table = self._data["activation_codes"]
        current = int(now if now is not None else _now())
        unused: list[str] = []
        expired: list[dict[str, Any]] = []
        used: list[dict[str, Any]] = []
        revoked: list[dict[str, Any]] = []
        for code, rec in table.items():
            expires_at = self._activation_code_expiry(rec)
            if rec.get("used_by"):
                used.append({"code": code, "used_by": rec.get("used_by"),
                             "used_at": rec.get("used_at"), "expires_at": expires_at})
            elif rec.get("revoked_at"):
                revoked.append({"code": code, "created_at": rec.get("created_at"),
                                "expires_at": expires_at, "revoked_at": rec.get("revoked_at")})
            elif current >= expires_at:
                expired.append({"code": code, "created_at": rec.get("created_at"),
                                "expires_at": expires_at})
            else:
                unused.append(code)
        return {"total": len(table), "unused": sorted(unused),
                "expired": sorted(expired, key=lambda r: r.get("expires_at") or 0),
                "used": sorted(used, key=lambda r: r.get("used_at") or 0),
                "revoked": sorted(revoked, key=lambda r: r.get("revoked_at") or 0)}

    # ---------- цифровые заказы Яндекс Маркета ----------
    @staticmethod
    def market_order_key(campaign_id: Any, order_id: Any) -> str:
        return f"{int(campaign_id)}:{int(order_id)}"

    async def queue_market_order(self, campaign_id: int, order_id: int, *,
                                 updated_at: str | None = None) -> dict[str, Any]:
        """Поставить оплаченный PROCESSING-заказ в персистентную очередь.

        Повторное уведомление не сбрасывает уже отправленные коды и не создаёт новую
        доставку. `processing` тоже возвращается в очередь: это crash-recovery, если
        процесс остановился между HTTP-запросом к Маркету и записью результата.
        """
        async with self._lock:
            key = self.market_order_key(campaign_id, order_id)
            table = self._data["market_orders"]
            rec = table.setdefault(key, {
                "id": key,
                "campaign_id": int(campaign_id),
                "order_id": int(order_id),
                "created_at": _now(),
                "state": "queued",
                "attempt_count": 0,
                "next_attempt_at": 0,
                "items": [],
            })
            rec["market_status"] = "PROCESSING"
            rec["notification_updated_at"] = updated_at
            rec["notification_at"] = _now()
            if rec.get("state") not in {"delivery_sent", "delivered", "cancelled",
                                        "cancelled_after_delivery", "failed"}:
                rec["state"] = "queued"
                rec["next_attempt_at"] = 0
            await self._save()
            return copy.deepcopy(rec)

    def market_order(self, key: str) -> dict[str, Any] | None:
        rec = self._data["market_orders"].get(str(key))
        return copy.deepcopy(rec) if rec is not None else None

    async def update_market_order(self, key: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        async with self._lock:
            rec = self._data["market_orders"].get(str(key))
            if rec is None:
                return None
            rec.update(copy.deepcopy(patch))
            await self._save()
            return copy.deepcopy(rec)

    def due_market_order_ids(self, *, now: int | None = None) -> list[str]:
        """Незавершённые заказы, готовые к попытке; старые первыми."""
        current = int(now if now is not None else _now())
        rows = [
            (key, rec) for key, rec in self._data["market_orders"].items()
            if rec.get("state") in {"queued", "processing", "retry"}
            and int(rec.get("next_attempt_at") or 0) <= current
        ]
        rows.sort(key=lambda pair: (int(pair[1].get("created_at") or 0), pair[0]))
        return [key for key, _ in rows]

    async def reserve_market_activation_codes(self, key: str,
                                              items: list[dict[str, Any]], *,
                                              created_at: int | None = None
                                              ) -> dict[str, Any] | None:
        """Атомарно закрепить заранее сгенерированные коды за позициями заказа.

        Если заказ уже имеет коды, возвращается прежний набор: повторная доставка после
        сетевого сбоя отправит те же секреты. Коллизия с любым существующим кодом
        отклоняется целиком, чтобы вызывающий код сгенерировал новый набор.
        """
        async with self._lock:
            rec = self._data["market_orders"].get(str(key))
            if rec is None:
                return None
            if rec.get("items"):
                return copy.deepcopy(rec)
            if rec.get("state") not in {"queued", "processing", "retry"}:
                return None
            codes = [str(code) for item in items for code in (item.get("codes") or [])]
            if not codes or len(codes) != len(set(codes)):
                raise ValueError("market activation codes must be non-empty and unique")
            activation = self._data["activation_codes"]
            if any(code in activation for code in codes):
                raise KeyError("activation code collision")
            now = int(created_at if created_at is not None else _now())
            expires_at = now + ACTIVATION_CODE_TTL
            normalized_items: list[dict[str, Any]] = []
            for item in items:
                item_id = int(item["id"])
                item_codes = [str(code) for code in item.get("codes") or []]
                normalized_items.append({
                    "id": item_id,
                    "offer_id": str(item.get("offer_id") or ""),
                    "count": len(item_codes),
                    "codes": item_codes,
                    "activate_till": str(item.get("activate_till") or ""),
                })
                for code in item_codes:
                    activation[code] = {
                        "created_at": now,
                        "expires_at": expires_at,
                        "used_by": None,
                        "used_at": None,
                        "source": "yandex_market",
                        "market_order_id": str(key),
                        "market_item_id": item_id,
                    }
            rec["items"] = normalized_items
            rec["codes_reserved_at"] = now
            await self._save()
            return copy.deepcopy(rec)

    async def set_market_order_status(self, campaign_id: int, order_id: int, *,
                                      market_status: str, updated_at: str | None = None
                                      ) -> dict[str, Any] | None:
        """Сохранить финальный статус Маркета и безопасно отменить невыданные коды."""
        async with self._lock:
            key = self.market_order_key(campaign_id, order_id)
            rec = self._data["market_orders"].get(key)
            if rec is None:
                return None
            status = str(market_status or "").upper()
            rec["market_status"] = status
            rec["notification_updated_at"] = updated_at
            rec["notification_at"] = _now()
            if status == "DELIVERED":
                rec["state"] = "delivered"
                rec["delivered_at"] = _now()
            elif status == "CANCELLED":
                already_sent = rec.get("state") in {"delivery_sent", "delivered",
                                                      "cancelled_after_delivery"}
                if already_sent:
                    # После раскрытия кода не отзываем его автоматически: покупатель уже
                    # мог скопировать секрет. Возврат цифрового товара требует ручной проверки.
                    rec["state"] = "cancelled_after_delivery"
                else:
                    for item in rec.get("items") or []:
                        for code in item.get("codes") or []:
                            code_rec = self._data["activation_codes"].get(code)
                            if (code_rec and not code_rec.get("used_by")
                                    and code_rec.get("market_order_id") == key):
                                self._data["activation_codes"].pop(code, None)
                    rec["state"] = "cancelled"
                    rec["items"] = []
                rec["cancelled_at"] = _now()
            await self._save()
            return copy.deepcopy(rec)

    # ---------- жалобы на контент (модерация, этап 3) ----------
    async def add_report(self, rec: dict[str, Any]) -> dict[str, Any]:
        """Записать новую жалобу (статус queued). Возвращает сохранённую запись с id.
        Персистентность нужна, чтобы очередь пережила рестарт (обработчик идемпотентен)."""
        async with self._lock:
            rid = rec.get("id") or ("rep_" + secrets.token_hex(6))
            rec["id"] = rid
            rec.setdefault("ts", _now())
            rec.setdefault("status", "queued")
            rec.setdefault("repeat_count", 0)
            self._data["reports"][rid] = rec
            await self._save()
            return dict(rec)

    def report(self, report_id: str) -> dict[str, Any] | None:
        r = self._data["reports"].get(report_id)
        return dict(r) if r else None

    async def update_report(self, report_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        async with self._lock:
            r = self._data["reports"].get(report_id)
            if r is None:
                return None
            r.update(patch)
            await self._save()
            return dict(r)

    def queued_report_ids(self) -> list[str]:
        """Id жалоб в статусе queued (старейшие раньше) — для наполнения очереди при старте."""
        items = [(rid, r) for rid, r in self._data["reports"].items()
                 if r.get("status") == "queued"]
        items.sort(key=lambda kv: kv[1].get("ts", 0))
        return [rid for rid, _ in items]

    def find_processed_report(self, src_key: str, text_hash: str) -> dict[str, Any] | None:
        """КОРЕНЬ уже проверенной жалобы на ТОТ ЖЕ контент (совпали src_key и hash текста) —
        чтобы повторную не гонять через ИИ снова. Матчим ТОЛЬКО ОКОНЧАТЕЛЬНЫЕ вердикты
        (`ok`/`violation`): `unsure`/`unavailable` (ИИ был недоступен) НЕ кэшируем — иначе
        транзиентный сбой ИИ навсегда снял бы контент с проверки (обход модерации). Исключаем
        сами повторы (`repeat_of`) и берём САМУЮ РАННЮЮ запись — тогда счётчик повторов всегда
        копится на одном корне (а не «повторная №1» на каждой новой)."""
        matches = [r for r in self._data["reports"].values()
                   if r.get("status") == "done" and r.get("verdict") in ("ok", "violation")
                   and not r.get("repeat_of")
                   and r.get("src_key") == src_key and r.get("text_hash") == text_hash]
        if not matches:
            return None
        return dict(min(matches, key=lambda r: r.get("ts", 0)))

    async def bump_report_repeat(self, report_id: str) -> int:
        """Учесть ещё одну повторную жалобу на уже проверенный контент. Возвращает
        новое число повторов (0, если записи нет)."""
        async with self._lock:
            r = self._data["reports"].get(report_id)
            if r is None:
                return 0
            r["repeat_count"] = int(r.get("repeat_count", 0)) + 1
            await self._save()
            return r["repeat_count"]

    def reports_since(self, account_id: str, since_ts: int, *,
                      verdict: str | None = None) -> list[dict[str, Any]]:
        """Жалобы аккаунта не старше since_ts (опционально фильтр по вердикту). Основа
        для страйков/автопаузы этапа 4 (подтверждённые нарушения за окно)."""
        out = [dict(r) for r in self._data["reports"].values()
               if r.get("account_id") == account_id and int(r.get("ts", 0)) >= since_ts
               and (verdict is None or r.get("verdict") == verdict)]
        out.sort(key=lambda r: r.get("ts", 0), reverse=True)
        return out

    def count_rule_violations_since(self, rule_id: str, since_ts: int) -> int:
        """Число подтверждённых нарушений (verdict=violation) по правилу за окно — для
        автопаузы по страйкам (этап 4.2)."""
        if not rule_id:
            return 0
        # Считаем УНИКАЛЬНЫЕ нарушающие сообщения по src_key (не число строк-жалоб): несколько
        # жалоб на одно сообщение ИЛИ его правка не должны раздувать страйки.
        keys = {r.get("src_key") for r in self._data["reports"].values()
                if r.get("rule_id") == rule_id and r.get("verdict") == "violation"
                and int(r.get("ts", 0)) >= since_ts and r.get("src_key")}
        return len(keys)

    def reports_page(self, *, status: str | None = None, verdict: str | None = None,
                     category: str | None = None, limit: int = 50,
                     offset: int = 0) -> dict[str, Any]:
        """Страница жалоб с фильтрами (для очереди в админ-панели). Сортировка — свежие первыми."""
        items = [dict(r) for r in self._data["reports"].values()
                 if (status is None or r.get("status") == status)
                 and (verdict is None or r.get("verdict") == verdict)
                 and (category is None or r.get("category") == category)]
        items.sort(key=lambda r: r.get("ts", 0), reverse=True)
        total = len(items)
        off = max(0, int(offset))
        lim = max(1, min(int(limit), 200))
        return {"items": items[off:off + lim], "total": total, "limit": lim, "offset": off}

    # ---------- индивидуальные переопределения аккаунта (этап 4.3) ----------
    # Пустой оверрайд (None/отсутствует) → эффективное значение = глобальный дефолт из config.
    # Явно заданный 0 — это ОВЕРРАЙД (цена 0 ₽ = комп, лимит трафика 0 = запрет медиа),
    # поэтому различаем «не задано» (None) и 0 через `is not None`, а не через truthy.
    def rule_limit_for(self, acc_id: str) -> int:
        a = self._data["accounts"].get(acc_id)
        v = a.get("rule_limit") if a else None
        return int(v) if v is not None else config.RULE_LIMIT

    def price_for(self, acc_id: str) -> int:
        a = self._data["accounts"].get(acc_id)
        v = a.get("price") if a else None
        return int(v) if v is not None else config.PRICE_RUB

    def traffic_limit_for(self, acc_id: str) -> int:
        a = self._data["accounts"].get(acc_id)
        v = a.get("traffic_limit") if a else None
        return int(v) if v is not None else config.TRAFFIC_LIMIT_BYTES

    def has_individual_tariff(self, acc_id: str) -> bool:
        return tariffs.is_individual(
            price=self.price_for(acc_id),
            rule_limit=self.rule_limit_for(acc_id),
            traffic_limit=self.traffic_limit_for(acc_id),
        )

    async def set_account_overrides(self, acc_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        """Задать/снять индивидуальные лимит правил, цену, лимит трафика. В patch присутствует
        ТОЛЬКО меняемый ключ; значение None → снять оверрайд (вернуть общий дефолт)."""
        async with self._lock:
            a = self._data["accounts"].get(acc_id)
            if a is None:
                return None
            for k in ("rule_limit", "price", "traffic_limit"):
                if k in patch:
                    v = patch[k]
                    if v is None:
                        a.pop(k, None)
                    else:
                        a[k] = int(v)
            await self._save()
            return dict(a)

    # ---------- админ-панель: поиск аккаунтов / подписок (этап 4.3) ----------
    def accounts_page(self, *, q: str = "", limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Страница аккаунтов с поиском по id / телефону / user_id идентичности."""
        query = (q or "").strip().lower()
        accs = list(self._data["accounts"].values())
        if query:
            ident_by_acc: dict[str, list[str]] = {}
            for ident, aid in self._data["identities"].items():
                ident_by_acc.setdefault(aid, []).append(ident)

            qd = "".join(c for c in query if c.isdigit())   # телефон хранится как цифры

            def _hit(a: dict[str, Any]) -> bool:
                if query in a["id"].lower():
                    return True
                if qd and qd in str(a.get("phone") or ""):   # запрос вида «+7 900 …» → цифры
                    return True
                return any(query in i.lower() for i in ident_by_acc.get(a["id"], []))
            accs = [a for a in accs if _hit(a)]
        accs.sort(key=lambda a: a.get("created_at", 0), reverse=True)
        total = len(accs)
        off, lim = max(0, int(offset)), max(1, min(int(limit), 200))
        return {"items": [dict(a) for a in accs[off:off + lim]],
                "total": total, "limit": lim, "offset": off}

    def subscriptions_page(self, *, status: str | None = None, limit: int = 50,
                           offset: int = 0) -> dict[str, Any]:
        """Страница подписок (с телефоном аккаунта) для админ-панели."""
        items = []
        for acc_id, sub in self._data["subscriptions"].items():
            if status and sub.get("status") != status:
                continue
            a = self._data["accounts"].get(acc_id) or {}
            individual = self.has_individual_tariff(acc_id)
            item = {"account_id": acc_id, "phone": a.get("phone"), **dict(sub)}
            item.update({
                "plan": tariffs.plan_id(individual, str(sub.get("plan") or tariffs.SMART_PLAN)),
                "planName": tariffs.plan_name(individual),
                "price": self.price_for(acc_id),
                "rule_limit": self.rule_limit_for(acc_id),
                "traffic_limit": self.traffic_limit_for(acc_id),
                "individual": individual,
            })
            items.append(item)
        items.sort(key=lambda s: str(s.get("renew_at") or ""), reverse=True)
        total = len(items)
        off, lim = max(0, int(offset)), max(1, min(int(limit), 200))
        return {"items": items[off:off + lim], "total": total, "limit": lim, "offset": off}

    # ---------- блокировка аккаунта (модерация, этап 4.2) ----------
    def account_blocked(self, acc_id: str) -> bool:
        a = self._data["accounts"].get(acc_id)
        return bool(a and a.get("blocked"))

    async def set_account_blocked(self, acc_id: str, blocked: bool) -> bool:
        """Пометить/снять блокировку аккаунта (доставка по его правилам останавливается —
        см. RuleDispatcher.decide). Возвращает True, если аккаунт существует."""
        async with self._lock:
            a = self._data["accounts"].get(acc_id)
            if a is None:
                return False
            if blocked:
                a["blocked"] = True
            else:
                a.pop("blocked", None)
            await self._save()
            return True

    # ---------- админ-панель: runtime-настройки + аудит (этап 4) ----------
    def settings_all(self) -> dict[str, Any]:
        """Сырые оверрайды настроек (эффективные значения считает control.settings.Settings)."""
        return dict(self._data["settings"])

    async def set_setting(self, key: str, value: Any) -> None:
        async with self._lock:
            self._data["settings"][str(key)] = value
            await self._save()

    async def add_audit(self, *, action: str, target: str | None = None,
                        details: Any = None, ip: str | None = None) -> dict[str, Any]:
        """Записать действие администратора в журнал (один админ, поэтому без actor-id)."""
        async with self._lock:
            aid = "aud_" + secrets.token_hex(6)
            rec = {"id": aid, "ts": int(time.time() * 1000), "action": action,
                   "target": target, "details": details, "ip": ip}
            self._data["admin_audit"][aid] = rec
            # Кольцевой предел: журнал не растёт бесконечно (храним последние 5000 записей).
            audit = self._data["admin_audit"]
            if len(audit) > 5000:
                for k in sorted(audit, key=lambda k: audit[k].get("ts", 0))[:len(audit) - 5000]:
                    audit.pop(k, None)
            await self._save()
            return dict(rec)

    def audit_list(self, limit: int = 200) -> list[dict[str, Any]]:
        items = [dict(r) for r in self._data["admin_audit"].values()]
        items.sort(key=lambda r: r.get("ts", 0), reverse=True)
        return items[:max(1, int(limit))]

    # ---------- лента сервисных событий (этап 4.5, ops) ----------
    # Персистентное кольцо: событие о падении задачи должно пережить рестарт (процесс
    # завершается сразу после записи). ts — в СЕКУНДАХ (как reports), не в мс как admin_audit.
    async def add_event(self, *, kind: str, title: str, detail: Any = None) -> dict[str, Any]:
        async with self._lock:
            eid = "ev_" + secrets.token_hex(6)
            rec = {"id": eid, "ts": _now(), "kind": kind, "title": title, "detail": detail}
            self._data["events"][eid] = rec
            ev = self._data["events"]
            if len(ev) > 500:
                for k in sorted(ev, key=lambda k: ev[k].get("ts", 0))[:len(ev) - 500]:
                    ev.pop(k, None)
            await self._save()
            return dict(rec)

    def events_list(self, limit: int = 100) -> list[dict[str, Any]]:
        # reversed(): порядок вставки = старое→новое; переворачиваем, затем СТАБИЛЬНО сортируем
        # по ts убыв. — так события одной секунды идут новое-сверху (гранулярность ts = секунды).
        items = [dict(r) for r in reversed(self._data["events"].values())]
        items.sort(key=lambda r: r.get("ts", 0), reverse=True)
        return items[:max(1, int(limit))]

    # ---------- рассылки в личные чаты (этап 4.6) ----------
    # Персистентная резюмируемая задача: замороженный снимок получателей + курсор, чтобы при
    # рестарте продолжить ровно с места, не пересчитывая аудиторию (иначе двойная отправка/пропуск).
    def build_broadcast_recipients(self, *, messenger: str | None = None, audience: str = "all",
                                   exclude_blocked: bool = True) -> list[list[str]]:
        """Снимок адресатов ОДНИМ проходом по identities (НЕ per-account identities_of — это был
        бы O(N²)). Возвращает [[acc_id, messenger, user_id], …] — только личные чаты (identity =
        пользователь, не источник). Аудитория: all / active (активная подписка) / trial (активная
        подписка на триале). Заблокированные аккаунты исключаются."""
        subs = self._data["subscriptions"]
        accts = self._data["accounts"]
        out: list[list[str]] = []
        for ident, acc_id in self._data["identities"].items():
            if ":" not in ident:
                continue
            m, uid = ident.split(":", 1)
            if messenger and m != messenger:
                continue
            a = accts.get(acc_id)
            if a is None:
                continue
            if exclude_blocked and a.get("blocked"):
                continue
            sub = subs.get(acc_id) or {}
            if audience == "active" and sub.get("status") != "active":
                continue
            if audience == "trial" and not (sub.get("status") == "active" and sub.get("trial")):
                continue
            out.append([acc_id, m, uid])
        return out

    async def add_broadcast(self, rec: dict[str, Any], *, if_idle: bool = False
                            ) -> dict[str, Any] | None:
        """Создать рассылку. if_idle=True — АТОМАРНО: под тем же локом отбить, если уже есть
        незавершённая (pending/running) → None (закрывает гонку двух одновременных POST)."""
        async with self._lock:
            bcasts = self._data["broadcasts"]
            if if_idle and any(r.get("status") in ("pending", "running") for r in bcasts.values()):
                return None
            bid = rec.get("id") or ("bc_" + secrets.token_hex(6))
            rec["id"] = bid
            rec.setdefault("created_at", _now())
            rec.setdefault("status", "pending")
            rec.setdefault("cursor", 0)
            rec.setdefault("sent", 0)
            rec.setdefault("failed", 0)
            rec.setdefault("total", len(rec.get("recipients") or []))
            bcasts[bid] = rec
            # Мягкий потолок истории (метаданные крошечные после снятия recipients на финале).
            if len(bcasts) > 200:
                done = [b for b, r in bcasts.items()
                        if r.get("status") in ("done", "canceled", "failed")]
                done.sort(key=lambda b: bcasts[b].get("created_at", 0))
                for b in done[:len(bcasts) - 200]:
                    bcasts.pop(b, None)
            await self._save()
            return dict(rec)

    def get_broadcast(self, bid: str) -> dict[str, Any] | None:
        r = self._data["broadcasts"].get(bid)
        return dict(r) if r else None

    async def update_broadcast(self, bid: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        async with self._lock:
            r = self._data["broadcasts"].get(bid)
            if r is None:
                return None
            r.update(patch)
            await self._save()
            return dict(r)

    def active_broadcast_ids(self) -> list[str]:
        """Id незавершённых рассылок (pending/running), старейшие раньше — для резюме при старте."""
        items = [(bid, r) for bid, r in self._data["broadcasts"].items()
                 if r.get("status") in ("pending", "running")]
        items.sort(key=lambda kv: kv[1].get("created_at", 0))
        return [bid for bid, _ in items]

    def broadcasts_page(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """История рассылок (без тяжёлого списка recipients) — новые сверху."""
        rows = [{k: v for k, v in r.items() if k != "recipients"}
                for r in self._data["broadcasts"].values()]
        rows.sort(key=lambda r: r.get("created_at", 0), reverse=True)
        total = len(rows)
        off, lim = max(0, int(offset)), max(1, min(int(limit), 200))
        return {"items": rows[off:off + lim], "total": total, "limit": lim, "offset": off}

    # ---------- трафик ----------
    def traffic(self, acc_id: str) -> dict[str, Any]:
        t = self._data["traffic"].get(acc_id) or {"used_bytes": 0, "topup_bytes": 0, "period_start": _now()}
        return dict(t)

    async def add_traffic(self, acc_id: str, n_bytes: int, rule_id: str | None = None) -> None:
        n = max(0, int(n_bytes))
        async with self._lock:
            t = self._data["traffic"].setdefault(acc_id, {"used_bytes": 0, "topup_bytes": 0, "period_start": _now()})
            before = max(0, int(t.get("used_bytes", 0)))
            after = before + n
            monthly_limit = max(0, int(self.traffic_limit_for(acc_id)))
            extra_before = max(0, before - monthly_limit)
            extra_after = max(0, after - monthly_limit)
            extra_delta = max(0, extra_after - extra_before)
            if extra_delta:
                topup = max(0, int(t.get("topup_bytes", 0)))
                t["topup_bytes"] = max(0, topup - extra_delta)
            t["used_bytes"] = after
            if rule_id:
                per = t.setdefault("per_rule", {})
                per[rule_id] = int(per.get(rule_id, 0)) + n
            await self._save()

    async def add_topup(self, acc_id: str, n_bytes: int) -> None:
        async with self._lock:
            t = self._data["traffic"].setdefault(acc_id, {"used_bytes": 0, "topup_bytes": 0, "period_start": _now()})
            t["topup_bytes"] = max(0, int(t.get("topup_bytes", 0))) + max(0, int(n_bytes))
            flags = t.get("_notified")
            if isinstance(flags, list) and "exhausted" in flags:
                t["_notified"] = [f for f in flags if f != "exhausted"]
            await self._save()

    async def reset_traffic(self, acc_id: str) -> None:
        async with self._lock:
            old = self._data["traffic"].get(acc_id) or {}
            self._data["traffic"][acc_id] = {
                "used_bytes": 0,
                "topup_bytes": max(0, int(old.get("topup_bytes", 0))),
                "period_start": _now(),
            }
            await self._save()

    def effective_traffic(self, acc_id: str) -> dict[str, int]:
        """Единая формула: месячный расход / месячный лимит / бессрочный add-on / процент.
        Тот же расчёт, что в _traffic_view (api) и гейте доставки (integration) — чтобы
        обзор, уведомления и блокировка не разошлись."""
        t = self.traffic(acc_id)
        used = max(0, int(t.get("used_bytes", 0)))
        topup = max(0, int(t.get("topup_bytes", 0)))
        limit = max(0, int(self.traffic_limit_for(acc_id)))
        included_used = min(used, limit)
        included_remaining = max(0, limit - used)
        overage = max(0, used - limit)
        percent = min(100, round(used / limit * 100)) if limit else (100 if used else 0)
        media_allowed = used < limit or topup > 0
        return {
            "used": used,
            "limit": limit,
            "topup": topup,
            "percent": percent,
            "included_used": included_used,
            "included_remaining": included_remaining,
            "overage": overage,
            "media_allowed": int(media_allowed),
        }

    def traffic_page(self, *, sort: str = "used", min_percent: int | None = None,
                     state: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Глобальный рейтинг потребителей трафика (админ-обзор). Читает только
        накопленное состояние — без сети и без обхода источников."""
        rows: list[dict[str, Any]] = []
        considered = sum_used = sum_topup = sum_overage = over80 = over100 = media_blocked = 0
        state = (state or "").strip().lower() or None
        for acc_id in list(self._data["traffic"]):
            a = self._data["accounts"].get(acc_id)
            if a is None:
                continue
            et = self.effective_traffic(acc_id)
            if et["used"] <= 0 and et["topup"] <= 0:
                continue   # запись трафика есть у всех; показываем расход или add-on баланс
            considered += 1
            sum_used += et["used"]
            sum_topup += et["topup"]
            sum_overage += et["overage"]
            if et["percent"] >= 80:
                over80 += 1
            if et["used"] > 0 and et["percent"] >= 100:   # по проценту — согласовано с фильтром min_percent
                over100 += 1
            if not et["media_allowed"]:
                media_blocked += 1
            if min_percent is not None and et["percent"] < int(min_percent):
                continue
            if state == "warn" and et["percent"] < 80:
                continue
            if state == "over" and et["percent"] < 100:
                continue
            if state == "blocked" and et["media_allowed"]:
                continue
            if state == "addon" and et["topup"] <= 0:
                continue
            rows.append({"account_id": acc_id, "phone": a.get("phone"),
                         "usedBytes": et["used"], "limitBytes": et["limit"],
                         "includedUsedBytes": et["included_used"],
                         "includedRemainingBytes": et["included_remaining"],
                         "topupBytes": et["topup"], "overageBytes": et["overage"],
                         "mediaAllowed": bool(et["media_allowed"]),
                         "percent": et["percent"]})
        if sort == "percent":
            key = lambda r: r["percent"]
        elif sort == "overage":
            key = lambda r: r["overageBytes"]
        elif sort == "topup":
            key = lambda r: r["topupBytes"]
        else:
            key = lambda r: r["usedBytes"]
        rows.sort(key=key, reverse=True)
        total = len(rows)
        off, lim = max(0, int(offset)), max(1, min(int(limit), 200))
        return {"items": rows[off:off + lim], "total": total, "limit": lim, "offset": off,
                "totals": {"sumUsed": sum_used, "count": considered,
                           "sumTopup": sum_topup, "sumOverage": sum_overage,
                           "over80": over80, "over100": over100,
                           "mediaBlocked": media_blocked}}

    async def mark_traffic_flag(self, acc_id: str, flag: str) -> None:
        """Пометить порог трафика как уже показанный (warn80/exhausted). Под lock и с
        сохранением: иначе флаг жил только в памяти до следующей записи стора — после
        рестарта пользователь получал бы дубль уведомления, а мутация без lock могла
        столкнуться с сериализацией _save в соседнем потоке."""
        async with self._lock:
            t = self._data["traffic"].setdefault(
                acc_id, {"used_bytes": 0, "topup_bytes": 0, "period_start": _now()})
            flags = t.setdefault("_notified", [])
            if flag not in flags:
                flags.append(flag)
                await self._save()

    # ---------- правила ----------
    def rules_of(self, acc_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self._data["rules"].values() if r.get("account_id") == acc_id]

    def rule(self, rule_id: str) -> dict[str, Any] | None:
        r = self._data["rules"].get(rule_id)
        return dict(r) if r else None

    def rules_filtered(self, *, q: str = "", account_id: str | None = None,
                       messenger: str | None = None, source_id: str | None = None
                       ) -> list[dict[str, Any]]:
        """Глобальный список правил (все аккаунты) под ДЕШЁВЫЕ фильтры для админ-обзора.
        Деривация статуса 'broken' и пагинация — в слое rules (после лёгкого обогащения).
        К каждому правилу приклеен телефон аккаунта (как в subscriptions_page)."""
        query = (q or "").strip().lower()
        qd = "".join(c for c in query if c.isdigit())
        out: list[dict[str, Any]] = []
        for r in self._data["rules"].values():
            aid = r.get("account_id")
            if account_id and aid != account_id:
                continue
            a, b = r.get("a") or {}, r.get("b") or {}
            if messenger and a.get("messenger") != messenger and b.get("messenger") != messenger:
                continue
            if source_id and endpoint_source_id(a) != source_id and endpoint_source_id(b) != source_id:
                continue
            phone = (self._data["accounts"].get(aid) or {}).get("phone") or ""
            if query and not (query in str(r.get("id", "")).lower() or (qd and qd in str(phone))):
                continue
            row = dict(r)
            row["phone"] = phone or None
            out.append(row)
        out.sort(key=lambda r: (int(r.get("created_at", 0)), str(r.get("id", ""))), reverse=True)
        return out

    async def add_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            rid = rule.get("id") or ("rule_" + secrets.token_hex(5))
            rule["id"] = rid
            rule.setdefault("created_at", _now())
            rule["number"] = self._alloc_rule_number(rule.get("account_id"))
            self._data["rules"][rid] = rule
            await self._save()
            return dict(rule)

    def _alloc_rule_number(self, acc_id: str | None) -> int:
        """Следующий порядковый номер правила для аккаунта: монотонный +1, который НЕ
        переиспользуется после удаления (счётчик хранится в accounts[acc_id].rules_seq и
        не опускается ниже макс. номера среди существующих правил). Вызывать под локом."""
        acc = self._data["accounts"].get(acc_id) if acc_id else None
        existing = [int(r["number"]) for r in self._data["rules"].values()
                    if r.get("account_id") == acc_id and isinstance(r.get("number"), int)]
        nxt = max([int((acc or {}).get("rules_seq", 0)), *existing], default=0) + 1
        if acc is not None:
            acc["rules_seq"] = nxt
        return nxt

    async def ensure_rule_numbers(self, acc_id: str) -> None:
        """Проставить порядковые номера правилам аккаунта, созданным ДО появления
        нумерации (по времени создания, затем по id). Идемпотентно; номера фиксируются
        на диске, поэтому далее не меняются."""
        async with self._lock:
            rules = [r for r in self._data["rules"].values() if r.get("account_id") == acc_id]
            unnumbered = [r for r in rules if not isinstance(r.get("number"), int)]
            if not unnumbered:
                return
            acc = self._data["accounts"].get(acc_id)
            numbered = [int(r["number"]) for r in rules if isinstance(r.get("number"), int)]
            seq = max([int((acc or {}).get("rules_seq", 0)), *numbered], default=0)
            for r in sorted(unnumbered, key=lambda r: (int(r.get("created_at", 0)), str(r.get("id", "")))):
                seq += 1
                r["number"] = seq
            if acc is not None:
                acc["rules_seq"] = seq
            await self._save()

    async def update_rule(self, rule_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        async with self._lock:
            r = self._data["rules"].get(rule_id)
            if not r:
                return None
            r.update(patch)
            await self._save()
            return dict(r)

    async def migrate_tg_endpoint(self, old_chat_id: Any, new_chat_id: Any) -> list[str]:
        """Перепривязать endpoint'ы правил с Telegram chat_id old→new (группа повышена до
        супергруппы — Telegram сменил id чата). Если endpoint был обычной группой без темы,
        переводим его на General (`thread_id=1`): после включения тем правило должно явно
        работать только с первой темой, а не со всем форумом. Возвращает id затронутых правил.
        Идемпотентно: повторный вызов (сигнал миграции приходит несколько раз / из обоих путей)
        вернёт []."""
        old_s, new_s = str(old_chat_id), str(new_chat_id)
        if old_s == new_s:
            return []
        async with self._lock:
            affected: list[str] = []
            for r in self._data["rules"].values():
                touched = False
                for side in ("a", "b"):
                    ep = r.get(side)
                    if (isinstance(ep, dict) and ep.get("messenger") == "tg"
                            and str(ep.get("chat_id")) == old_s):
                        ep["chat_id"] = new_s
                        if ep.get("thread_id") is None:
                            ep["thread_id"] = "1"
                        touched = True
                if touched:
                    affected.append(r["id"])
            changed = bool(affected)
            for acc_id, srcs in list(self._data["account_sources"].items()):
                if not isinstance(srcs, list):
                    continue
                migrated: list[str] = []
                for sid in srcs:
                    p = parse_source_id(sid)
                    if p and p.get("messenger") == "tg" and str(p.get("chat_id")) == old_s:
                        migrated.append(make_source_id("tg", new_s, p.get("thread_id")))
                        changed = True
                    else:
                        migrated.append(sid)
                self._data["account_sources"][acc_id] = list(dict.fromkeys(migrated))
            for rec in self._data["pending_codes"].values():
                bound = rec.get("bound")
                if not isinstance(bound, list):
                    continue
                migrated = []
                for sid in bound:
                    p = parse_source_id(sid)
                    if p and p.get("messenger") == "tg" and str(p.get("chat_id")) == old_s:
                        migrated.append(make_source_id("tg", new_s, p.get("thread_id")))
                        changed = True
                    else:
                        migrated.append(sid)
                rec["bound"] = list(dict.fromkeys(migrated))
            for sid in list(self._data["source_meta"].keys()):
                p = parse_source_id(sid)
                if p and p.get("messenger") == "tg" and str(p.get("chat_id")) == old_s:
                    nsid = make_source_id("tg", new_s, p.get("thread_id"))
                    if nsid not in self._data["source_meta"]:
                        self._data["source_meta"][nsid] = self._data["source_meta"].pop(sid)
                    else:
                        self._data["source_meta"].pop(sid, None)
                    changed = True
            if changed:
                await self._save()
            return affected

    async def set_rule_delivery_warn(self, rule_id: str, value: bool) -> bool:
        """Поднять/снять у правила флаг предупреждения о сбое доставки. Пишет на диск
        ТОЛЬКО при изменении значения — поэтому безопасно звать на каждое сообщение
        (idempotent, без лишних записей). Возвращает True, если значение изменилось."""
        async with self._lock:
            r = self._data["rules"].get(rule_id)
            if r is None or bool(r.get("delivery_warn")) == bool(value):
                return False
            if value:
                r["delivery_warn"] = True
            else:
                r.pop("delivery_warn", None)
            await self._save()
            return True

    async def delete_rule(self, rule_id: str) -> bool:
        async with self._lock:
            ok = self._data["rules"].pop(rule_id, None) is not None
            if ok:
                await self._save()
            return ok

    # ---------- метаданные источника (тон аватара, кэш названия) ----------
    def source_tone(self, source_id: str) -> str:
        meta = self._data["source_meta"].get(source_id)
        if meta and meta.get("tone"):
            return meta["tone"]
        return _tone_for(source_id)

    def cached_source_info(self, source_id: str) -> dict[str, Any]:
        """Кэш свежей инфы о чате из мессенджера: {title, title_ts, icon_url, photo_id,
        has_avatar_info}. Пустой dict — если ничего не закэшировано. has_avatar_info
        отличает «уточнили (фото может и не быть)» от «старый формат кэша без аватара»."""
        meta = self._data["source_meta"].get(source_id)
        if not meta:
            return {}
        return {"title": meta.get("title"), "title_ts": int(meta.get("title_ts", 0)),
                "icon_url": meta.get("icon_url"), "photo_id": meta.get("photo_id"),
                "has_avatar_info": ("icon_url" in meta or "photo_id" in meta)}

    async def set_source_info(self, source_id: str, *, title: str | None = None,
                              icon_url: str | None = None, photo_id: str | None = None) -> None:
        """Сохранить подтянутую из мессенджера инфу: название + идентификатор аватара.
        icon_url/photo_id пишутся ВСЕГДА (в т.ч. None = «фото нет») — чтобы по наличию
        ключа отличать «уже уточняли» от «старый кэш»; title пишется, только если задан."""
        async with self._lock:
            meta = self._data["source_meta"].setdefault(source_id, {})
            if title is not None:
                meta["title"] = title
            meta["icon_url"] = icon_url
            meta["photo_id"] = photo_id
            meta["title_ts"] = _now()
            await self._save()

    # ---------- коды привязки (инициированы из mini-app) ----------
    async def issue_code(self, acc_id: str, messenger: str | None = None) -> dict[str, Any]:
        """Один активный код привязки на АККАУНТ (1 на 10 минут, НЕЗАВИСИМО от
        мессенджера). Если активный код уже есть — возвращаем его, а не создаём новый.
        Код многоразовый в пределах TTL и принимается обоими ботами (MAX и Telegram)."""
        async with self._lock:
            purged = self._purge_codes()
            for c, v in self._data["pending_codes"].items():
                if v.get("account_id") == acc_id and v.get("expires_at", 0) > _now():
                    if purged:
                        await self._save()
                    return {"code": c, "expires_at": v["expires_at"]}
            taken = set(self._data["pending_codes"].keys())
            code = None
            for _ in range(20000):
                cand = f"{secrets.randbelow(10000):04d}"
                if cand not in taken:
                    code = cand
                    break
            if code is None:
                raise RuntimeError("Свободных кодов нет")
            rec = {"account_id": acc_id, "messenger": messenger,
                   "expires_at": _now() + config.CODE_TTL,
                   "bound": []}  # источники, привязанные этим кодом (общий код аккаунта)
            self._data["pending_codes"][code] = rec
            await self._save()
            return {"code": code, "expires_at": rec["expires_at"]}

    def active_codes(self) -> dict[str, dict[str, Any]]:
        now = _now()
        return {c: dict(v) for c, v in self._data["pending_codes"].items()
                if int(v.get("expires_at") or 0) > now}

    async def consume_code(self, code: str) -> dict[str, Any] | None:
        async with self._lock:
            rec = self._data["pending_codes"].pop(code, None)
            if rec is not None:
                await self._save()
            return rec

    async def record_code_bind(self, code: str, source_id: str) -> dict[str, Any] | None:
        """Отметить привязку источника этим кодом, НЕ удаляя код — он многоразовый
        в пределах своего TTL (10 минут), так одним кодом можно добавить несколько чатов."""
        async with self._lock:
            rec = self._data["pending_codes"].get(code)
            if not rec:
                return None
            bound = rec.setdefault("bound", [])
            if source_id and source_id not in bound:
                bound.append(source_id)
                await self._save()
            return dict(rec)

    def _purge_codes(self) -> bool:
        now = _now()
        expired = [c for c, v in self._data["pending_codes"].items()
                   if int(v.get("expires_at") or 0) <= now]
        for c in expired:
            del self._data["pending_codes"][c]
        return bool(expired)

    # ---------- OTP ----------
    async def issue_otp(self, phone: str) -> dict[str, Any]:
        async with self._lock:
            code = f"{secrets.randbelow(10000):04d}"
            rec = {"code": code, "expires_at": _now() + config.OTP_TTL, "attempts": 0, "sent_at": _now()}
            self._data["otp"][_norm_phone(phone)] = rec
            await self._save()
            return dict(rec)

    async def check_otp(self, phone: str, code: str) -> bool:
        async with self._lock:
            rec = self._data["otp"].get(_norm_phone(phone))
            if not rec or rec.get("expires_at", 0) <= _now():
                return False
            rec["attempts"] = int(rec.get("attempts", 0)) + 1
            ok = str(code) == str(rec.get("code"))
            if ok:
                self._data["otp"].pop(_norm_phone(phone), None)
            await self._save()
            return ok

    # ---------- уведомления ----------
    def notifications_of(self, acc_id: str) -> list[dict[str, Any]]:
        items = [dict(n) for n in self._data["notifications"].values() if n.get("account_id") == acc_id]
        items.sort(key=lambda n: n.get("ts", 0), reverse=True)
        return items

    async def add_notification(self, acc_id: str, *, type: str, title: str,
                               subtitle: str = "", link: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._lock:
            nid = "n_" + secrets.token_hex(5)
            rec = {"id": nid, "account_id": acc_id, "type": type, "title": title,
                   "subtitle": subtitle, "ts": int(time.time() * 1000), "read": False,
                   "link": link or {}}
            self._data["notifications"][nid] = rec
            await self._save()
            return dict(rec)

    async def mark_read(self, acc_id: str, ids: list[str] | None = None) -> None:
        """Отметить уведомления прочитанными. ids=None — все уведомления аккаунта,
        иначе — только указанные (для кнопки «Скрыть» на отдельном баннере)."""
        idset = set(ids) if ids else None
        async with self._lock:
            for n in self._data["notifications"].values():
                if n.get("account_id") == acc_id and (idset is None or n.get("id") in idset):
                    n["read"] = True
            await self._save()


def _default_subscription() -> dict[str, Any]:
    # Поля биллинга ЮKassa (см. control.billing): paid_until — точный момент истечения
    # (epoch), renew_at — ISO-дата для UI; pending — незавершённый платёж/привязка.
    return {"status": "inactive", "plan": "smart", "renew_at": None, "created_at": _now(),
            "paid_until": 0, "trial": False, "trial_used": False, "autopay": False,
            "payment_method_id": None, "payment_method_title": None,
            "pending": None, "renew_attempts": 0, "renew_retry_at": 0, "last_error": None}


def _norm_phone(phone: str | None) -> str:
    if not phone:
        return ""
    return "".join(ch for ch in str(phone) if ch.isdigit())


def _valid_phone(phone: str | None) -> bool:
    """Минимальная E.164-проверка после нормализации (без ведущего ``+``)."""
    digits = _norm_phone(phone)
    return 11 <= len(digits) <= 15


def _clean_text(value: Any, *, limit: int) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = "".join(ch for ch in text if ch.isprintable()).strip()
    return text[:limit] or None


def _clean_url(value: Any) -> str | None:
    url = str(value or "").strip()
    if not url.lower().startswith(("https://", "http://")):
        return None
    return url[:2048]


def _clean_identity_profile(messenger: str, user_id: Any, user: dict[str, Any]) -> dict[str, Any]:
    first = _clean_text(user.get("first_name"), limit=96)
    last = _clean_text(user.get("last_name"), limit=96)
    full = " ".join(p for p in (first, last) if p).strip()
    name = _clean_text(full or user.get("name") or user.get("username"), limit=128)
    username = _clean_text(user.get("username"), limit=96)
    out: dict[str, Any] = {
        "messenger": str(messenger),
        "user_id": str(user_id),
        "updated_at": _now(),
    }
    if name:
        out["name"] = name
    if username:
        out["username"] = username
    if messenger == "max":
        avatar = _clean_url(user.get("avatar_url"))
        full_avatar = _clean_url(user.get("full_avatar_url"))
        if avatar:
            out["avatar_url"] = avatar
        if full_avatar:
            out["full_avatar_url"] = full_avatar
    return out


_LEAD_STAGE_RANK = {
    "started": 10,
    "reminded": 20,
    "phone_requested": 25,   # legacy stage from the removed chat-contact fallback
    "phone_confirmed": 30,   # legacy stage from the removed chat-contact fallback
    "app_opened": 40,
    "registered": 50,
}


def _lead_stage_rank(stage: str) -> int:
    return _LEAD_STAGE_RANK.get(str(stage or ""), 0)


def _clean_lead_payload(raw: Any, *, limit: int = 128) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    return "".join(ch if ch.isprintable() and ch not in "\r\n\t" else "_" for ch in value)[:limit]


_TONES = ("av-blue", "av-green", "av-orange", "av-purple", "av-red")


def _tone_for(key: str) -> str:
    h = 0
    for ch in str(key):
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return _TONES[h % len(_TONES)]

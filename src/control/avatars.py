"""Кэш аватаров источников.

Фото чата/канала недоступно фронту напрямую (в Telegram ссылка на файл подписана
токеном бота; в MAX это публичный URL, но проксируем единообразно). Поэтому
control-API отдаёт байты сам через эндпоинт /api/sources/{id}/avatar, а тут — кэш.

Само получение байтов делает инъектируемый fetcher (есть доступ к ботам):
    fetcher(messenger, chat_id) -> (content_type, bytes) | None
None означает «у чата нет фото» — кэшируем как негативный результат, чтобы не
дёргать get_chat на каждый запрос.

Кэш на диске (data/media/avatars/):
    <key>.img   — байты картинки (только если фото есть)
    <key>.json  — мета: {"ts": <unix>, "has": bool, "ct": "image/jpeg"}
key = "<messenger>_<chat_id>" с заменой небезопасных для имени файла символов; для
версионных (content-addressed) записей к ключу добавляется "--v--<version>", и при
записи новой версии старые версии этого источника удаляются (диск не растёт).
Все обращения к диску — в пуле потоков (event loop не блокируем).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from . import config
from .source_ids import parse_source_id

log = logging.getLogger("control.avatars")

# Рядом с данными (в проде data/media/avatars; в тестах — внутри temp DATA_DIR).
CACHE_DIR: Path = Path(os.environ.get("MESYNC_AVATAR_DIR", str(config.DATA_DIR.parent / "media" / "avatars")))
# Как часто перепроверять фото у мессенджера. Час — чтобы смена/появление фото
# подтягивались «автоматически» в разумный срок (в браузере ещё кэш max-age=1ч).
TTL: int = int(os.environ.get("MESYNC_AVATAR_TTL", str(3600)))

_unsafe = re.compile(r"[^A-Za-z0-9._-]+")

# Маркер версии в имени файла кэша: его символы (дефисы/буквы) переживают _key и не
# пересекаются с заменой ':'→'_', так что версионные записи однозначно отделяются.
_VSEP = "--v--"

# fetcher(messenger, chat_id) -> (content_type, bytes[, version]) | None
# Необязательный 3-й элемент version = фактический small_file_unique_id скачанного фото
# (Telegram) для сверки с запрошенной версией; None у MAX и у старых 2-кортежных фетчеров.
Fetcher = Callable[[str, Any], Awaitable[Optional[tuple]]]


def _key(source_id: str) -> str:
    """'tg:-100123' -> 'tg_-100123' (безопасное имя файла)."""
    return _unsafe.sub("_", source_id)


def _cache_id(source_id: str, version: str | None) -> str:
    return f"{source_id}{_VSEP}{version}" if version else source_id


def _paths(source_id: str) -> tuple[Path, Path]:
    base = CACHE_DIR / _key(source_id)
    return base.with_suffix(".img"), base.with_suffix(".json")


def _evict_other_versions(source_id: str, keep_cache_id: str) -> None:
    """Удалить версионные записи кэша этого источника, кроме текущей (keep) — чтобы диск
    не рос на каждую историческую версию фото (храним только последнюю)."""
    keep = _key(keep_cache_id)
    prefix = _key(source_id) + _VSEP
    try:
        for p in CACHE_DIR.glob(prefix + "*"):
            if p.stem != keep:
                try:
                    p.unlink()
                except OSError:  # noqa: PERF203
                    pass
    except OSError:
        pass


def _write_versioned(source_id: str, write_id: str, ct: str, data: bytes) -> None:
    _write_cache(write_id, has=True, ct=ct, data=data)
    _evict_other_versions(source_id, write_id)


def _read_cache(source_id: str) -> tuple[dict[str, Any] | None, bytes | None]:
    img_path, meta_path = _paths(source_id)
    meta: dict[str, Any] | None = None
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            meta = None
    data: bytes | None = None
    if img_path.exists():
        try:
            data = img_path.read_bytes()
        except Exception:  # noqa: BLE001
            data = None
    return meta, data


def _write_cache(source_id: str, *, has: bool, ct: str = "", data: bytes | None = None) -> None:
    img_path, meta_path = _paths(source_id)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if has and data is not None:
        img_path.write_bytes(data)
    meta_path.write_text(json.dumps({"ts": int(time.time()), "has": has, "ct": ct}),
                         encoding="utf-8")


async def get_avatar(source_id: str, fetcher: Fetcher | None,
                     version: str | None = None) -> tuple[bytes, str, bool] | None:
    """Вернуть (байты, content-type, exact) аватара источника или None, если фото нет.

    exact=True — отданные байты соответствуют ЗАПРОШЕННОЙ version (ответ можно пометить
    immutable). Без version — обычный TTL-кэш под source_id, exact=False.

    С version (Telegram small_file_unique_id) кэш АДРЕСУЕТСЯ ПО СОДЕРЖИМОМУ: запись под
    ключом версии неизменна (TTL не применяется). Байты пишутся под ФАКТИЧЕСКУЮ версию
    скачанного фото (3-й элемент ответа fetcher), поэтому под ключ версии A никогда не
    попадут байты другого фото B (узкая гонка «версия из getChat №1 ≠ фото из getChat
    №2» не отравляет immutable-запись — при несовпадении exact=False, ответ не immutable).
    При сетевой ошибке отдаём устаревший кэш, если есть, иначе None.
    """
    lookup_id = _cache_id(source_id, version)
    meta, data = await asyncio.to_thread(_read_cache, lookup_id)
    now = int(time.time())
    # Версионная запись неизменна — любой существующий кэш авторитетен (без TTL).
    fresh = bool(meta) if version else (bool(meta) and (now - int(meta.get("ts", 0)) < TTL))
    if fresh:
        if meta.get("has") and data is not None:
            return data, meta.get("ct") or "image/jpeg", bool(version)
        if not meta.get("has"):
            return None
        # has=true, но файл пропал — перезапросим ниже.

    if fetcher is None:
        # Нет доступа к ботам (standalone): что есть в кэше, то и отдаём.
        if data is not None and (meta or {}).get("has"):
            return data, (meta or {}).get("ct") or "image/jpeg", bool(version)
        return None

    try:
        parsed = parse_source_id(source_id)
        if not parsed:
            return None
        res = await fetcher(parsed["messenger"], parsed["chat_id"])
    except Exception:  # noqa: BLE001
        log.warning("avatar fetch failed for %s — отдаём устаревший кэш при наличии",
                    source_id, exc_info=True)
        if data is not None and (meta or {}).get("has"):
            return data, (meta or {}).get("ct") or "image/jpeg", bool(version)
        return None

    if not res:
        await asyncio.to_thread(_write_cache, lookup_id, has=False)
        return None
    ct = res[0] or "image/jpeg"
    raw = res[1]
    actual_ver = res[2] if len(res) > 2 else None
    # exact: байты соответствуют запрошенной версии (фетчер не сообщил версию → доверяем).
    exact = bool(version) and (actual_ver is None or actual_ver == version)
    if version:
        # Пишем под ФАКТИЧЕСКУЮ версию (или запрошенную, если фетчер её не сообщил) и
        # вычищаем прочие версии этого источника.
        await asyncio.to_thread(_write_versioned, source_id,
                                _cache_id(source_id, actual_ver or version), ct, raw)
    else:
        await asyncio.to_thread(_write_cache, lookup_id, has=True, ct=ct, data=raw)
    return raw, ct, exact

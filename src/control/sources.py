"""Единый список источников поверх ownership обоих ботов.

Источник = групповой чат/канал, к которому добавлен бот и который привязан к
пользователю. Привязки живут в ownership.json каждого бота (owner = messenger
user_id). Аккаунт продукта объединяет несколько messenger-логинов, поэтому
источники аккаунта = объединение привязок по всем его идентичностям.

ID источника в API: "<messenger>:<chat_id>" для обычных чатов/каналов и
"tg:<chat_id>:<message_thread_id>" для темы Telegram-форума.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote

from . import config, security
from .source_ids import make_source_id, parse_source_id, topic_title
from .store import ControlStore

_FILES = {"max": config.MAX_OWNERSHIP_FILE, "tg": config.TG_OWNERSHIP_FILE}
_TOPIC_CACHE: dict[str, Any] = {"path": None, "mtime_ns": None, "size": None, "topics": {}}

# Как часто перезапрашивать название чата/канала из мессенджера (имя меняется редко,
# но обновление должно ощущаться «автоматическим»). Свежее имя кэшируется в source_meta.
TITLE_TTL = 300


def _avatar_url(acc_id: str, source_id: str, version: str | None = None) -> str:
    """URL фото источника через прокси с узким токеном аватара (см.
    security.make_avatar_token). version (Telegram small_file_unique_id) — ключ
    инвалидации кэша: меняется фото → меняется URL → кэш (наш и браузера) сбрасывается."""
    base = f"/api/sources/{source_id}/avatar?t={security.make_avatar_token(acc_id, source_id)}"
    return f"{base}&v={quote(str(version), safe='')}" if version else base


async def _refresh_chat_info(store: ControlStore, acc_id: str, sources: list[dict[str, Any]],
                             provider: Callable[[str, Any], Awaitable[Any]]) -> None:
    """Подтянуть свежие название и аватар источников из мессенджера (best-effort, с кэшем).

    Аватар по мессенджеру: MAX — ПРЯМАЯ публичная ссылка icon.url (или None → значок);
    Telegram — прокси-URL с версией (small_file_unique_id) для авто-инвалидации кэша
    (или None → значок). Свежий кэш (моложе TITLE_TTL) применяем сразу; устаревшее
    перезапрашиваем у provider параллельно. Ошибка/None — оставляем прежние значения.
    """
    now = int(time.time())

    def apply(s: dict[str, Any], info: dict[str, Any]) -> None:
        parsed = parse_source_id(s["id"]) or {}
        title = info.get("title")
        if title:
            thread_id = parsed.get("thread_id")
            if thread_id:
                topic_name = s.get("topicTitle") or store.cached_source_info(s["id"]).get("title")
                s["baseTitle"] = title
                s["topicTitle"] = topic_name or ("General" if str(thread_id) == "1" else f"тема {thread_id}")
                s["title"] = topic_title(title, thread_id, topic_name)
            else:
                s["title"] = title
        if s["id"].partition(":")[0] == "max":
            s["avatar"] = info.get("icon_url") or None
        else:  # tg
            pid = info.get("photo_id")
            s["avatar"] = _avatar_url(acc_id, s["id"], pid) if pid else None

    stale: list[dict[str, Any]] = []
    for s in sources:
        parsed = parse_source_id(s["id"]) or {}
        cache_id = make_source_id(parsed.get("messenger") or s["id"].partition(":")[0],
                                  parsed.get("chat_id") or s["id"].partition(":")[2])
        info = store.cached_source_info(cache_id)
        if info.get("title_ts") and (now - info["title_ts"]) < TITLE_TTL and info.get("has_avatar_info"):
            apply(s, info)
        else:
            stale.append(s)
    if not stale:
        return

    async def one(s: dict[str, Any]) -> None:
        parsed = parse_source_id(s["id"])
        if not parsed:
            return
        messenger, chat_id = parsed["messenger"], parsed["chat_id"]
        cache_id = make_source_id(messenger, chat_id)
        try:
            info = await provider(messenger, chat_id)
        except Exception:  # noqa: BLE001
            info = None
        if info is None:
            return  # ошибка/нет данных — оставляем прежние title и avatar (прокси-фоллбэк)
        if isinstance(info, str):
            # Обратная совместимость: провайдер вернул только название — обновляем имя,
            # аватар НЕ трогаем и в кэш аватара не пишем (иначе затёрли бы фото в None).
            if info:
                thread_id = parsed.get("thread_id")
                if thread_id:
                    topic_name = s.get("topicTitle") or store.cached_source_info(s["id"]).get("title")
                    s["baseTitle"] = info
                    s["topicTitle"] = topic_name or ("General" if str(thread_id) == "1" else f"тема {thread_id}")
                    s["title"] = topic_title(info, thread_id, topic_name)
                else:
                    s["title"] = info
            return
        await store.set_source_info(cache_id, title=info.get("title"),
                                    icon_url=info.get("icon_url"), photo_id=info.get("photo_id"))
        apply(s, info)

    await asyncio.gather(*(one(s) for s in stale), return_exceptions=True)


async def _read_ownership(messenger: str) -> dict[str, Any]:
    path = Path(_FILES[messenger])
    return await asyncio.to_thread(_read_json, path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"chats": {}, "owners": {}, "pending": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:  # noqa: BLE001
        pass
    return {"chats": {}, "owners": {}, "pending": {}}


def _norm_type(raw: str | None) -> str:
    return "channel" if str(raw or "").lower() == "channel" else "group"


def _status(rec: dict[str, Any]) -> tuple[str, bool]:
    rights_ok = bool(rec.get("rights_ok"))
    if rec.get("dead"):
        return "dead", rights_ok
    return ("ok", True) if rights_ok else ("err", False)


def _status_for(messenger: str, ctype: str, rec: dict[str, Any]) -> tuple[str, bool]:
    """Статус источника по модели прав мессенджера: в Telegram-группе особые права не
    нужны (всегда ok), для Telegram-канала и для MAX (групп и каналов) — по сохранённому
    rights_ok. Это и отображение, и обогащение правил берут отсюда."""
    if not rec:
        return "dead", False
    if messenger == "tg" and ctype == "group":
        return "ok", True
    return _status(rec)


def _copy_topics(topics: dict[tuple[str, str], dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {k: dict(v) for k, v in topics.items()}


async def _read_observed_tg_topics() -> dict[tuple[str, str], dict[str, Any]]:
    """Темы Telegram-форумов, которые бот уже видел в локальной истории.

    Bot API не даёт метода «перечислить все темы форума», зато в Message есть
    message_thread_id и service-события forum_topic_* с именем темы. Читаем
    нормализованный content.jsonl в отдельном потоке и кешируем по mtime/size файла.
    """
    return await asyncio.to_thread(_read_observed_tg_topics_sync, Path(config.TG_CONTENT_FILE))


def _read_observed_tg_topics_sync(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    try:
        st = path.stat()
    except FileNotFoundError:
        key = (str(path), None, None)
        if (_TOPIC_CACHE.get("path"), _TOPIC_CACHE.get("mtime_ns"), _TOPIC_CACHE.get("size")) == key:
            return _copy_topics(_TOPIC_CACHE.get("topics") or {})
        _TOPIC_CACHE.update({"path": str(path), "mtime_ns": None, "size": None, "topics": {}})
        return {}
    except Exception:  # noqa: BLE001
        return {}

    key = (str(path), st.st_mtime_ns, st.st_size)
    if (_TOPIC_CACHE.get("path"), _TOPIC_CACHE.get("mtime_ns"), _TOPIC_CACHE.get("size")) == key:
        return _copy_topics(_TOPIC_CACHE.get("topics") or {})

    topics: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(obj, dict):
                    _remember_topic_from_content(obj, topics)
    except Exception:  # noqa: BLE001
        return {}

    _TOPIC_CACHE.update({"path": str(path), "mtime_ns": st.st_mtime_ns, "size": st.st_size,
                         "topics": _copy_topics(topics)})
    return _copy_topics(topics)


def _remember_topic_from_content(obj: dict[str, Any],
                                 topics: dict[tuple[str, str], dict[str, Any]]) -> None:
    chat = obj.get("chat") if isinstance(obj.get("chat"), dict) else {}
    chat_id = chat.get("id")
    chat_type = chat.get("type")
    is_forum = bool(chat.get("is_forum"))
    thread_id = obj.get("message_thread_id")
    service = obj.get("service") if isinstance(obj.get("service"), dict) else {}

    if chat_id is None:
        return
    if thread_id is None and is_forum and chat_type == "supergroup":
        # В Telegram General может приходить как сообщение форума без явного thread id.
        thread_id = "1"
    if thread_id is None:
        # Service-события General тоже могут прийти без message_thread_id.
        if "general_forum_topic_hidden" in service or "general_forum_topic_unhidden" in service:
            thread_id = "1"
        else:
            return

    rec = _remember_topic(topics, chat_id, thread_id, base_title=chat.get("title"),
                          topic_name=("General" if str(thread_id) == "1" else None),
                          is_forum=is_forum, date=obj.get("date"))
    created = service.get("forum_topic_created")
    if isinstance(created, dict) and created.get("name"):
        rec["topic_title"] = str(created["name"])
        rec["closed"] = False
    edited = service.get("forum_topic_edited")
    if isinstance(edited, dict) and edited.get("name"):
        rec["topic_title"] = str(edited["name"])
    if "forum_topic_closed" in service or "general_forum_topic_hidden" in service:
        rec["closed"] = True
    if "forum_topic_reopened" in service or "general_forum_topic_unhidden" in service:
        rec["closed"] = False


def _remember_topic(topics: dict[tuple[str, str], dict[str, Any]], chat_id: Any, thread_id: Any, *,
                    base_title: Any = None, topic_name: Any = None, is_forum: bool = False,
                    date: Any = None) -> dict[str, Any]:
    chat_key, thread_key = str(chat_id), str(thread_id)
    key = (chat_key, thread_key)
    rec = topics.setdefault(key, {"chat_id": chat_key, "thread_id": thread_key,
                                  "topic_title": None, "base_title": None,
                                  "closed": False, "is_forum": False,
                                  "last_seen": 0})
    if base_title:
        rec["base_title"] = str(base_title)
    if topic_name:
        rec["topic_title"] = str(topic_name)
    rec["is_forum"] = bool(rec.get("is_forum")) or bool(is_forum)
    try:
        rec["last_seen"] = max(int(rec.get("last_seen") or 0), int(date or 0))
    except (TypeError, ValueError):
        pass
    return rec


def _general_topic(base_view: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_source_id(base_view.get("id", "")) or {}
    return {
        "chat_id": str(parsed.get("chat_id") or ""),
        "thread_id": "1",
        "topic_title": "General",
        "base_title": base_view.get("title"),
        "closed": False,
        "is_forum": True,
        "last_seen": 0,
    }


def _topic_source_view(store: ControlStore, acc_id: str, base: dict[str, Any],
                       info: dict[str, Any], used_count: dict[str, int]) -> dict[str, Any]:
    chat_id, thread_id = str(info["chat_id"]), str(info["thread_id"])
    sid = make_source_id("tg", chat_id, thread_id)
    topic_name = info.get("topic_title") or ("General" if str(thread_id) == "1" else f"тема {thread_id}")
    base_title = base.get("title") or info.get("base_title") or chat_id
    return {
        "id": sid,
        "messenger": "tg",
        "type": "topic",
        "title": topic_title(base_title, thread_id, topic_name),
        "baseTitle": base_title,
        "topicTitle": topic_name,
        "status": base.get("status", "ok"),
        "rightsOk": base.get("rightsOk", True),
        "tone": store.source_tone(sid),
        "avatar": base.get("avatar") or _avatar_url(acc_id, sid),
        "usedInRules": used_count.get(sid, 0),
        "threadId": thread_id,
        "baseSourceId": make_source_id("tg", chat_id),
        "observedTopic": True,
        "deletable": False,
    }


async def list_sources(store: ControlStore, acc_id: str, *,
                       title_provider: Callable[[str, Any], Awaitable[str | None]] | None = None,
                       ) -> dict[str, Any]:
    """Все источники аккаунта в формате API + счётчики.

    Если передан title_provider — названия И аватары источников автоматически
    подтягиваются из мессенджера (свежие, с кэшем): MAX — прямой icon.url, Telegram —
    прокси-URL с версией. Без него (например, при проверке владения) — сохранённые
    названия и прокси-URL аватара без версии, без сетевых запросов."""
    idents = store.identities_of(acc_id)
    by_messenger: dict[str, set[str]] = {"max": set(), "tg": set()}
    for messenger, uid in idents:
        if messenger in by_messenger:
            by_messenger[messenger].add(str(uid))

    rules = store.rules_of(acc_id)
    used_count: dict[str, int] = {}
    for r in rules:
        for ep in (r.get("a"), r.get("b")):
            if ep and ep.get("messenger") and ep.get("chat_id") is not None:
                sid = make_source_id(ep["messenger"], ep["chat_id"], ep.get("thread_id"))
                used_count[sid] = used_count.get(sid, 0) + 1

    pending = store.active_codes()
    wait_sources = {v.get("source_id") for v in pending.values() if v.get("source_id")}

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    tg_base_views: dict[str, dict[str, Any]] = {}
    tg_forum_flags: dict[str, bool] = {}
    for messenger, uids in by_messenger.items():
        if not uids:
            continue
        own = await _read_ownership(messenger)
        owners = own.get("owners", {})
        chats = own.get("chats", {})
        for chat_id, rec in owners.items():
            if str(rec.get("user_id")) not in uids:
                continue
            sid = f"{messenger}:{chat_id}"
            chat_meta = chats.get(chat_id, {})
            ctype = _norm_type(rec.get("type") or chat_meta.get("type"))
            status, rights_ok = _status_for(messenger, ctype, rec)
            if sid in wait_sources:
                status = "wait"
            seen.add(sid)
            view = {
                "id": sid,
                "messenger": messenger,
                "type": ctype,
                "title": rec.get("title") or chat_meta.get("title") or chat_id,
                "status": status,
                "rightsOk": rights_ok,
                "tone": store.source_tone(sid),
                "avatar": _avatar_url(acc_id, sid),
                "usedInRules": used_count.get(sid, 0),
                "isForum": bool(rec.get("is_forum") or chat_meta.get("is_forum")),
            }
            out.append(view)
            if messenger == "tg" and ctype == "group":
                tg_base_views[str(chat_id)] = view
                tg_forum_flags[str(chat_id)] = bool(view.get("isForum"))

    # Источники, привязанные через mini-app и связанные с АККАУНТОМ напрямую
    # (в частности каналы — у их постов нет отправителя, поэтому в ownership они
    # лежат с owner=None и не попадают в выборку по идентичностям выше).
    for sid in store.account_source_ids(acc_id):
        if sid in seen:
            continue
        src = await resolve_source(store, sid)
        if not src:
            continue
        seen.add(sid)
        view = dict(src)
        if sid in wait_sources:
            view["status"] = "wait"
        view["avatar"] = _avatar_url(acc_id, sid)
        view["usedInRules"] = used_count.get(sid, 0)
        out.append(view)
        parsed = parse_source_id(sid)
        if parsed and parsed.get("messenger") == "tg" and parsed.get("thread_id") is None \
                and view.get("type") == "group":
            chat_id = str(parsed["chat_id"])
            tg_base_views[chat_id] = view
            tg_forum_flags[chat_id] = bool(view.get("isForum"))

    # Авто-подтягивание свежих названий И аватаров из мессенджера (до сортировки).
    if title_provider is not None:
        await _refresh_chat_info(store, acc_id, out, title_provider)

    if tg_base_views:
        observed = await _read_observed_tg_topics()
        topics_by_chat: dict[str, list[dict[str, Any]]] = {}
        for info in observed.values():
            if info.get("closed"):
                continue
            chat_id = str(info.get("chat_id"))
            if chat_id in tg_base_views:
                topics_by_chat.setdefault(chat_id, []).append(info)
                if info.get("is_forum"):
                    tg_forum_flags[chat_id] = True
        for chat_id, base in tg_base_views.items():
            infos = list(topics_by_chat.get(chat_id) or [])
            if tg_forum_flags.get(chat_id) or infos:
                if all(str(x.get("thread_id")) != "1" for x in infos):
                    infos.append(_general_topic(base))
            for info in sorted(infos, key=lambda x: (str(x.get("thread_id")) != "1",
                                                     str(x.get("topic_title") or ""),
                                                     int(x.get("last_seen") or 0))):
                sid = make_source_id("tg", chat_id, info.get("thread_id"))
                if sid in seen:
                    continue
                seen.add(sid)
                out.append(_topic_source_view(store, acc_id, base, info, used_count))

    out.sort(key=lambda s: (s["status"] != "wait", s["title"]))
    counts = {"total": len(out), "wait": sum(1 for s in out if s["status"] == "wait")}
    return {"sources": out, "counts": counts}


async def resolve_source(store: ControlStore, source_id: str) -> dict[str, Any] | None:
    """Источник по его API-id (для обогащения правил). None — если не найден."""
    parsed = parse_source_id(source_id)
    if not parsed:
        return None
    messenger, chat_id = parsed["messenger"], parsed["chat_id"]
    thread_id = parsed.get("thread_id")
    if messenger not in _FILES:
        return None
    own = await _read_ownership(messenger)
    rec = own.get("owners", {}).get(chat_id)
    chat_meta = own.get("chats", {}).get(chat_id, {})
    if not rec and not chat_meta:
        return None
    rec = rec or {}
    ctype = _norm_type(rec.get("type") or chat_meta.get("type"))
    is_forum = bool(rec.get("is_forum") or chat_meta.get("is_forum"))
    status, rights_ok = _status_for(messenger, ctype, rec)
    base_title = rec.get("title") or chat_meta.get("title") \
        or store.cached_source_info(make_source_id(messenger, chat_id)).get("title") or chat_id
    title = base_title
    topic_name = None
    observed_topic = None
    synthetic_topic = False
    if thread_id is not None:
        observed = await _read_observed_tg_topics() if messenger == "tg" else {}
        observed_topic = observed.get((str(chat_id), str(thread_id)))
        synthetic_topic = bool(observed_topic) or (
            messenger == "tg" and str(thread_id) == "1"
            and (bool(rec.get("is_forum") or chat_meta.get("is_forum"))
                 or any(k[0] == str(chat_id) for k in observed))
        )
        topic_name = (observed_topic or {}).get("topic_title") \
            or store.cached_source_info(source_id).get("title")
        if not topic_name and str(thread_id) == "1":
            topic_name = "General"
        title = topic_title(base_title, thread_id, topic_name)
    return {
        "id": source_id,
        "messenger": messenger,
        "type": "topic" if thread_id is not None else ctype,
        "title": title,
        "baseTitle": base_title if thread_id is not None else None,
        "topicTitle": (topic_name or f"тема {thread_id}") if thread_id is not None else None,
        "status": status,
        "rightsOk": rights_ok,
        "tone": store.source_tone(source_id),
        "threadId": thread_id,
        "baseSourceId": make_source_id(messenger, chat_id) if thread_id is not None else None,
        "observedTopic": synthetic_topic if thread_id is not None else False,
        "deletable": False if synthetic_topic and thread_id is not None else True,
        "isForum": is_forum,
    }


async def owns_source(store: ControlStore, acc_id: str, source_id: str) -> bool:
    data = await list_sources(store, acc_id)
    return any(s["id"] == source_id for s in data["sources"])


# ---------------- админ-обзоры (этап 4.4): батч без обхода по аккаунтам ----------------
async def status_map(store: ControlStore) -> dict[str, dict[str, Any]]:
    """Доступность ВСЕХ базовых источников обоих мессенджеров ОДНИМ чтением ownership-
    файлов — без сети и без обхода по аккаунтам (замена per-endpoint resolve_source в
    админ-обзорах). Ключ — базовый source id ('max:<id>'/'tg:<id>'). Значение:
    {id, messenger, type, title, status, rightsOk, isForum, userId}. Статус — ok/err/dead
    (без 'wait': коды привязки хранят источники в bound-списке, а не как отдельный source_id,
    и «ожидает» для глобальной доски здоровья смысла не несёт)."""
    out: dict[str, dict[str, Any]] = {}
    for messenger in ("tg", "max"):
        own = await _read_ownership(messenger)
        owners = own.get("owners", {})
        chats = own.get("chats", {})
        for chat_id in set(owners) | set(chats):
            rec = owners.get(chat_id) or {}
            chat_meta = chats.get(chat_id) or {}
            if not rec and not chat_meta:
                continue
            ctype = _norm_type(rec.get("type") or chat_meta.get("type"))
            status, rights_ok = _status_for(messenger, ctype, rec)
            sid = f"{messenger}:{chat_id}"
            out[sid] = {
                "id": sid, "messenger": messenger, "type": ctype,
                "title": rec.get("title") or chat_meta.get("title")
                or store.cached_source_info(sid).get("title") or str(chat_id),
                "status": status, "rightsOk": rights_ok,
                "isForum": bool(rec.get("is_forum") or chat_meta.get("is_forum")),
                "userId": rec.get("user_id"),
            }
    return out


async def admin_list_sources(store: ControlStore, *, q: str = "", messenger: str | None = None,
                             status: str | None = None, limit: int = 50, offset: int = 0
                             ) -> dict[str, Any]:
    """Глобальная инвентаризация РАЗЛИЧНЫХ источников: здоровье + сколько правил ссылается
    + какие аккаунты владеют. Один проход по ownership (status_map), один — по правилам,
    один — по привязкам аккаунтов. Титулы — из кэша (без сети)."""
    smap = await status_map(store)
    used: dict[str, int] = {}   # base sid -> число РАЗЛИЧНЫХ правил
    for r in store.table("rules").values():
        # дедуп базовых sid внутри правила: правило между двумя темами одного форума
        # (или чат+его тема) не должно засчитываться источнику дважды.
        bases = {make_source_id(ep["messenger"], ep["chat_id"])
                 for ep in (r.get("a"), r.get("b"))
                 if ep and ep.get("messenger") and ep.get("chat_id") is not None}
        for base in bases:
            used[base] = used.get(base, 0) + 1
    # обратный индекс sid -> аккаунты: путь владельца (ownership user_id) + путь каналов
    # (account_sources: каналы лежат с owner=None и связаны напрямую с аккаунтом).
    acct_by_sid: dict[str, set[str]] = {}
    for sid, info in smap.items():
        uid = info.get("userId")
        if uid is not None:
            acc = store.find_account_by_identity(info["messenger"], uid)
            if acc:
                acct_by_sid.setdefault(sid, set()).add(acc["id"])
    for aid in list(store.table("accounts")):
        for sid in store.account_source_ids(aid):
            parsed = parse_source_id(sid) or {}
            base = make_source_id(parsed.get("messenger") or "", parsed.get("chat_id") or "")
            if base in smap:
                acct_by_sid.setdefault(base, set()).add(aid)

    query = (q or "").strip().lower()
    counts = {"total": 0, "ok": 0, "err": 0, "dead": 0}
    rows: list[dict[str, Any]] = []
    for sid, info in smap.items():
        st = info["status"]
        counts["total"] += 1
        counts[st] = counts.get(st, 0) + 1
        if messenger and info["messenger"] != messenger:
            continue
        if status and st != status:
            continue
        if query and query not in info["title"].lower() and query not in sid.lower():
            continue
        accts = sorted(acct_by_sid.get(sid, set()))
        rows.append({
            "id": sid, "messenger": info["messenger"], "type": info["type"],
            "title": info["title"], "status": st, "rightsOk": info["rightsOk"],
            "isForum": info["isForum"], "usedInRules": used.get(sid, 0),
            "accounts": [{"id": a, "phone": (store.account(a) or {}).get("phone")} for a in accts],
        })
    # сначала проблемные источники (нет прав / недоступны), затем по названию
    rows.sort(key=lambda s: (s["status"] not in ("err", "dead"), s["title"].lower()))
    total = len(rows)
    off, lim = max(0, int(offset)), max(1, min(int(limit), 200))
    return {"items": rows[off:off + lim], "total": total, "limit": lim, "offset": off,
            "counts": counts}

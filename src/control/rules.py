"""Правила маршрутизации: CRUD, обогащение из ownership, движок направления.

Правило хранит пару источников a/b ({messenger, chat_id[, thread_id]}), направление dir
(to|both|from), подпись отправителя ПО НАПРАВЛЕНИЯМ (sign_ab — поток A→B, для
получателя B; sign_ba — поток B→A, для получателя A; фоллбэк на старое единое
поле signature) и статус (active|paused). При чтении эндпоинты обогащаются из
ownership; вычисляется фактический статус правила (active|paused|broken). В лимит
тарифа (10) входят только активные правила.
"""
from __future__ import annotations

from typing import Any

from . import config, sources
from .source_ids import endpoint_source_id, make_source_id, parse_source_id, topic_title
from .store import ControlStore

def limit_text(limit: int) -> str:
    return (f"Достигнут лимит {limit} активных правил по вашему тарифу. "
            "Удалите одно, чтобы создать новое.")


class RuleError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def _raise_if_moderation_held(r: dict[str, Any]) -> None:
    if r.get("moderation_hold"):
        raise RuleError(
            "moderation_hold",
            "Правило остановлено модерацией.",
            status=409,
        )


def _parse_sid(source_id: str) -> dict[str, Any] | None:
    return parse_source_id(source_id)


def _sid(ep: dict[str, Any]) -> str:
    return endpoint_source_id(ep)


def _sid_matches(ep: dict[str, Any], sid: str) -> bool:
    """Match an endpoint against a source id.

    Exact topic ids match only the same topic. A base Telegram chat id matches all
    endpoints in that chat, including topics; this is needed for chat-level rights events.
    """
    q = parse_source_id(sid)
    if not q:
        return False
    if ep.get("messenger") != q["messenger"] or str(ep.get("chat_id")) != str(q["chat_id"]):
        return False
    if q["messenger"] == "tg" and q.get("thread_id") is not None:
        return str(ep.get("thread_id")) == str(q["thread_id"])
    return True


def _flows(a_sid: str, b_sid: str, direction: str) -> frozenset[tuple[str, str]]:
    """Множество направленных потоков правила (src→dst). to: a→b; from: b→a; both: оба.
    A→B и B→A — РАЗНЫЕ потоки (правила сосуществуют); один и тот же поток, выраженный
    по-разному ((a,b,to) и (b,a,from)), даёт одинаковый элемент."""
    if direction == "from":
        return frozenset({(b_sid, a_sid)})
    if direction == "to":
        return frozenset({(a_sid, b_sid)})
    return frozenset({(a_sid, b_sid), (b_sid, a_sid)})


def _rule_flows(r: dict[str, Any]) -> frozenset[tuple[str, str]]:
    return _flows(_sid(r["a"]), _sid(r["b"]), r.get("dir", "both"))


def rule_roles(rule: dict[str, Any], sid: str) -> set[str]:
    """Роли endpoint `sid` в правиле с учётом направления: 'source' (из него ЧИТАЕМ) и/или
    'target' (в него ПИШЕМ). Пусто, если sid не участвует в правиле. Для двустороннего правила
    общий endpoint одновременно и источник, и приёмник → {'source', 'target'}. Используется для
    проактивной реакции на смену прав бота: чату-источнику нужно право читать, приёмнику — писать."""
    a, b = rule.get("a"), rule.get("b")
    if not a or not b:
        return set()
    a_match, b_match = _sid_matches(a, sid), _sid_matches(b, sid)
    if not a_match and not b_match:
        return set()
    a_sid, b_sid = _sid(a), _sid(b)
    roles: set[str] = set()
    for src, dst in _flows(a_sid, b_sid, rule.get("dir", "both")):
        if (src == a_sid and a_match) or (src == b_sid and b_match):
            roles.add("source")
        if (dst == a_sid and a_match) or (dst == b_sid and b_match):
            roles.add("target")
    return roles


def _conflict(store: ControlStore, *, a_sid: str, b_sid: str, direction: str, acc_id: str,
              exclude_id: str | None = None) -> tuple[str | None, dict[str, Any] | None]:
    """Есть ли ГЛОБАЛЬНО (среди всех аккаунтов) правило, пересекающееся по направленному
    потоку. Источник может быть привязан к нескольким пользователям, поэтому проверка не
    ограничена своим аккаунтом. Возвращает ('self', rule) — конфликт у этого же аккаунта
    (приоритет, более точное сообщение), ('other', rule) — у другого пользователя, либо
    (None, None). A→B и B→A не пересекаются → разрешены и у одного, и у разных пользователей."""
    flows = _flows(a_sid, b_sid, direction)
    other: tuple[str, dict[str, Any]] | None = None
    for r in store.table("rules").values():
        if r.get("id") == exclude_id:
            continue
        if _rule_flows(r) & flows:
            if r.get("account_id") == acc_id:
                return "self", r
            other = ("other", r)
    return other if other else (None, None)


_DUP_SELF = "Такое правило уже существует."
_DUP_OTHER = "Такое правило уже существует у другого пользователя."


def _raise_on_conflict(store: ControlStore, *, a_sid: str, b_sid: str, direction: str,
                       acc_id: str, exclude_id: str | None = None) -> None:
    kind, _c = _conflict(store, a_sid=a_sid, b_sid=b_sid, direction=direction,
                         acc_id=acc_id, exclude_id=exclude_id)
    if kind == "self":
        raise RuleError("dup", _DUP_SELF, status=409)
    if kind == "other":
        raise RuleError("dup_other", _DUP_OTHER, status=409)


async def _enrich_endpoint(store: ControlStore, ep: dict[str, Any], acc_id: str) -> dict[str, Any]:
    sid = _sid(ep)
    # avatar — настоящее фото чата/канала через прокси (как на странице «Источники»):
    # фронт рисует его в <Avatar src>, при отсутствии фото откатывается на значок типа.
    avatar = sources._avatar_url(acc_id, sid)
    src = await sources.resolve_source(store, sid)
    if not src:
        return {"sourceId": sid, "messenger": ep["messenger"], "type": "group",
                "title": ep.get("title") or sid, "tone": store.source_tone(sid),
                "avatar": avatar, "_ok": False}
    return {"sourceId": sid, "messenger": src["messenger"], "type": src["type"],
            "title": src["title"], "tone": src["tone"], "avatar": avatar,
            "isForum": bool(src.get("isForum")), "_ok": src["status"] == "ok"}


def _rule_sign(rule: dict[str, Any], flow: str) -> bool:
    """Подпись отправителя для потока flow: 'ab' = A→B (подпись для получателя B),
    'ba' = B→A (для получателя A). Фоллбэк на старое единое поле signature — для правил,
    созданных до раздельной по направлениям подписи."""
    key = "sign_ab" if flow == "ab" else "sign_ba"
    if key in rule:
        return bool(rule[key])
    return bool(rule.get("signature"))


async def _enrich_rule(store: ControlStore, r: dict[str, Any], acc_id: str) -> dict[str, Any]:
    a = await _enrich_endpoint(store, r["a"], acc_id)
    b = await _enrich_endpoint(store, r["b"], acc_id)
    if r.get("status") == "paused":
        status = "paused"
    elif not a.pop("_ok", True) or not b.pop("_ok", True):
        status = "broken"
    else:
        status = "active"
    a.pop("_ok", None); b.pop("_ok", None)
    out = {"id": r["id"], "number": r.get("number"), "a": a, "b": b, "dir": r.get("dir", "both"),
           "signAB": _rule_sign(r, "ab"), "signBA": _rule_sign(r, "ba"), "status": status,
           "deliveryWarn": bool(r.get("delivery_warn")),
           "moderationHold": bool(r.get("moderation_hold"))}
    if status == "broken":
        out["brokenReason"] = "Источник недоступен — правило не работает"
    return out


async def list_rules(store: ControlStore, acc_id: str) -> dict[str, Any]:
    await store.ensure_rule_numbers(acc_id)   # бэкфилл номеров правилам, созданным до нумерации
    raw = store.rules_of(acc_id)
    rules = [await _enrich_rule(store, r, acc_id) for r in raw]
    rules.sort(key=lambda r: (r.get("number") or 0, r["id"]))   # по номеру = порядку создания
    active = sum(1 for r in rules if r["status"] == "active")
    return {"rules": rules, "activeCount": active, "limit": store.rule_limit_for(acc_id)}


# ---------------- админ-обзор (этап 4.4): лёгкое обогащение без сети ----------------
# Статус источника берём из батча sources.status_map (одно чтение ownership), титулы — из
# кэша; НЕ вызываем resolve_source/_enrich_rule в цикле (иначе O(N) чтений ownership).
def _admin_enrich_endpoint(store: ControlStore, ep: dict[str, Any],
                           smap: dict[str, Any]) -> dict[str, Any]:
    sid = _sid(ep)
    parsed = parse_source_id(sid) or {}
    messenger = parsed.get("messenger") or ep.get("messenger")
    chat_id = parsed.get("chat_id")
    thread_id = parsed.get("thread_id")
    base_sid = make_source_id(messenger, chat_id) if chat_id is not None else sid
    base = smap.get(base_sid)
    ok = bool(base) and base["status"] == "ok"
    if thread_id is not None:
        base_title = base["title"] if base else (ep.get("title") or sid)
        topic_name = store.cached_source_info(sid).get("title") \
            or ("General" if str(thread_id) == "1" else None)
        title = topic_title(base_title, thread_id, topic_name)
        ctype = "topic"
    else:
        title = base["title"] if base else (ep.get("title") or sid)
        ctype = base["type"] if base else "group"
    return {"sourceId": sid, "messenger": messenger, "type": ctype,
            "title": title, "tone": store.source_tone(sid), "_ok": ok}


def _admin_enrich_rule(store: ControlStore, r: dict[str, Any],
                       smap: dict[str, Any]) -> dict[str, Any]:
    a = _admin_enrich_endpoint(store, r["a"], smap)
    b = _admin_enrich_endpoint(store, r["b"], smap)
    if r.get("status") == "paused":
        status = "paused"
    elif not a["_ok"] or not b["_ok"]:
        status = "broken"
    else:
        status = "active"
    a.pop("_ok", None); b.pop("_ok", None)
    out = {"id": r["id"], "number": r.get("number"), "account_id": r.get("account_id"),
           "phone": r.get("phone"), "a": a, "b": b, "dir": r.get("dir", "both"),
           "signAB": _rule_sign(r, "ab"), "signBA": _rule_sign(r, "ba"), "status": status,
           "deliveryWarn": bool(r.get("delivery_warn")),
           "moderationHold": bool(r.get("moderation_hold")),
           "reportMuted": bool(r.get("report_muted"))}
    if status == "broken":
        out["brokenReason"] = "Источник недоступен — правило не работает"
    return out


async def admin_rules_page(store: ControlStore, *, q: str = "", account_id: str | None = None,
                           status: str | None = None, messenger: str | None = None,
                           source_id: str | None = None, limit: int = 100, offset: int = 0
                           ) -> dict[str, Any]:
    """Глобальный список правил всех аккаунтов + KPI. Статус ('broken') деривуется после
    лёгкого обогащения, поэтому фильтр по статусу и пагинация — здесь, а не в store."""
    raw = store.rules_filtered(q=q, account_id=account_id, messenger=messenger, source_id=source_id)
    smap = await sources.status_map(store)
    enriched = [_admin_enrich_rule(store, r, smap) for r in raw]
    stats = {"total": len(enriched), "active": 0, "paused": 0, "broken": 0}
    for e in enriched:
        stats[e["status"]] = stats.get(e["status"], 0) + 1
    if status in ("active", "paused", "broken"):
        enriched = [e for e in enriched if e["status"] == status]
    total = len(enriched)
    off, lim = max(0, int(offset)), max(1, min(int(limit), 200))
    return {"items": enriched[off:off + lim], "total": total, "limit": lim,
            "offset": off, "stats": stats}


async def admin_rule_view(store: ControlStore, rule_id: str) -> dict[str, Any] | None:
    r = store.rule(rule_id)
    if not r:
        return None
    r = dict(r)
    r["phone"] = (store.account(r.get("account_id")) or {}).get("phone")
    smap = await sources.status_map(store)
    return _admin_enrich_rule(store, r, smap)


async def create_rule(store: ControlStore, acc_id: str, *, a_id: str, b_id: str,
                      direction: str = "both", sign_ab: bool = False,
                      sign_ba: bool = False) -> dict[str, Any]:
    a = _parse_sid(a_id); b = _parse_sid(b_id)
    if not a or not b:
        raise RuleError("required", "Выберите оба источника.")
    if a_id == b_id:
        raise RuleError("same", "Источники должны быть разными.")
    if not await sources.owns_source(store, acc_id, a_id) or not await sources.owns_source(store, acc_id, b_id):
        raise RuleError("not_owned", "Источник недоступен, выберите другой")
    if direction not in ("to", "both", "from"):
        direction = "both"
    # Уникальность ГЛОБАЛЬНАЯ (источник может быть привязан к нескольким пользователям) и
    # ПО НАПРАВЛЕНИЮ потока: A→B и B→A — разные правила.
    _raise_on_conflict(store, a_sid=a_id, b_sid=b_id, direction=direction, acc_id=acc_id)
    enriched = await list_rules(store, acc_id)
    lim = enriched["limit"]   # эффективный лимит аккаунта (индивидуальный оверрайд или дефолт)
    if enriched["activeCount"] >= lim:
        raise RuleError("limit", limit_text(lim), status=409)
    rule = await store.add_rule({"account_id": acc_id, "a": a, "b": b, "dir": direction,
                                 "sign_ab": bool(sign_ab), "sign_ba": bool(sign_ba), "status": "active"})
    return await _enrich_rule(store, rule, acc_id)


async def update_rule(store: ControlStore, acc_id: str, rule_id: str, patch: dict[str, Any],
                      *, allow_moderation_hold: bool = False) -> dict[str, Any]:
    r = store.rule(rule_id)
    if not r or r.get("account_id") != acc_id:
        raise RuleError("not_found", "Правило не найдено", status=404)
    if not allow_moderation_hold:
        _raise_if_moderation_held(r)
    clean: dict[str, Any] = {}
    if "dir" in patch and patch["dir"] in ("to", "both", "from"):
        clean["dir"] = patch["dir"]
    if "signAB" in patch:
        clean["sign_ab"] = bool(patch["signAB"])
    if "signBA" in patch:
        clean["sign_ba"] = bool(patch["signBA"])
    # back-compat: единое signature (без раздельных) применяем к обоим направлениям
    if "signature" in patch and "signAB" not in patch and "signBA" not in patch:
        clean["sign_ab"] = clean["sign_ba"] = bool(patch["signature"])
    if "status" in patch and patch["status"] in ("active", "paused"):
        clean["status"] = patch["status"]
    for slot in ("a", "b"):
        key = f"{slot}_id"
        if patch.get(key):
            ep = _parse_sid(patch[key])
            if ep and await sources.owns_source(store, acc_id, patch[key]):
                clean[slot] = ep
    # Изменение направления/источников не должно создавать дубль (глобально, по потоку;
    # исключая само правило).
    if "dir" in clean or "a" in clean or "b" in clean:
        a_ep = clean.get("a", r["a"]); b_ep = clean.get("b", r["b"])
        d = clean.get("dir", r.get("dir", "both"))
        _raise_on_conflict(store, a_sid=_sid(a_ep), b_sid=_sid(b_ep), direction=d,
                           acc_id=acc_id, exclude_id=rule_id)
    updated = await store.update_rule(rule_id, clean)
    return await _enrich_rule(store, updated, acc_id)


async def set_status(store: ControlStore, acc_id: str, rule_id: str, status: str,
                     *, allow_moderation_hold: bool = False) -> dict[str, Any]:
    if status not in ("active", "paused"):
        raise RuleError("bad_status", "Неверный статус")
    return await update_rule(store, acc_id, rule_id, {"status": status},
                             allow_moderation_hold=allow_moderation_hold)


async def delete_rule(store: ControlStore, acc_id: str, rule_id: str) -> bool:
    r = store.rule(rule_id)
    if not r or r.get("account_id") != acc_id:
        raise RuleError("not_found", "Правило не найдено", status=404)
    return await store.delete_rule(rule_id)


async def dismiss_warning(store: ControlStore, acc_id: str, rule_id: str,
                          *, allow_moderation_hold: bool = False) -> dict[str, Any]:
    """«Скрыть» баннер предупреждения о сбое доставки. Снимает флаг до следующего
    сбоя (при новой серии сбоев диспетчер поставит его снова)."""
    r = store.rule(rule_id)
    if not r or r.get("account_id") != acc_id:
        raise RuleError("not_found", "Правило не найдено", status=404)
    if not allow_moderation_hold:
        _raise_if_moderation_held(r)
    await store.set_rule_delivery_warn(rule_id, False)
    return await _enrich_rule(store, store.rule(rule_id), acc_id)


# ---------------- движок: цели для входящего сообщения ----------------
def targets_for(store: ControlStore, messenger: str, chat_id: Any,
                thread_id: Any | None = None) -> list[dict[str, Any]]:
    """Куда переслать сообщение из (messenger, chat_id[, thread_id]) по активным правилам.

    Возвращает [{messenger, chat_id[, thread_id], signature, rule_id, account_id}].
    Учитывает направление; правила на паузе игнорируются. Подписка/трафик
    проверяются в диспетчере (integration), не здесь.
    """
    src_sids = [make_source_id(messenger, chat_id, thread_id)]
    if messenger == "tg" and thread_id is not None:
        src_sids.append(make_source_id("tg", chat_id))  # legacy whole-chat rules still see topic messages
    elif messenger == "tg":
        # Сообщения General в Telegram-форумах могут приходить без message_thread_id.
        # Правило на tg:<chat_id>:1 считаем точным правилом на General.
        src_sids.append(make_source_id("tg", chat_id, "1"))
    out: list[dict[str, Any]] = []
    for r in store.table("rules").values():
        if r.get("status") != "active":
            continue
        a, b, d = r.get("a"), r.get("b"), r.get("dir", "both")
        if not a or not b:
            continue
        a_sid, b_sid = _sid(a), _sid(b)
        if a_sid in src_sids and d in ("to", "both"):
            out.append(_target(b, r, "ab"))     # поток A→B: подпись sign_ab
        elif b_sid in src_sids and d in ("from", "both"):
            out.append(_target(a, r, "ba"))     # поток B→A: подпись sign_ba
    return out


def _target(ep: dict[str, Any], rule: dict[str, Any], flow: str) -> dict[str, Any]:
    out = {"messenger": ep["messenger"], "chat_id": ep["chat_id"],
           "signature": _rule_sign(rule, flow), "rule_id": rule["id"],
           "account_id": rule.get("account_id")}
    if ep.get("messenger") == "tg" and ep.get("thread_id") is not None:
        out["thread_id"] = ep["thread_id"]
    return out

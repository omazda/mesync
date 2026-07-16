"""Тесты рассылок в личные чаты (этап 4.6): построение аудитории (снимок identities),
воркер Broadcaster (отправка/троттлинг/резюме по курсору/отмена), admin-API + инвариант
«только личка» + аудит.

Запуск:  .venv/bin/python -m pytest tests/test_admin_broadcasts.py -q
"""
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="admbc_"))
os.environ.setdefault("MESYNC_DATA_DIR", str(_TMP / "control"))
os.environ.setdefault("MESYNC_SESSION_SECRET", "test-secret")
os.environ.setdefault("MESYNC_AUTH_INSECURE", "1")
os.environ.setdefault("MESYNC_ADMIN_PASSWORD", "pw")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "111:TESTTOKEN")
os.environ.setdefault("MAX_BOT_TOKEN", "maxtoken")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control import config  # noqa: E402
from control.broadcasts import Broadcaster  # noqa: E402
from control.settings import Settings  # noqa: E402
from control.store import ControlStore  # noqa: E402

run = asyncio.run


def _fixture():
    """3 аккаунта: a1 (max+tg, активная подписка), a2 (tg, истёкшая), a3 (max, активный триал),
    b (max, заблокирован)."""
    s = ControlStore(_TMP / f"bc_{time.time_ns()}.json")
    a1 = run(s.get_or_create_account("max", 10, "79990001111"))["id"]
    run(s.link_identity("tg", 11, a1))
    run(s.set_subscription(a1, {"status": "active", "trial": False}))
    a2 = run(s.get_or_create_account("tg", 20, "79990002222"))["id"]
    run(s.set_subscription(a2, {"status": "inactive"}))
    a3 = run(s.get_or_create_account("max", 30, "79990003333"))["id"]
    run(s.set_subscription(a3, {"status": "active", "trial": True}))
    b = run(s.get_or_create_account("max", 40, None))["id"]
    run(s.set_account_blocked(b, True))
    return s, a1, a2, a3, b


# ================= аудитория =================
def test_build_recipients_filters():
    s, a1, a2, a3, b = _fixture()
    allr = s.build_broadcast_recipients()
    # a1(max,tg) + a2(tg) + a3(max) = 4 личных адресата; b исключён (заблокирован)
    assert len(allr) == 4
    assert all(len(r) == 3 for r in allr)
    assert not any(r[0] == b for r in allr)                       # заблокированный исключён
    active = s.build_broadcast_recipients(audience="active")      # a1(2) + a3(1, триал тоже active)
    assert {r[0] for r in active} == {a1, a3}
    trial = s.build_broadcast_recipients(audience="trial")        # только a3
    assert {r[0] for r in trial} == {a3}
    tg_only = s.build_broadcast_recipients(messenger="tg")        # a1(tg) + a2(tg)
    assert {(r[0], r[1]) for r in tg_only} == {(a1, "tg"), (a2, "tg")}


# ================= воркер =================
class FakeSend:
    def __init__(self, fail_uids=()):
        self.calls = []
        self.fail = set(fail_uids)

    async def __call__(self, m, uid, text):
        if uid in self.fail:
            raise RuntimeError("blocked user")
        self.calls.append((m, uid, text))
        return {"ok": True}


def _fast_settings(s):
    st = Settings(s)
    run(st.set("broadcast_rate_limit", 30))   # быстрее в тестах (delay ~33мс)
    return st


def test_worker_sends_all_and_counts_failures():
    s, a1, a2, a3, b = _fixture()
    recips = s.build_broadcast_recipients()
    rec = run(s.add_broadcast({"text": "привет", "audience": "all", "messenger": "both",
                               "recipients": recips, "total": len(recips)}))
    send = FakeSend(fail_uids={"20"})          # tg:20 «заблокировал бота»
    bc = Broadcaster(s, send=send, settings=_fast_settings(s))
    run(bc._process(rec["id"]))
    done = s.get_broadcast(rec["id"])
    assert done["status"] == "done" and done["sent"] == 3 and done["failed"] == 1
    assert len(send.calls) == 3                # доставлено всем, кроме сбойного
    # ВСЕ адресаты — личные user_id (из identities), НИ ОДНОГО chat_id источника
    sent_uids = {c[1] for c in send.calls}
    assert sent_uids <= {"10", "11", "30"}


def test_worker_none_send_counts_failed():
    # notifier вернул None (клиент мессенджера не сконфигурирован) → НЕ доставлено = failed,
    # иначе рапортовали бы «100% доставлено» при нуле отправок.
    s, *_ = _fixture()
    recips = s.build_broadcast_recipients()
    rec = run(s.add_broadcast({"text": "t", "audience": "all", "messenger": "both",
                               "recipients": recips, "total": len(recips)}))

    async def none_send(m, uid, text):
        return None
    bc = Broadcaster(s, send=none_send, settings=_fast_settings(s))
    run(bc._process(rec["id"]))
    done = s.get_broadcast(rec["id"])
    assert done["status"] == "done" and done["sent"] == 0 and done["failed"] == 4


def test_add_broadcast_if_idle_is_atomic():
    s, *_ = _fixture()
    run(s.add_broadcast({"text": "a", "recipients": [["x", "max", "1"]], "total": 1}))  # активная
    second = run(s.add_broadcast({"text": "b", "recipients": [["y", "max", "2"]], "total": 1},
                                 if_idle=True))
    assert second is None                          # атомарно отбито (гонки нет)
    assert len(s.active_broadcast_ids()) == 1


def test_recipients_stripped_on_terminal():
    s, *_ = _fixture()
    recips = s.build_broadcast_recipients()
    rec = run(s.add_broadcast({"text": "t", "audience": "all", "messenger": "both",
                               "recipients": recips, "total": len(recips)}))
    assert s.get_broadcast(rec["id"])["recipients"]           # пока есть (для резюме)
    run(Broadcaster(s, send=FakeSend(), settings=_fast_settings(s))._process(rec["id"]))
    assert s.get_broadcast(rec["id"])["recipients"] == []     # снят на финале (экономия стора)


def test_worker_resumes_from_cursor():
    s, *_ = _fixture()
    recips = s.build_broadcast_recipients()    # 4 адресата
    rec = run(s.add_broadcast({"text": "t", "audience": "all", "messenger": "both",
                               "recipients": recips, "total": len(recips)}))
    run(s.update_broadcast(rec["id"], {"status": "running", "cursor": 2, "sent": 2}))  # «уже отправлено 2»
    send = FakeSend()
    bc = Broadcaster(s, send=send, settings=_fast_settings(s))
    run(bc._process(rec["id"]))
    assert len(send.calls) == 2                # только оставшиеся 2 (резюме по курсору)
    assert s.get_broadcast(rec["id"])["sent"] == 4


def test_worker_cancel_stops_at_checkpoint():
    s, *_ = _fixture()
    recips = [[f"acc{i}", "max", str(i)] for i in range(10)]   # синтетические 10 адресатов
    rec = run(s.add_broadcast({"text": "t", "audience": "all", "messenger": "max",
                               "recipients": recips, "total": len(recips)}))
    send = FakeSend()
    bc = Broadcaster(s, send=send, settings=_fast_settings(s), checkpoint=3)

    # отменяем после того, как воркер уже что-то отправил: обёртка помечает отмену на 4-м send
    orig = send.__call__

    async def wrapped(m, uid, text):
        r = await orig(m, uid, text)
        if len(send.calls) == 4:
            run_no = s._data["broadcasts"][rec["id"]]
            run_no["status"] = "canceled"       # прямая пометка (эмулируем отмену из API)
        return r
    send.__call__ = wrapped  # type: ignore
    bc._send = wrapped
    run(bc._process(rec["id"]))
    done = s.get_broadcast(rec["id"])
    assert done["status"] == "canceled"
    assert len(send.calls) < 10                 # остановились до конца
    assert len(send.calls) >= 4


# ================= admin-API =================
def _client(s, *, with_worker=True):
    from fastapi.testclient import TestClient
    from control.api import create_app, set_settings, set_broadcaster
    config.ADMIN_PASSWORD = "pw"
    config.AUTH_INSECURE = True
    set_settings(Settings(s))
    set_broadcaster(Broadcaster(s, send=FakeSend(), settings=Settings(s)) if with_worker else None)
    c = TestClient(create_app(s))
    assert c.post("/api/admin/login", json={"password": "pw"}).status_code == 200
    return c


def test_bc_preview_and_create_flow():
    s, a1, a2, a3, b = _fixture()
    c = _client(s)
    prev = c.post("/api/admin/broadcasts/preview", json={"audience": "active", "messenger": "both"}).json()
    assert prev["count"] == 3                    # a1(2)+a3(1)
    # пустой текст / без подтверждения — 400
    assert c.post("/api/admin/broadcasts", json={"text": "", "confirm": True}).status_code == 400
    assert c.post("/api/admin/broadcasts", json={"text": "hi"}).status_code == 400
    # создание
    r = c.post("/api/admin/broadcasts", json={"text": "Всем привет", "audience": "all",
                                              "messenger": "both", "confirm": True})
    assert r.status_code == 200
    bid = r.json()["broadcast"]["id"]
    assert "recipients" not in r.json()["broadcast"] and r.json()["broadcast"]["total"] == 4
    # пока активна — вторая создаётся с 409
    assert c.post("/api/admin/broadcasts", json={"text": "ещё", "confirm": True}).status_code == 409
    # список/деталь
    assert c.get("/api/admin/broadcasts").json()["total"] >= 1
    assert c.get(f"/api/admin/broadcasts/{bid}").json()["broadcast"]["id"] == bid
    assert c.get("/api/admin/broadcasts/nope").status_code == 404
    # отмена
    assert c.post(f"/api/admin/broadcasts/{bid}/action", json={"action": "cancel"}).status_code == 200
    assert s.get_broadcast(bid)["status"] == "canceled"
    # аудит
    actions = [i["action"] for i in c.get("/api/admin/audit").json()["items"]]
    assert "broadcast_create" in actions and "broadcast_cancel" in actions


def test_bc_no_recipients_and_unavailable():
    s, *_ = _fixture()
    c = _client(s)
    # аудитория без адресатов → 400 (у нас нет trial-аккаунтов после блокировки? есть a3 — берём messenger tg+trial)
    r = c.post("/api/admin/broadcasts", json={"text": "x", "audience": "trial",
                                              "messenger": "tg", "confirm": True})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "no_recipients"  # a3 только в max
    # без воркера → 503
    c2 = _client(s, with_worker=False)
    assert c2.post("/api/admin/broadcasts", json={"text": "x", "confirm": True}).status_code == 503

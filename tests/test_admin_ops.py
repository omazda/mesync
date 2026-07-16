"""Тесты ops-обзора админ-панели (этап 4.5): эндпоинт /api/admin/ops (живость ботов,
очередь жалоб, метрики, лента событий), кольцо events, мягкая деградация без инжектов.

Запуск:  .venv/bin/python -m pytest tests/test_admin_ops.py -q
"""
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="admops_"))
os.environ.setdefault("MESYNC_DATA_DIR", str(_TMP / "control"))
os.environ.setdefault("MESYNC_SESSION_SECRET", "test-secret")
os.environ.setdefault("MESYNC_AUTH_INSECURE", "1")
os.environ.setdefault("MESYNC_ADMIN_PASSWORD", "pw")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "111:TESTTOKEN")
os.environ.setdefault("MAX_BOT_TOKEN", "maxtoken")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control import config  # noqa: E402
from control.health import BotHealth  # noqa: E402
from control.store import ControlStore  # noqa: E402

run = asyncio.run


class FakeReports:
    def stats(self):
        return {"running": True, "depth": 3, "persistedDepth": 3, "inflight": True,
                "processedTotal": 42, "errorTotal": 2, "lastProcessedTs": 1000.0,
                "paused": False, "pausedUntil": None}


def _store():
    s = ControlStore(_TMP / f"ops_{time.time_ns()}.json")
    a1 = run(s.get_or_create_account("max", 10, "79990001111"))["id"]
    a2 = run(s.get_or_create_account("tg", 20, "79990002222"))["id"]
    run(s.set_subscription(a1, {"status": "active"}))
    run(s.set_subscription(a2, {"status": "inactive"}))
    run(s.add_rule({"account_id": a1, "a": {"messenger": "max", "chat_id": "100"},
                    "b": {"messenger": "tg", "chat_id": "200"}, "dir": "both", "status": "active"}))
    run(s.add_traffic(a1, 5000))
    return s, a1, a2


def _client(s, *, health=True, reports=True):
    from fastapi.testclient import TestClient
    from control.api import create_app, set_settings, set_health, set_reports
    from control.settings import Settings
    config.ADMIN_PASSWORD = "pw"
    config.AUTH_INSECURE = True
    set_settings(Settings(s))
    if health:
        h = BotHealth()
        h.mark_started("max", bot_id=7, username="test_bot", poll_timeout=30)
        h.channel("max").poll()
        h.mark_started("tg", bot_id=8, username="mesynctg", poll_timeout=30)
        set_health(h)
    else:
        set_health(None)
    set_reports(FakeReports() if reports else None)
    c = TestClient(create_app(s))
    assert c.post("/api/admin/login", json={"password": "pw"}).status_code == 200
    return c


# ================= лента событий (кольцо) =================
def test_events_ring_and_order():
    s = ControlStore(_TMP / f"ev_{time.time_ns()}.json")
    run(s.add_event(kind="info", title="Первое"))
    run(s.add_event(kind="crash", title="Падение задачи reports-worker", detail="RuntimeError: x"))
    items = s.events_list(limit=10)
    assert len(items) == 2 and items[0]["title"].startswith("Падение")   # свежее сверху
    assert items[0]["kind"] == "crash" and "ts" in items[0]


def test_events_ring_evicts_oldest():
    # Вытеснение инкрементально роняет по одному старейшему (равный ts → стабильно по порядку
    # вставки), поэтому первые 20 из 520 вытесняются, последние 500 остаются.
    s = ControlStore(_TMP / f"evc_{time.time_ns()}.json")
    for i in range(520):
        run(s.add_event(kind="info", title=f"e{i}", detail=i))
    assert len(s.table("events")) == 500                  # кольцо держит потолок
    kept = {e["detail"] for e in s.events_list(limit=1000)}
    assert 519 in kept and 20 in kept and 19 not in kept  # новейшие есть, старейшие вытеснены


# ================= эндпоинт /api/admin/ops =================
def test_ops_requires_auth():
    from fastapi.testclient import TestClient
    from control.api import create_app, set_settings
    from control.settings import Settings
    s, _, _ = _store()
    set_settings(Settings(s))
    assert TestClient(create_app(s)).get("/api/admin/ops").status_code == 401


def test_ops_full_shape():
    s, a1, a2 = _store()
    run(s.add_event(kind="quota_pause", title="Пауза очереди жалоб: квота ИИ исчерпана"))
    c = _client(s)
    ops = c.get("/api/admin/ops").json()
    # живость ботов
    assert ops["bots"]["max"]["state"] == "online" and ops["bots"]["max"]["username"] == "test_bot"
    assert ops["bots"]["tg"]["state"] in ("online", "stalled")   # tg стартовал, но без poll
    # очередь жалоб
    assert ops["queues"]["reports"]["depth"] == 3 and ops["queues"]["reports"]["inflight"] is True
    # метрики
    m = ops["metrics"]
    assert m["accounts"] == 2 and m["accounts24h"] == 2
    assert m["subs"]["active"] == 1 and m["subs"]["inactive"] == 1
    assert m["rules"] == 1
    assert m["traffic"]["sumUsed"] == 5000
    assert "total" in m["codes"] and "queued" in m["reports"]
    # лента событий
    assert any(e["kind"] == "quota_pause" for e in ops["events"])
    assert ops["paymentsPaused"] is False


def test_ops_degrades_without_injections():
    # Без BotHealth / Reports эндпоинт всё равно отвечает 200 частичными данными.
    s, _, _ = _store()
    c = _client(s, health=False, reports=False)
    ops = c.get("/api/admin/ops").json()
    assert ops["bots"] == {} and ops["queues"]["reports"] is None
    assert ops["metrics"]["accounts"] == 2   # метрики из стора доступны всегда

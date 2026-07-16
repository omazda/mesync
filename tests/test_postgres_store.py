"""PostgreSQL lifecycle и миграция JSON-состояния ControlStore."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control import config  # noqa: E402
from control.api import create_app  # noqa: E402
from control.store import ControlStore  # noqa: E402
import control.store as store_module  # noqa: E402


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _FakeConnection:
    def __init__(self, pool):
        self.pool = pool

    def transaction(self):
        return _FakeTransaction()

    async def execute(self, query, *args):
        self.pool.queries.append(query)
        if "INSERT INTO mesync_control_state" in query and args:
            self.pool.payload = json.loads(args[0])

    async def fetchval(self, query, *args):
        self.pool.queries.append(query)
        if "INSERT INTO mesync_control_state" in query:
            if self.pool.payload is None:
                self.pool.payload = json.loads(args[0])
                return 1
            return None
        if "SELECT payload" in query:
            return (json.dumps(self.pool.payload, ensure_ascii=False)
                    if self.pool.payload is not None else None)
        raise AssertionError(f"Unexpected query: {query}")


class _FakeAcquire:
    def __init__(self, pool):
        self.connection = _FakeConnection(pool)

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _FakePool:
    def __init__(self, payload=None):
        self.payload = payload
        self.queries = []
        self.closed = False
        self.healthy = True

    def acquire(self):
        return _FakeAcquire(self)

    async def execute(self, query, payload):
        self.queries.append(query)
        self.payload = json.loads(payload)

    async def fetchval(self, query):
        self.queries.append(query)
        if not self.healthy:
            raise RuntimeError("database unavailable")
        return 1

    async def close(self):
        self.closed = True


def _pool_factory(monkeypatch, pool):
    calls = []

    async def create_pool(**options):
        calls.append(options)
        return pool

    monkeypatch.setattr(store_module, "_create_postgres_pool", create_pool)
    return calls


def _state(**tables):
    data = {name: {} for name in store_module._TABLES}
    data.update(tables)
    return data


def test_empty_postgres_is_seeded_from_json_and_receives_saves(tmp_path, monkeypatch):
    state_file = tmp_path / "control.json"
    state_file.write_text(json.dumps({
        "accounts": {"acc_old": {"id": "acc_old", "phone": "79990000000"}},
        "identities": {"tg:1": "acc_old"},
    }), encoding="utf-8")
    pool = _FakePool()
    calls = _pool_factory(monkeypatch, pool)

    async def scenario():
        store = ControlStore(state_file, database_url="postgresql://db/mesync")
        assert store.backend == "postgresql"
        await store.start()
        assert store.account("acc_old")["phone"] == "79990000000"
        created = await store.get_or_create_account("max", 2, "79991112233")
        assert pool.payload["identities"]["max:2"] == created["id"]
        backup = json.loads(await store.export_backup())
        assert set(backup) == set(store_module._TABLES)
        assert backup["identities"]["max:2"] == created["id"]
        await store.close()

    asyncio.run(scenario())
    assert calls == [{"dsn": "postgresql://db/mesync"}]
    assert pool.closed is True
    # PostgreSQL становится источником правды; файл остаётся снимком на момент миграции.
    assert "max:2" not in json.loads(state_file.read_text(encoding="utf-8"))["identities"]


def test_existing_postgres_state_wins_over_json_seed(tmp_path, monkeypatch):
    state_file = tmp_path / "control.json"
    state_file.write_text(json.dumps({
        "accounts": {"acc_file": {"id": "acc_file"}},
    }), encoding="utf-8")
    pool = _FakePool({
        "accounts": {"acc_db": {"id": "acc_db", "phone": "78880000000"}},
        "identities": {"tg:9": "acc_db"},
    })
    calls = _pool_factory(monkeypatch, pool)

    async def scenario():
        store = ControlStore(state_file, database_url="postgresql://db/mesync")
        await store.start()
        await store.start()  # lifecycle идемпотентен
        assert store.account("acc_file") is None
        assert store.account("acc_db")["phone"] == "78880000000"
        assert store.table("rules") == {}
        await store.close()

    asyncio.run(scenario())
    assert len(calls) == 1


def test_corrupt_json_cannot_seed_empty_postgres(tmp_path, monkeypatch):
    state_file = tmp_path / "control.json"
    state_file.write_text("{broken", encoding="utf-8")
    pool = _FakePool()
    _pool_factory(monkeypatch, pool)

    async def scenario():
        store = ControlStore(state_file, database_url="postgresql://db/mesync")
        try:
            await store.start()
        except RuntimeError as exc:
            assert "Cannot initialize PostgreSQL from unreadable" in str(exc)
        else:
            raise AssertionError("corrupt migration source must fail")

    asyncio.run(scenario())
    assert pool.payload is None
    assert pool.closed is True


def test_invalid_table_shape_cannot_seed_empty_postgres(tmp_path, monkeypatch):
    state_file = tmp_path / "control.json"
    state_file.write_text(json.dumps({"accounts": None}), encoding="utf-8")
    pool = _FakePool()
    _pool_factory(monkeypatch, pool)

    async def scenario():
        store = ControlStore(state_file, database_url="postgresql://db/mesync")
        try:
            await store.start()
        except RuntimeError as exc:
            assert "Cannot initialize PostgreSQL from unreadable" in str(exc)
        else:
            raise AssertionError("invalid migration table must fail")

    asyncio.run(scenario())
    assert pool.payload is None
    assert pool.closed is True


def test_existing_postgres_ignores_stale_corrupt_json(tmp_path, monkeypatch):
    state_file = tmp_path / "control.json"
    state_file.write_text("{broken", encoding="utf-8")
    pool = _FakePool({"accounts": {"acc_db": {"id": "acc_db"}}})
    _pool_factory(monkeypatch, pool)

    async def scenario():
        store = ControlStore(state_file, database_url="postgresql://db/mesync")
        await store.start()
        assert store.account("acc_db") == {"id": "acc_db"}
        await store.close()

    asyncio.run(scenario())
    assert pool.closed is True


def test_json_restore_is_staged_and_applied_only_on_next_start(tmp_path):
    state_file = tmp_path / "control.json"
    target = _state(
        accounts={"acc_new": {"id": "acc_new", "phone": "79990000002"}},
        identities={"tg:2": "acc_new"},
    )
    raw = json.dumps(target, ensure_ascii=False).encode("utf-8")

    async def scenario():
        live = ControlStore(state_file)
        await live.start()
        old = await live.get_or_create_account("max", 1, "79990000001")
        summary = await live.inspect_backup(raw)
        staged = await live.stage_restore(
            raw, expected_sha256=summary["sha256"], ip="127.0.0.1")

        assert live.account(old["id"]) is not None
        assert live.account("acc_new") is None
        assert live.restore_pending_path.exists()
        await live.close()

        restored = ControlStore(state_file)
        await restored.start()
        assert restored.account(old["id"]) is None
        assert restored.account("acc_new")["phone"] == "79990000002"
        assert not restored.restore_pending_path.exists()
        previous = json.loads(restored.restore_previous_path.read_text(encoding="utf-8"))
        assert old["id"] in previous["accounts"]
        assert any(rec.get("action") == "database:restore"
                   and rec.get("target") == staged["restoreId"]
                   for rec in restored.table("admin_audit").values())
        await restored.close()

    asyncio.run(scenario())


def test_restore_validation_rejects_partial_duplicate_and_changed_backup(tmp_path):
    store = ControlStore(tmp_path / "control.json")

    async def scenario():
        for raw in (
            b'{"accounts":{},"accounts":{}}',
            json.dumps({"accounts": {}}).encode(),
            json.dumps({**_state(), "future_table": {}}).encode(),
            json.dumps({**_state(), "accounts": None}).encode(),
        ):
            try:
                await store.inspect_backup(raw)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid backup must be rejected")

        valid = json.dumps(_state()).encode()
        summary = await store.inspect_backup(valid)
        try:
            await store.stage_restore(valid, expected_sha256="0" * 64)
        except ValueError as exc:
            assert "изменился после проверки" in str(exc)
        else:
            raise AssertionError("changed backup must be rejected")
        assert summary["tables"] == len(store_module._TABLES)
        assert not store.restore_pending_path.exists()

        # Даже злонамеренные audit timestamps из будущего не должны вытеснить
        # служебный marker, который защищает PostgreSQL restore от повтора.
        saturated = _state(admin_audit={
            f"aud_{i}": {"id": f"aud_{i}", "ts": 9_999_999_999_999 + i}
            for i in range(5000)
        })
        saturated_raw = json.dumps(saturated).encode()
        saturated_summary = await store.inspect_backup(saturated_raw)
        staged = await store.stage_restore(
            saturated_raw, expected_sha256=saturated_summary["sha256"])
        pending = json.loads(store.restore_pending_path.read_text(encoding="utf-8"))
        assert len(pending["payload"]["admin_audit"]) == 5000
        assert any(record.get("action") == "database:restore"
                   and record.get("target") == staged["restoreId"]
                   for record in pending["payload"]["admin_audit"].values())

    asyncio.run(scenario())


def test_postgres_restore_applies_once_and_preserves_newer_state(tmp_path, monkeypatch):
    old_state = _state(accounts={"acc_old": {"id": "acc_old"}})
    target = _state(accounts={"acc_new": {"id": "acc_new"}})
    raw = json.dumps(target).encode()
    pool = _FakePool(old_state)
    _pool_factory(monkeypatch, pool)
    state_file = tmp_path / "control.json"

    async def scenario():
        live = ControlStore(state_file, database_url="postgresql://db/mesync")
        await live.start()
        summary = await live.inspect_backup(raw)
        staged = await live.stage_restore(raw, expected_sha256=summary["sha256"])
        pending_bytes = live.restore_pending_path.read_bytes()
        await live.close()

        restored = ControlStore(state_file, database_url="postgresql://db/mesync")
        await restored.start()
        assert restored.account("acc_old") is None
        assert restored.account("acc_new") == {"id": "acc_new"}
        assert pool.payload["accounts"] == {"acc_new": {"id": "acc_new"}}
        previous = json.loads(restored.restore_previous_path.read_text(encoding="utf-8"))
        assert previous["accounts"] == {"acc_old": {"id": "acc_old"}}
        await restored.close()

        # Имитируем сбой удаления staging после успешного commit и более свежую запись.
        state_file.with_name("control.restore.pending.json").write_bytes(pending_bytes)
        pool.payload["events"]["newer"] = {"id": "newer", "title": "after restore"}
        reopened = ControlStore(state_file, database_url="postgresql://db/mesync")
        await reopened.start()
        assert reopened.table("events")["newer"]["title"] == "after restore"
        assert not reopened.restore_pending_path.exists()
        assert any(rec.get("target") == staged["restoreId"]
                   for rec in reopened.table("admin_audit").values())
        await reopened.close()

    asyncio.run(scenario())


def test_standalone_app_owns_postgres_lifecycle(tmp_path, monkeypatch):
    pool = _FakePool()
    calls = _pool_factory(monkeypatch, pool)
    monkeypatch.setattr(config, "STATE_FILE", tmp_path / "standalone.json")
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://db/standalone")
    monkeypatch.setattr(config, "POSTGRES_HOST", "")

    app = create_app()
    with TestClient(app) as client:
        healthy = client.get("/api/health")
        assert healthy.status_code == 200
        assert healthy.json()["storage"] == "postgresql"
        pool.healthy = False
        unavailable = client.get("/api/health")
        assert unavailable.status_code == 503
        assert unavailable.json()["ok"] is False
        assert app.state.store.backend == "postgresql"

    assert calls == [{"dsn": "postgresql://db/standalone"}]
    assert pool.closed is True


def test_expired_code_cleanup_and_legacy_revocation_are_persisted(tmp_path, monkeypatch):
    now = int(time.time())
    pool = _FakePool({
        "activation_codes": {
            "Old1-Code-0001": {
                "created_at": now - 40 * 86400,
                "used_by": None,
                "used_at": None,
            },
        },
        "pending_codes": {
            "1111": {"account_id": "acc_1", "expires_at": now - 1, "bound": []},
            "2222": {"account_id": "acc_1", "expires_at": now + 600,
                     "bound": ["max:9"]},
        },
        "account_sources": {"acc_1": ["max:9"]},
    })
    _pool_factory(monkeypatch, pool)

    async def scenario():
        store = ControlStore(tmp_path / "seed.json", database_url="postgresql://db/mesync")
        await store.start()

        # Чтение фильтрует TTL, но не меняет состояние в обход async persistence.
        assert set(store.active_codes()) == {"2222"}
        assert "1111" in store.table("pending_codes")

        # Повторная выдача возвращает живой код и одновременно сохраняет purge старого.
        assert (await store.issue_code("acc_1"))["code"] == "2222"
        assert "1111" not in pool.payload["pending_codes"]

        # Legacy-код без expires_at получает вычисленный срок даже в ветке `expired`.
        assert await store.revoke_activation_code("Old1-Code-0001", now=now) == "expired"
        expected = now - 40 * 86400 + store_module.ACTIVATION_CODE_TTL
        assert pool.payload["activation_codes"]["Old1-Code-0001"]["expires_at"] == expected

        # Резервные точечные методы удаления тоже проходят через PostgreSQL persistence.
        await store.remove_account_source("acc_1", "max:9")
        await store.remove_source_from_codes("max:9")
        assert pool.payload["account_sources"]["acc_1"] == []
        assert pool.payload["pending_codes"]["2222"]["bound"] == []
        await store.close()

    asyncio.run(scenario())

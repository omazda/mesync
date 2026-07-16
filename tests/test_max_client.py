"""Точечные тесты MAX API клиента.

Запуск: .venv/bin/python -m pytest tests/test_max_client.py -q
"""
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from max_sync.client import MaxClient, _AsyncRateLimiter  # noqa: E402


run = asyncio.run


class RecordingMaxClient(MaxClient):
    def __init__(self):
        super().__init__("token")
        self.calls = []

    async def call(self, http_method, path, *, query=None, json_body=None, read_timeout=None):
        self.calls.append({
            "method": http_method,
            "path": path,
            "query": query,
            "json_body": json_body,
            "read_timeout": read_timeout,
        })
        return {"message": {"body": {"mid": "mid.test"}}}


def test_send_message_disables_max_link_preview_with_false_query_value():
    client = RecordingMaxClient()

    run(client.send_message(chat_id=-1, text="https://example.com", disable_link_preview=True))

    call = client.calls[-1]
    assert call["query"]["disable_link_preview"] is False
    assert call["json_body"]["text"] == "https://example.com"


def test_send_message_omits_link_preview_flag_when_not_requested():
    client = RecordingMaxClient()

    run(client.send_message(chat_id=-1, text="https://example.com"))

    assert "disable_link_preview" not in client.calls[-1]["query"]


class _FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def request(self, method, url, *, params=None, json=None, timeout=None):
        self.calls.append({"method": method, "url": url, "params": params, "json": json})
        resp = self.responses.pop(0)
        if isinstance(resp, httpx.Response):
            return resp
        return httpx.Response(resp, json={"ok": True}, request=httpx.Request(method, url))


def _resp(status: int, *, headers=None, body=None) -> httpx.Response:
    return httpx.Response(
        status,
        headers=headers,
        json=body or {"code": "rate.limit", "message": "too many requests"},
        request=httpx.Request("GET", "https://max.test/method"),
    )


def test_call_uses_shared_rate_limiter_between_requests():
    async def scenario():
        now = 0.0
        sleeps = []

        def clock():
            return now

        async def fake_sleep(delay):
            nonlocal now
            sleeps.append(delay)
            now += delay

        client = MaxClient("token", "https://max.test", rate_limit_per_second=2)
        client._rate_limiter = _AsyncRateLimiter(2, clock=clock, sleep=fake_sleep)
        client._client = _FakeHttp([200, 200])

        await client.call("GET", "me")
        await client.call("GET", "me")

        assert sleeps == [0.5]
        assert len(client._client.calls) == 2

    run(scenario())


def test_call_retries_429_without_consuming_transient_retry_budget():
    async def scenario():
        now = 0.0
        sleeps = []

        def clock():
            return now

        async def fake_sleep(delay):
            nonlocal now
            sleeps.append(delay)
            now += delay

        client = MaxClient("token", "https://max.test", max_retries=0,
                           rate_limit_per_second=25)
        client._rate_limiter = _AsyncRateLimiter(25, clock=clock, sleep=fake_sleep)
        client._client = _FakeHttp([
            _resp(429, headers={"Retry-After": "1"}),
            _resp(429, headers={"Retry-After": "1"}),
            200,
        ])

        result = await client.call("POST", "messages", json_body={"text": "hello"})

        assert result == {"ok": True}
        assert len(client._client.calls) == 3
        assert sleeps == [2.0, 2.0]

    run(scenario())


def test_rate_limiter_cooldown_delays_next_slot():
    async def scenario():
        now = 0.0
        sleeps = []

        def clock():
            return now

        async def fake_sleep(delay):
            nonlocal now
            sleeps.append(delay)
            now += delay

        limiter = _AsyncRateLimiter(10, clock=clock, sleep=fake_sleep)

        await limiter.wait()
        await limiter.cooldown(2)
        await limiter.wait()

        assert sleeps == [2.0]

    run(scenario())


def test_disabled_rate_limiter_still_sleeps_on_cooldown():
    async def scenario():
        sleeps = []

        async def fake_sleep(delay):
            sleeps.append(delay)

        limiter = _AsyncRateLimiter(None, sleep=fake_sleep)

        await limiter.cooldown(3)

        assert sleeps == [3.0]

    run(scenario())

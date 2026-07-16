"""Асинхронный клиент Bot API MAX поверх httpx.

Все сетевые операции — async (требование проекта). Авторизация — заголовком
`Authorization: <token>` (передача токена в query больше не поддерживается).
Базовый домен и сигнатуры методов сверены с docs/max/ (раздел docs-api).

Особенности MAX vs Telegram:
- успешный ответ возвращает результат напрямую (без обёртки {ok, result});
- ошибка приходит HTTP-кодом 4xx/5xx с телом {"code": ..., "message": ...};
- методы используют разные HTTP-глаголы (GET/POST/PUT/DELETE/PATCH);
- параметры передаются и в query, и в JSON-теле (зависит от метода);
- лимит — 30 rps, при превышении возможен HTTP 429.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

log = logging.getLogger(__name__)

# Таймаут httpx на одну операцию при переносе крупного медиа (скачивание из MAX по url,
# загрузка в MAX через POST байтов). MAX принимает файлы до 4 ГБ (docs/.../uploads.md).
# По требованию заказчика ограничение по времени переноса СНЯТО (по умолчанию None — крупный
# файл качается/грузится сколько нужно); ограничен только connect, чтобы не зависнуть на
# недоступном хосте. Чтобы вернуть лимит — задайте MAX_MEDIA_TIMEOUT=<сек> (0/пусто = снят).
def _parse_media_timeout(raw: str | None) -> float | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


_MEDIA_TIMEOUT: float | None = _parse_media_timeout(os.environ.get("MAX_MEDIA_TIMEOUT"))
_MEDIA_CONNECT_TIMEOUT: float = 30.0


def _parse_rate_limit(raw: str | None, default: float = 25.0) -> float | None:
    """Запросов в секунду к Bot API MAX. 0/отрицательное значение отключает лимитер."""
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else None


_MAX_API_RATE_LIMIT_RPS: float | None = _parse_rate_limit(
    os.environ.get("MAX_API_RATE_LIMIT_RPS"))


class _AsyncRateLimiter:
    """Простой leaky-bucket: все конкурентные задачи резервируют следующий слот под lock."""

    def __init__(self, rate_per_second: float | None, *,
                 clock: Any = None, sleep: Any = None) -> None:
        self._interval = (1.0 / float(rate_per_second)) if rate_per_second else 0.0
        self._lock = asyncio.Lock()
        self._next_at = 0.0
        self._cooldown_until = 0.0
        self._clock = clock
        self._sleep = sleep or asyncio.sleep

    def _now(self) -> float:
        if self._clock is not None:
            return float(self._clock())
        return asyncio.get_running_loop().time()

    async def wait(self) -> None:
        if self._interval <= 0:
            return
        while True:
            async with self._lock:
                now = self._now()
                due = max(self._next_at, self._cooldown_until)
                delay = max(0.0, due - now)
                if delay <= 0:
                    self._next_at = now + self._interval
                    return
            await self._sleep(delay)

    async def cooldown(self, seconds: float) -> None:
        if seconds <= 0:
            return
        if self._interval <= 0:
            await self._sleep(float(seconds))
            return
        async with self._lock:
            until = self._now() + float(seconds)
            self._cooldown_until = max(self._cooldown_until, until)
            self._next_at = max(self._next_at, self._cooldown_until)


def _media_timeout() -> httpx.Timeout:
    """httpx.Timeout для переноса медиа: read/write без ограничения (None по умолчанию — крупный
    файл идёт сколько нужно), а connect и pool (ожидание свободного соединения) ограничены, чтобы
    мёртвый хост или исчерпанный пул не вешали навсегда (это не «время загрузки», а очередь)."""
    return httpx.Timeout(_MEDIA_TIMEOUT, connect=_MEDIA_CONNECT_TIMEOUT, pool=_MEDIA_CONNECT_TIMEOUT)


def _content_length_over(headers: httpx.Headers, max_bytes: int | None) -> bool:
    """Заявленный в Content-Length размер превышает потолок? (пре-флайт: не качать заведомо
    слишком большой файл). Отсутствующий/нечисловой Content-Length → False (решит потоковый
    лимит при чтении)."""
    if max_bytes is None:
        return False
    cl = headers.get("content-length")
    return bool(cl and cl.isdigit() and int(cl) > max_bytes)


def _filename_from_cd(cd: str | None) -> str | None:
    """Имя файла из заголовка `Content-Disposition` (RFC 6266). MAX не кладёт имя в payload
    файлового вложения (только url/token/fileId) — настоящее имя CDN отдаёт здесь. Предпочитаем
    `filename*=` (RFC 5987, percent-encoded с charset), иначе `filename="..."`. Возвращаем
    безопасный basename (без путей/упр.символов, ≤255), или None."""
    if not cd:
        return None
    name: str | None = None
    m = re.search(r"filename\*\s*=\s*([^;]+)", cd, re.I)
    if m:
        val = m.group(1).strip().strip('"')
        # Некоторые CDN отдают разделители RFC 5987 percent-кодированными (charset%27%27…) —
        # нормализуем ведущий `charset%27%27` к литеральному `charset''`.
        if "''" not in val:
            val = re.sub(r"^([\w-]+)%27%27", r"\1''", val, flags=re.I)
        if "''" in val:                       # charset'lang'pct-encoded
            charset, _, enc = val.partition("''")
            try:
                name = unquote(enc, encoding=(charset.strip() or "utf-8"), errors="replace")
            except Exception:  # noqa: BLE001 — кривой charset → декодируем как utf-8
                name = unquote(enc)
        else:
            name = val
    if not name:
        m = re.search(r'filename\s*=\s*"([^"]+)"', cd, re.I) or \
            re.search(r"filename\s*=\s*([^;]+)", cd, re.I)
        if m:
            name = m.group(1).strip().strip('"')
    if not name:
        return None
    name = name.replace("\\", "/").split("/")[-1]          # basename (без путей)
    # Убрать управляющие (Cc) и форматные (Cf) символы — в т.ч. bidi-оверрайды (U+202E и пр.),
    # которыми маскируют расширение (invoice<U+202E>gpj.exe → выглядит как invoiceexe.jpg).
    name = "".join(ch for ch in name if unicodedata.category(ch) not in ("Cc", "Cf")).strip()
    return name[:255] or None


class MaxError(RuntimeError):
    """Ошибка уровня Bot API MAX (HTTP 4xx/5xx)."""

    def __init__(self, method: str, status_code: int | None, code: str | None,
                 message: str) -> None:
        self.method = method
        self.status_code = status_code
        self.code = code
        self.description = message
        super().__init__(f"{method}: [{status_code}/{code}] {message}")


class MaxClient:
    """Тонкий async-клиент Bot API MAX. Использовать как `async with`."""

    def __init__(self, token: str, api_base: str = "https://platform-api.max.ru",
                 *, request_timeout: float = 60.0, max_retries: int = 5,
                 rate_limit_per_second: float | None = _MAX_API_RATE_LIMIT_RPS) -> None:
        self._token = token
        self._api_base = api_base.rstrip("/")
        self._request_timeout = request_timeout
        self._max_retries = max_retries
        self._rate_limiter = _AsyncRateLimiter(rate_limit_per_second)
        self._client: httpx.AsyncClient | None = None
        # Необязательный наблюдатель за ОТПРАВЛЕННЫМИ ботом сообщениями: вызывается с
        # результатом POST /messages ({"message": Message}). Диспетчер запоминает «свои»
        # сообщения, чтобы не синхронизировать их обратно (защита от петли).
        self.on_sent: Any = None

    def _fire_sent(self, result: Any) -> Any:
        if self.on_sent is not None and result is not None:
            try:
                self.on_sent(result)
            except Exception:  # noqa: BLE001 — наблюдатель не должен ломать отправку
                pass
        return result

    async def __aenter__(self) -> "MaxClient":
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._request_timeout),
            headers={"Authorization": self._token},
        )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("MaxClient используется вне 'async with'.")
        return self._client

    async def call(self, http_method: str, path: str, *,
                   query: dict[str, Any] | None = None,
                   json_body: dict[str, Any] | None = None,
                   read_timeout: float | None = None) -> Any:
        """Вызвать метод Bot API MAX. Возвращает разобранный JSON-ответ.

        Повторяет попытки при 429/5xx/сетевых сбоях (экспоненциальный backoff).
        """
        url = f"{self._api_base}/{path.lstrip('/')}"
        params = _clean_query(query or {})
        timeout = httpx.Timeout(read_timeout or self._request_timeout)
        label = f"{http_method} /{path.lstrip('/')}"
        transient_attempt = 0
        rate_limit_hits = 0
        while True:
            await self._rate_limiter.wait()
            try:
                resp = await self._http.request(
                    http_method, url, params=params, json=json_body, timeout=timeout)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                transient_attempt += 1
                if transient_attempt > self._max_retries:
                    raise
                delay = min(2 ** transient_attempt, 30)
                log.warning("Сетевая ошибка %s (%s); попытка %d/%d, пауза %ds",
                            label, exc, transient_attempt, self._max_retries, delay)
                await asyncio.sleep(delay)
                continue

            if 200 <= resp.status_code < 300:
                return _safe_json(resp)

            data = _safe_json(resp) or {}
            code = data.get("code")
            message = data.get("message") or resp.text[:200]

            if resp.status_code == 429:                  # троттлинг (30 rps)
                retry_after = _retry_after(resp)
                rate_limit_hits += 1
                log.warning("429 по %s: общий лимитер MAX уходит в паузу %ds (hit #%d)",
                            label, retry_after, rate_limit_hits)
                await self._rate_limiter.cooldown(retry_after)
                continue
            if 500 <= resp.status_code < 600 and transient_attempt < self._max_retries:
                transient_attempt += 1
                delay = min(2 ** transient_attempt, 30)
                log.warning("%s по %s; попытка %d/%d, пауза %ds",
                            resp.status_code, label, transient_attempt, self._max_retries, delay)
                await asyncio.sleep(delay)
                continue
            raise MaxError(label, resp.status_code, code, message)

    # --- удобные обёртки над методами MAX ---
    async def get_me(self) -> dict[str, Any]:
        return await self.call("GET", "me")

    async def get_updates(self, marker: int | None, *, timeout: int, limit: int,
                          types: list[str]) -> dict[str, Any]:
        query: dict[str, Any] = {"timeout": timeout, "limit": limit, "types": types}
        if marker is not None:
            query["marker"] = marker
        # HTTP read timeout должен превышать timeout long polling.
        return await self.call("GET", "updates", query=query, read_timeout=timeout + 20)

    async def send_message(self, *, chat_id: Any = None, user_id: Any = None,
                           text: str | None = None,
                           attachments: list[dict[str, Any]] | None = None,
                           link: dict[str, Any] | None = None,
                           notify: bool | None = None, fmt: str | None = None,
                           disable_link_preview: bool | None = None) -> dict[str, Any]:
        """POST /messages. Адресат — chat_id ИЛИ user_id (в query)."""
        query: dict[str, Any] = {}
        if chat_id is not None:
            query["chat_id"] = chat_id
        if user_id is not None:
            query["user_id"] = user_id
        if disable_link_preview is not None:
            # MAX API has inverted semantics here: docs say previews are not generated when
            # `disable_link_preview=false`, and live checks confirm that `true` still creates
            # a share card. Keep the wrapper argument conventional for callers.
            query["disable_link_preview"] = not disable_link_preview
        body: dict[str, Any] = {}
        if text is not None:
            body["text"] = text
        if attachments is not None:
            body["attachments"] = attachments
        if link is not None:
            body["link"] = link
        if notify is not None:
            body["notify"] = notify
        if fmt is not None:
            body["format"] = fmt
        return self._fire_sent(await self.call("POST", "messages", query=query, json_body=body))

    async def edit_message(self, message_id: str, *, text: str | None = None,
                          attachments: list[dict[str, Any]] | None = None,
                          fmt: str | None = None, notify: bool | None = None) -> dict[str, Any]:
        """PUT /messages — редактирование сообщения бота."""
        body: dict[str, Any] = {}
        if text is not None:
            body["text"] = text
        if attachments is not None:
            body["attachments"] = attachments
        if fmt is not None:
            body["format"] = fmt
        if notify is not None:
            body["notify"] = notify
        return await self.call("PUT", "messages", query={"message_id": message_id},
                               json_body=body)

    async def delete_message(self, message_id: str) -> dict[str, Any]:
        return await self.call("DELETE", "messages", query={"message_id": message_id})

    async def get_message(self, message_id: Any) -> dict[str, Any]:
        """GET /messages/{messageId} — перечитать сообщение по mid. Возвращает объект Message
        (sender/recipient/timestamp/link/body/stat/url); текст — в body.text (сверено с
        docs/max/markdown/docs-api/methods/GET/messages/-messageId-.md). Нужен для проверки
        актуального текста по жалобе (control.reports)."""
        return await self.call("GET", f"messages/{message_id}")

    async def answer_callback(self, callback_id: str, notification: str | None = None) -> dict[str, Any]:
        """POST /answers — ответ на нажатие inline-кнопки (message_callback)."""
        body: dict[str, Any] = {}
        if notification:
            body["notification"] = notification
        return await self.call("POST", "answers", query={"callback_id": callback_id},
                               json_body=body or None)

    async def get_chat(self, chat_id: Any) -> dict[str, Any]:
        return await self.call("GET", f"chats/{chat_id}")

    async def get_chat_membership(self, chat_id: Any) -> dict[str, Any]:
        return await self.call("GET", f"chats/{chat_id}/members/me")

    async def get_chat_admins(self, chat_id: Any, marker: Any = None) -> dict[str, Any]:
        query = {"marker": marker} if marker is not None else None
        return await self.call("GET", f"chats/{chat_id}/members/admins", query=query)

    async def leave_chat(self, chat_id: Any) -> dict[str, Any]:
        return await self.call("DELETE", f"chats/{chat_id}/members/me")

    async def subscribe(self, url: str, update_types: list[str],
                        secret: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"url": url, "update_types": update_types}
        if secret:
            body["secret"] = secret
        return await self.call("POST", "subscriptions", json_body=body)

    async def get_subscriptions(self) -> dict[str, Any]:
        return await self.call("GET", "subscriptions")

    async def unsubscribe(self, url: str) -> dict[str, Any]:
        return await self.call("DELETE", "subscriptions", query={"url": url})

    async def upload_url(self, upload_type: str) -> dict[str, Any]:
        """POST /uploads?type=image|video|audio|file — получить URL для загрузки."""
        return await self.call("POST", "uploads", query={"type": upload_type})

    async def upload_media(self, upload_type: str, data: bytes, *, filename: str = "file",
                           content_type: str | None = None) -> str | None:
        """Загрузить медиа в MAX и вернуть token для attachments (или None).

        Флоу сверен с docs/max/.../POST/uploads.md и проверен вживую: POST /uploads?type=…
        → {url[, token]}; затем POST байтов на этот url (multipart) — БЕЗ заголовка
        Authorization (url уже подписан apiToken; иначе bot-токен утёк бы на CDN-хост).
        Где лежит token зависит от типа (проверено round-trip):
          • video/audio → token приходит уже в ответе /uploads (шаг 1);
          • image       → ответ загрузки {"photos": {"<id>": {"token": …}}};
          • file        → ответ загрузки {"token": …}.
        """
        info = await self.upload_url(upload_type)
        url = info.get("url")
        if not url:
            return None
        files = {"data": (filename or "file", data, content_type or "application/octet-stream")}
        # Крупный файл (до 4 ГБ) — без лимита по времени на загрузку и ожидание ответа CDN MAX.
        async with httpx.AsyncClient(timeout=_media_timeout(), follow_redirects=True) as pub:
            r = await pub.post(url, files=files)
            r.raise_for_status()
            try:
                resp = r.json()
            except Exception:  # noqa: BLE001
                resp = {}
        if upload_type in ("video", "audio") and info.get("token"):
            return info["token"]
        if isinstance(resp, dict):
            photos = resp.get("photos")
            if isinstance(photos, dict):
                for v in photos.values():
                    if isinstance(v, dict) and v.get("token"):
                        return v["token"]
            if resp.get("token"):
                return resp["token"]
        return info.get("token")

    async def download_file(self, url: str, dest: Path) -> int:
        """Скачать файл по прямому ПУБЛИЧНОМУ URL вложения на диск. Возвращает байты.

        ВАЖНО (безопасность): качаем ОТДЕЛЬНЫМ httpx-клиентом БЕЗ заголовка Authorization
        (как download_bytes). Общий self._http несёт client-level `Authorization: <bot-токен>`,
        который httpx шлёт на ЛЮБОЙ хост, а url вложения ведёт на сторонний CDN MAX
        (i.oneme.ru/okcdn) — иначе bot-токен утёк бы на CDN. Расширенный таймаут — для
        крупного медиа (MAX отдаёт файлы до 4 ГБ)."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        async with httpx.AsyncClient(timeout=_media_timeout(),
                                     follow_redirects=True) as pub:
            async with pub.stream("GET", url) as r:
                r.raise_for_status()
                with dest.open("wb") as fh:
                    async for chunk in r.aiter_bytes():
                        fh.write(chunk)
                        total += len(chunk)
        return total

    async def download_bytes(self, url: str, *, max_bytes: int = 16 * 1024 * 1024
                             ) -> tuple[bytes, str, str | None]:
        """Скачать файл по прямому ПУБЛИЧНОМУ URL в память (для аватаров: icon.url чата).
        Возвращает (байты, content-type, имя_файла|None). Имя — из заголовка
        `Content-Disposition` (MAX не отдаёт его в payload вложения; см. _filename_from_cd).

        ВАЖНО (безопасность): качаем ОТДЕЛЬНЫМ httpx-клиентом БЕЗ заголовка Authorization.
        Общий self._http несёт client-level `Authorization: <bot-токен>`, а httpx шлёт его
        на ЛЮБОЙ хост при прямом запросе (срезает только при cross-origin редиректе) —
        icon.url ведёт на сторонний CDN MAX, поэтому иначе bot-токен утёк бы на CDN.
        max_bytes — потолок размера ответа (защита от слишком большого тела). Для аватаров
        вызывается с дефолтом (16 МБ); для кросс-мессенджерного переноса MAX→TG вызывающий
        передаёт config.TG_UPLOAD_MAX_BYTES (с локальным Bot API сервером — до 2000 МБ)."""
        async with httpx.AsyncClient(timeout=_media_timeout(),
                                     follow_redirects=True) as pub:
            async with pub.stream("GET", url) as r:
                r.raise_for_status()
                # Пре-флайт: если CDN заранее сообщил размер больше потолка — НЕ качаем тело
                # вовсе (заказчик: «больше 2 ГБ даже не начинали загружаться»).
                if _content_length_over(r.headers, max_bytes):
                    raise ValueError("download_bytes: Content-Length превышает лимит размера")
                filename = _filename_from_cd(r.headers.get("content-disposition"))
                buf = bytearray()
                async for chunk in r.aiter_bytes():
                    buf += chunk
                    if len(buf) > max_bytes:
                        raise ValueError("download_bytes: ответ превышает лимит размера")
                return bytes(buf), r.headers.get("content-type") or "image/jpeg", filename

    async def content_length(self, url: str) -> int | None:
        """Размер файла по публичному url вложения через HEAD (Content-Length) — БЕЗ скачивания.
        Нужен для учёта трафика MAX→MAX: у MAX-вложений нет file_size в payload, а файл мы не
        качаем (переиспользуем token). Отдельный httpx-клиент БЕЗ заголовка Authorization
        (url ведёт на сторонний CDN MAX — bot-токен туда слать нельзя, как в download_*).
        Возвращает int или None (если CDN не сообщил размер). Таймаут небольшой — это лёгкий
        запрос метаданных без тела."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0),
                                     follow_redirects=True) as pub:
            r = await pub.head(url)
            r.raise_for_status()
            cl = r.headers.get("content-length")
        return int(cl) if cl is not None and str(cl).isdigit() else None


def _clean_query(query: dict[str, Any]) -> dict[str, Any]:
    """Подготовить query: None отбросить, list -> 'a,b,c', bool -> 'true'/'false'."""
    out: dict[str, Any] = {}
    for key, value in query.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            out[key] = ",".join(str(v) for v in value)
        elif isinstance(value, bool):
            out[key] = "true" if value else "false"
        else:
            out[key] = value
    return out


def _safe_json(resp: httpx.Response) -> dict[str, Any] | None:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"result": data}
    except Exception:  # noqa: BLE001 — ответ может быть пустым/не-JSON
        return {} if 200 <= resp.status_code < 300 else None


def _retry_after(resp: httpx.Response) -> int:
    raw = resp.headers.get("Retry-After")
    if raw:
        try:
            return max(1, int(raw)) + 1
        except ValueError:
            pass
    return 2

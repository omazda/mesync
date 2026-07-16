"""Асинхронный клиент Telegram Bot API поверх httpx.

Все сетевые операции — async (требование проекта). Реализованы getMe,
getUpdates, getFile и скачивание файлов. Обрабатываются ошибки Bot API
(ok=false), троттлинг (429 + retry_after) и временные сетевые/5xx сбои
с экспоненциальным backoff.

Сигнатуры методов сверены с docs/telegram/markdown/04-api-reference.md.
"""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import shutil
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

# Таймаут httpx при переносе крупного медиа: скачивание файла и multipart-загрузка. С
# локальным Bot API сервером файлы — до 2000 МБ. По требованию заказчика ограничение по
# времени переноса СНЯТО (по умолчанию None — крупный файл идёт сколько нужно); ограничен
# только connect, чтобы не зависнуть на мёртвом хосте. Вернуть лимит: TELEGRAM_MEDIA_TIMEOUT=<сек>.
def _parse_media_timeout(raw: str | None) -> float | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


_MEDIA_TIMEOUT: float | None = _parse_media_timeout(os.environ.get("TELEGRAM_MEDIA_TIMEOUT"))
_MEDIA_CONNECT_TIMEOUT: float = 30.0


def _media_timeout() -> httpx.Timeout:
    """httpx.Timeout для переноса медиа: read/write без ограничения (None по умолчанию — крупный
    файл идёт сколько нужно), а connect и pool (ожидание свободного соединения) ограничены, чтобы
    мёртвый хост или исчерпанный пул не вешали навсегда (это не «время загрузки», а очередь)."""
    return httpx.Timeout(_MEDIA_TIMEOUT, connect=_MEDIA_CONNECT_TIMEOUT, pool=_MEDIA_CONNECT_TIMEOUT)


class UploadFile:
    """Файл для отправки multipart/form-data (а не file_id/URL).

    Используется, когда контент нужно ЗАГРУЗИТЬ байтами (например, медиа из MAX, которое
    нельзя отдать Telegram ссылкой: webp-картинки отвергает sendPhoto, sendDocument по URL
    принимает лишь PDF/ZIP — сверено с docs/.../04-api-reference.md «Sending files»). Лимиты
    multipart на ОБЛАЧНОМ Bot API: 10 МБ фото, 50 МБ прочее; на ЛОКАЛЬНОМ Bot API сервере —
    до 2000 МБ (крупное фото при отказе sendPhoto уходит документом — см. _tg_send_one)."""

    __slots__ = ("data", "filename", "content_type")

    def __init__(self, data: bytes, *, filename: str = "file",
                 content_type: str | None = None) -> None:
        self.data = data
        self.filename = filename or "file"
        self.content_type = content_type

    def as_tuple(self) -> tuple[str, bytes, str]:
        return (self.filename, self.data, self.content_type or "application/octet-stream")


class TelegramError(RuntimeError):
    """Ошибка уровня Bot API (ответ с ok=false)."""

    def __init__(self, method: str, error_code: int | None, description: str,
                 parameters: dict[str, Any] | None = None) -> None:
        self.method = method
        self.error_code = error_code
        self.description = description
        self.parameters = parameters or {}
        super().__init__(f"{method}: [{error_code}] {description}")


class TelegramClient:
    """Тонкий async-клиент Bot API. Использовать как `async with`."""

    def __init__(self, token: str, api_base: str = "https://api.telegram.org",
                 *, request_timeout: float = 60.0, max_retries: int = 5,
                 local_file_root: str | Path | None = None) -> None:
        self._token = token
        self._api_base = api_base.rstrip("/")
        self._method_url = f"{self._api_base}/bot{token}"
        self._file_url = f"{self._api_base}/file/bot{token}"
        configured_root = local_file_root or os.environ.get("TELEGRAM_API_LOCAL_FILES_ROOT")
        self._local_file_root = Path(
            configured_root or f"/var/lib/telegram-bot-api/{token}"
        ).resolve(strict=False)
        self._request_timeout = request_timeout
        self._max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
        # Необязательный наблюдатель за ОТПРАВЛЕННЫМИ ботом сообщениями: вызывается с
        # результатом sendMessage/sendPhoto/…/sendMediaGroup (объект Message или их список).
        # Используется диспетчером, чтобы запомнить «свои» сообщения и не синхронизировать их.
        self.on_sent: Any = None

    def _fire_sent(self, result: Any) -> Any:
        if self.on_sent is not None and result is not None:
            try:
                self.on_sent(result)
            except Exception:  # noqa: BLE001 — наблюдатель не должен ломать отправку
                pass
        return result

    async def __aenter__(self) -> "TelegramClient":
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(self._request_timeout))
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
            raise RuntimeError("TelegramClient используется вне 'async with'.")
        return self._client

    async def call(self, method: str, params: dict[str, Any] | None = None,
                   *, read_timeout: float | None = None,
                   files: dict[str, Any] | None = None) -> Any:
        """Вызвать метод Bot API и вернуть поле result.

        Значения-списки/словари сериализуются в JSON (требование Bot API,
        например allowed_updates). Повторяет попытки при 429/5xx/сетевых сбоях.
        """
        payload = _encode_params(params or {})
        url = f"{self._method_url}/{method}"
        # multipart-загрузка (files) крупного медиа может слать тело и ждать ответ долго —
        # без лимита по времени (с локальным Bot API сервером файл до 2000 МБ).
        if read_timeout is not None:
            timeout = httpx.Timeout(read_timeout)
        elif files:
            timeout = _media_timeout()
        else:
            timeout = httpx.Timeout(self._request_timeout)
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = await self._http.post(url, data=payload, files=files, timeout=timeout)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt > self._max_retries:
                    raise
                delay = min(2 ** attempt, 30)
                log.warning("Сетевая ошибка %s (%s); попытка %d/%d, пауза %ds",
                            method, exc, attempt, self._max_retries, delay)
                await asyncio.sleep(delay)
                continue

            data = _safe_json(resp)
            if data is not None and data.get("ok"):
                return data.get("result")

            error_code = (data or {}).get("error_code", resp.status_code)
            description = (data or {}).get("description") or resp.text[:200]
            parameters = (data or {}).get("parameters", {})

            # 429 — троттлинг: уважаем retry_after.
            if error_code == 429:
                retry_after = int(parameters.get("retry_after", 1))
                log.warning("429 по %s: пауза retry_after=%ds", method, retry_after)
                await asyncio.sleep(retry_after + 1)
                continue
            # 5xx — временный сбой сервера Telegram.
            if isinstance(error_code, int) and 500 <= error_code < 600 and attempt <= self._max_retries:
                delay = min(2 ** attempt, 30)
                log.warning("%s по %s; попытка %d/%d, пауза %ds",
                            error_code, method, attempt, self._max_retries, delay)
                await asyncio.sleep(delay)
                continue
            raise TelegramError(method, error_code, description, parameters)

    async def get_me(self) -> dict[str, Any]:
        return await self.call("getMe")

    async def get_updates(self, offset: int | None, *, timeout: int, limit: int,
                          allowed_updates: list[str]) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeout": timeout,
            "limit": limit,
            "allowed_updates": allowed_updates,
        }
        if offset is not None:
            params["offset"] = offset
        # HTTP read timeout должен превышать timeout long polling.
        return await self.call("getUpdates", params, read_timeout=timeout + 15)

    async def get_file(self, file_id: str) -> dict[str, Any]:
        """getFile: подготовить файл к скачиванию. На ОБЛАЧНОМ Bot API — файлы ≤20 МБ; с
        локальным Bot API сервером ограничения на размер скачивания нет (см. docs/.../
        04-api-reference.md «Using a Local Bot API Server»)."""
        return await self.call("getFile", {"file_id": file_id})

    async def get_user_profile_photos(self, user_id: Any, *, offset: int = 0,
                                      limit: int = 1) -> dict[str, Any]:
        """getUserProfilePhotos: получить фото профиля пользователя.

        Возвращает UserProfilePhotos; сами байты затем берём через getFile + download.
        """
        return await self.call("getUserProfilePhotos", {
            "user_id": user_id,
            "offset": offset,
            "limit": limit,
        })

    def _checked_local_file_path(self, file_path: str) -> str:
        """Разрешить local Bot API читать только файлы каталога текущего бота.

        Абсолютный file_path приходит из сетевого ответа getFile. Даже доверенному local
        Bot API не даём превратить его в произвольное чтение filesystem приложения.
        resolve() одновременно закрывает `..`, prefix-подмену и symlink-выход из root.
        """
        try:
            candidate = Path(file_path).resolve(strict=False)
            if candidate == self._local_file_root \
                    or not candidate.is_relative_to(self._local_file_root):
                raise RuntimeError("Файл локального Telegram Bot API недоступен")
            return str(candidate)
        except (OSError, RuntimeError):
            raise RuntimeError("Файл локального Telegram Bot API недоступен") from None

    async def download_file(self, file_path: str, dest: Path) -> int:
        """Скачать файл из getFile на диск. Возвращает число записанных байт.

        Локальный Bot API сервер (--local) отдаёт в file_path АБСОЛЮТНЫЙ путь файла на общем
        томе — копируем прямо с диска (без перекачки по HTTP). Облачный/нелокальный сервер
        отдаёт относительный путь — качаем потоково по HTTP /file/bot<token>/<path>."""
        if os.path.isabs(file_path):
            local_path = self._checked_local_file_path(file_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            return await asyncio.to_thread(_copy_local_file, local_path, dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"{self._file_url}/{file_path}"
        total = 0
        async with self._http.stream("GET", url, timeout=_media_timeout()) as r:
            r.raise_for_status()
            with dest.open("wb") as fh:
                async for chunk in r.aiter_bytes():
                    fh.write(chunk)
                    total += len(chunk)
        return total

    async def download_file_bytes(self, file_path: str, *, max_bytes: int | None = None) -> tuple[bytes, str]:
        """Скачать файл из getFile в память. Возвращает (байты, content-type).

        Локальный Bot API сервер (--local) отдаёт АБСОЛЮТНЫЙ путь на общем томе — читаем с
        диска напрямую (у локального сервера лимита размера скачивания нет). Облачный/
        нелокальный — относительный путь, качаем по HTTP. max_bytes (если задан) — потолок
        размера: защита RAM при крупном медиа (превышение → ValueError, вызывающий
        деградирует до текст+ссылки). Годится и для аватаров (без потолка), и для TG→MAX."""
        if os.path.isabs(file_path):
            local_path = self._checked_local_file_path(file_path)
            return await asyncio.to_thread(_read_local_file, local_path, max_bytes)
        url = f"{self._file_url}/{file_path}"
        buf = bytearray()
        ct = "image/jpeg"
        async with self._http.stream("GET", url, timeout=_media_timeout()) as r:
            r.raise_for_status()
            ct = r.headers.get("content-type") or "image/jpeg"
            async for chunk in r.aiter_bytes():
                buf += chunk
                if max_bytes is not None and len(buf) > max_bytes:
                    raise ValueError("download_file_bytes: файл превышает лимит размера")
        return bytes(buf), ct

    # --- отправка (для синхронизации по правилам mini-app) ---
    # Сигнатуры сверены с docs/telegram/markdown/04-api-reference.md.
    async def send_message(self, chat_id: Any, text: str, *, parse_mode: str | None = "HTML",
                           message_thread_id: Any | None = None,
                           entities: list[dict[str, Any]] | None = None,
                           disable_web_page_preview: bool | None = None,
                           disable_notification: bool | None = None,
                           reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if message_thread_id is not None:
            params["message_thread_id"] = message_thread_id
        if entities is not None:
            params["entities"] = entities                 # entities вместо parse_mode
        elif parse_mode:
            params["parse_mode"] = parse_mode
        if disable_web_page_preview is not None:
            params["link_preview_options"] = {"is_disabled": bool(disable_web_page_preview)}
        if disable_notification is not None:
            params["disable_notification"] = disable_notification
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return self._fire_sent(await self.call("sendMessage", params))

    async def _send_single_media(self, method: str, field: str, chat_id: Any,
                                 media: "str | UploadFile", *, caption: str | None,
                                 parse_mode: str | None,
                                 message_thread_id: Any | None = None,
                                 reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        """Общий путь sendPhoto/Video/Audio/Document: media — file_id/URL (строка, в params)
        ЛИБО UploadFile (байты, multipart-файлом под именем `field`)."""
        params: dict[str, Any] = {"chat_id": chat_id}
        if message_thread_id is not None:
            params["message_thread_id"] = message_thread_id
        files: dict[str, Any] | None = None
        if isinstance(media, UploadFile):
            files = {field: media.as_tuple()}
        else:
            params[field] = media
        if caption is not None:
            params["caption"] = caption
            if parse_mode:
                params["parse_mode"] = parse_mode
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return self._fire_sent(await self.call(method, params, files=files))

    async def send_photo(self, chat_id: Any, photo: "str | UploadFile", *,
                         caption: str | None = None, parse_mode: str | None = "HTML",
                         message_thread_id: Any | None = None,
                         reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._send_single_media("sendPhoto", "photo", chat_id, photo,
                                             caption=caption, parse_mode=parse_mode,
                                             message_thread_id=message_thread_id,
                                             reply_markup=reply_markup)

    async def send_document(self, chat_id: Any, document: "str | UploadFile", *,
                            caption: str | None = None, parse_mode: str | None = "HTML",
                            message_thread_id: Any | None = None,
                            reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._send_single_media("sendDocument", "document", chat_id, document,
                                             caption=caption, parse_mode=parse_mode,
                                             message_thread_id=message_thread_id,
                                             reply_markup=reply_markup)

    async def send_video(self, chat_id: Any, video: "str | UploadFile", *,
                         caption: str | None = None, parse_mode: str | None = "HTML",
                         message_thread_id: Any | None = None,
                         reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._send_single_media("sendVideo", "video", chat_id, video,
                                             caption=caption, parse_mode=parse_mode,
                                             message_thread_id=message_thread_id,
                                             reply_markup=reply_markup)

    async def send_audio(self, chat_id: Any, audio: "str | UploadFile", *,
                         caption: str | None = None, parse_mode: str | None = "HTML",
                         message_thread_id: Any | None = None,
                         reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._send_single_media("sendAudio", "audio", chat_id, audio,
                                             caption=caption, parse_mode=parse_mode,
                                             message_thread_id=message_thread_id,
                                             reply_markup=reply_markup)

    async def send_media_group(self, chat_id: Any, media: list[dict[str, Any]],
                               *, message_thread_id: Any | None = None) -> Any:
        """sendMediaGroup. Поле `media` каждого элемента — строка (file_id/URL) ИЛИ UploadFile;
        загружаемые байты привязываются multipart-файлами через `attach://<имя>` (сверено с
        docs/.../04-api-reference.md — InputMedia*.media, способ attach://)."""
        files: dict[str, Any] = {}
        out: list[dict[str, Any]] = []
        for i, item in enumerate(media):
            entry = dict(item)
            ref = entry.get("media")
            if isinstance(ref, UploadFile):
                name = f"file{i}"
                files[name] = ref.as_tuple()
                entry["media"] = f"attach://{name}"
            out.append(entry)
        params: dict[str, Any] = {"chat_id": chat_id, "media": out}
        if message_thread_id is not None:
            params["message_thread_id"] = message_thread_id
        return self._fire_sent(await self.call("sendMediaGroup", params, files=files or None))

    async def leave_chat(self, chat_id: Any) -> Any:
        return await self.call("leaveChat", {"chat_id": chat_id})

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> Any:
        params: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            params["text"] = text
        return await self.call("answerCallbackQuery", params)

    async def edit_message_text(self, chat_id: Any, message_id: Any, text: str, *,
                               parse_mode: str | None = "HTML",
                               reply_markup: dict[str, Any] | None = None,
                               disable_web_page_preview: bool | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if parse_mode:
            params["parse_mode"] = parse_mode
        if disable_web_page_preview is not None:
            params["link_preview_options"] = {"is_disabled": bool(disable_web_page_preview)}
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return await self.call("editMessageText", params)

    async def edit_message_caption(self, chat_id: Any, message_id: Any, caption: str, *,
                                   parse_mode: str | None = "HTML",
                                   reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "caption": caption}
        if parse_mode:
            params["parse_mode"] = parse_mode
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return await self.call("editMessageCaption", params)

    async def edit_message_media(self, chat_id: Any, message_id: Any, media: dict[str, Any], *,
                                 reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        """editMessageMedia. `media.media` может быть UploadFile и уйдёт multipart через attach://."""
        entry = dict(media)
        files: dict[str, Any] = {}
        ref = entry.get("media")
        if isinstance(ref, UploadFile):
            name = "media"
            files[name] = ref.as_tuple()
            entry["media"] = f"attach://{name}"
        params: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "media": entry}
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return await self.call("editMessageMedia", params, files=files or None)

    async def delete_message(self, chat_id: Any, message_id: Any) -> Any:
        return await self.call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

    async def get_chat(self, chat_id: Any) -> dict[str, Any]:
        return await self.call("getChat", {"chat_id": chat_id})

    async def get_chat_member(self, chat_id: Any, user_id: Any) -> dict[str, Any]:
        return await self.call("getChatMember", {"chat_id": chat_id, "user_id": user_id})


def _read_local_file(path: str, max_bytes: int | None) -> tuple[bytes, str]:
    """Прочитать с диска файл локального Bot API сервера (--local отдаёт абсолютный путь).
    Размер сверяется с потолком ДО чтения — не буферизуем сверх лимита. content-type
    угадывается по имени (для аватаров вызывающий всё равно пересниффит по байтам)."""
    try:
        size = os.path.getsize(path)
        if max_bytes is not None and size > max_bytes:
            raise ValueError("download_file_bytes: файл превышает лимит размера")
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        # Абсолютный путь local Bot API содержит bot token. Не включаем его в исключение:
        # вызывающий может залогировать traceback при проблемах mount/прав.
        raise RuntimeError("Файл локального Telegram Bot API недоступен") from None
    ct = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return data, ct


def _copy_local_file(src: str, dest: Path) -> int:
    """Скопировать файл локального Bot API сервера с диска в dest. Возвращает размер."""
    try:
        shutil.copyfile(src, dest)
        return os.path.getsize(dest)
    except OSError:
        raise RuntimeError("Файл локального Telegram Bot API недоступен") from None


def _encode_params(params: dict[str, Any]) -> dict[str, Any]:
    """Подготовить значения для form-data: list/dict -> JSON, bool -> 'true'/'false'."""
    out: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            out[key] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            out[key] = "true" if value else "false"
        else:
            out[key] = value
    return out


def _safe_json(resp: httpx.Response) -> dict[str, Any] | None:
    try:
        return resp.json()
    except Exception:  # noqa: BLE001 — ответ может быть не-JSON (например, HTML 502)
        return None

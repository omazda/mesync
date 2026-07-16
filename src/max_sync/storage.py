"""Персистентное хранилище бота MAX.

Сохраняем:
- сырые события как есть (JSONL) — ничего не теряем;
- нормализованный контент (JSONL);
- marker GET /updates — чтобы при перезапуске не переобрабатывать события;
- скачанные медиафайлы (по запросу).

Файловый I/O — в пуле потоков (asyncio.to_thread), чтобы не блокировать event loop.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, raw_file: Path, content_file: Path, marker_file: Path,
                 media_dir: Path) -> None:
        self.raw_file = Path(raw_file)
        self.content_file = Path(content_file)
        self.marker_file = Path(marker_file)
        self.media_dir = Path(media_dir)
        for p in (self.raw_file, self.content_file, self.marker_file):
            p.parent.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

    # --- сырые события и нормализованный контент ---
    async def append_raw(self, update: dict[str, Any]) -> None:
        await asyncio.to_thread(self._append_line, self.raw_file, update)

    async def append_content(self, obj: dict[str, Any]) -> None:
        await asyncio.to_thread(self._append_line, self.content_file, _strip_raw(obj))

    @staticmethod
    def _append_line(path: Path, obj: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")

    # --- marker (аналог offset в Telegram) ---
    async def load_marker(self) -> int | None:
        return await asyncio.to_thread(self._read_marker)

    def _read_marker(self) -> int | None:
        if not self.marker_file.exists():
            return None
        text = self.marker_file.read_text(encoding="utf-8").strip()
        return int(text) if text else None

    async def save_marker(self, marker: int) -> None:
        await asyncio.to_thread(self.marker_file.write_text, str(marker), "utf-8")

    # --- путь для медиа ---
    def media_path(self, chat_id: Any, name: str) -> Path:
        safe_chat = str(chat_id).replace("/", "_")
        return self.media_dir / safe_chat / name


def _strip_raw(obj: dict[str, Any]) -> dict[str, Any]:
    """Облегчённая копия для content.jsonl: убираем дублирующий сырой JSON
    (он уже сохранён в updates.jsonl)."""
    out = dict(obj)
    out.pop("raw", None)
    if isinstance(out.get("attachments"), list):
        out["attachments"] = [
            {k: v for k, v in a.items() if k != "raw"} for a in out["attachments"]
        ]
    if isinstance(out.get("media"), list):
        out["media"] = [
            {k: v for k, v in a.items() if k != "raw"} for a in out["media"]
        ]
    return out

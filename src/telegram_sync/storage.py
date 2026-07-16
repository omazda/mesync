"""Персистентное хранилище Этапа 1.

Сохраняем:
- сырые апдейты как есть (JSONL) — гарантия, что ничего не потеряно;
- нормализованный контент (сообщения и собранные альбомы) — JSONL;
- offset getUpdates — чтобы при перезапуске не переобрабатывать апдейты;
- скачанные медиафайлы (по запросу) — с именами, отражающими порядок.

Файловые операции выполняются в пуле потоков (asyncio.to_thread), чтобы не
блокировать event loop.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, raw_file: Path, content_file: Path, offset_file: Path,
                 media_dir: Path) -> None:
        self.raw_file = Path(raw_file)
        self.content_file = Path(content_file)
        self.offset_file = Path(offset_file)
        self.media_dir = Path(media_dir)
        for p in (self.raw_file, self.content_file, self.offset_file):
            p.parent.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

    # --- сырые апдейты и нормализованный контент ---
    async def append_raw(self, update: dict[str, Any]) -> None:
        await asyncio.to_thread(self._append_line, self.raw_file, update)

    async def append_content(self, obj: dict[str, Any]) -> None:
        await asyncio.to_thread(self._append_line, self.content_file, _strip_raw(obj))

    @staticmethod
    def _append_line(path: Path, obj: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")

    # --- offset ---
    async def load_offset(self) -> int | None:
        return await asyncio.to_thread(self._read_offset)

    def _read_offset(self) -> int | None:
        if not self.offset_file.exists():
            return None
        text = self.offset_file.read_text(encoding="utf-8").strip()
        return int(text) if text else None

    async def save_offset(self, offset: int) -> None:
        await asyncio.to_thread(self.offset_file.write_text, str(offset), "utf-8")

    # --- путь для медиа (имя отражает порядок) ---
    def media_path(self, chat_id: Any, name: str) -> Path:
        safe_chat = str(chat_id).replace("/", "_")
        return self.media_dir / safe_chat / name


def _strip_raw(obj: dict[str, Any]) -> dict[str, Any]:
    """Облегчённая копия для content.jsonl: убираем дублирующий сырой JSON
    (он уже сохранён в updates.jsonl), оставляя ссылки и метаданные."""
    out = dict(obj)
    out.pop("raw", None)
    if isinstance(out.get("parts"), list):
        out["parts"] = [
            {k: v for k, v in p.items() if k != "raw"} for p in out["parts"]
        ]
    if isinstance(out.get("media"), list):
        cleaned = []
        for m in out["media"]:
            mm = {k: v for k, v in m.items() if k != "raw"}
            cleaned.append(mm)
        out["media"] = cleaned
    return out

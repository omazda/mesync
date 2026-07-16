"""Конвертация анимированных и видео-стикеров Telegram в mp4 (для отправки видео в MAX).

Зачем: у MAX при загрузке нет типа «стикер/GIF», а анимированные стикеры Telegram бывают
двух форматов, ни один из которых MAX не отрисует как есть:
  • is_animated → TGS = gzip(Lottie JSON), векторная анимация (не видео/не GIF);
  • is_video    → WebM/VP9, растровое видео.
Поэтому оба формата приводим к mp4 (h264/yuv420p) и отправляем как `type=video` MAX —
стикер «оживает». Статичные стикеры (webp/png) этот модуль не трогает (они идут картинкой).

Зависимости — self-contained (pip, без системного apt):
  • imageio-ffmpeg — статичный бинарь ffmpeg (libx264 включён);
  • rlottie-python — рендер Lottie (rlottie зашит в колесо);
  • Pillow — сборка кадров.
Если зависимостей/бинаря нет — функции возвращают None, а вызывающий деградирует на
статичное превью (фоллбэк), т.е. отсутствие тулинга НЕ ломает пересылку.

Асинхронность: тяжёлая работа (рендер кадров + ffmpeg) блокирующая, поэтому публичная
`sticker_to_mp4` уносит её в пул потоков (`asyncio.to_thread`) — event loop не блокируется.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile

log = logging.getLogger("control.stickers")

# Фон под прозрачность стикера (mp4/h264 не поддерживает альфу — приходится «приплюснуть»).
_BG = (255, 255, 255, 255)
# Потолок стороны кадра и числа кадров — защита от чрезмерного CPU/размера на патологии.
_MAX_SIDE = 512
_MAX_FRAMES = 300


def _ffmpeg_exe() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        log.warning("ffmpeg недоступен (imageio-ffmpeg не установлен) — анимация стикеров отключена")
        return None


def conversion_available() -> bool:
    """Можно ли вообще конвертировать (есть ffmpeg + rlottie + Pillow)."""
    if _ffmpeg_exe() is None:
        return False
    try:
        import rlottie_python  # noqa: F401
        import PIL  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _tail(path: str, n: int = 400) -> str:
    try:
        with open(path, "rb") as fh:
            return fh.read()[-n:].decode("utf-8", "replace")
    except OSError:
        return ""


def _even(v: int) -> int:
    """Чётный размер ≥2 (h264/yuv420p требует чётные ширину и высоту)."""
    return max(2, (int(v) // 2) * 2)


def _tgs_to_mp4_blocking(data: bytes, ff: str, workdir: str) -> bytes | None:
    from rlottie_python import LottieAnimation
    from PIL import Image

    tgs = os.path.join(workdir, "in.tgs")
    with open(tgs, "wb") as fh:
        fh.write(data)
    anim = LottieAnimation.from_tgs(tgs)
    try:
        total = int(anim.lottie_animation_get_totalframe() or 0)
        fps = float(anim.lottie_animation_get_framerate() or 30.0)
        w, h = anim.lottie_animation_get_size()
        w, h = int(w or _MAX_SIDE), int(h or _MAX_SIDE)
        if total <= 0:
            return None
        # Не апскейлим: вписываем в _MAX_SIDE с сохранением пропорций, размеры — чётные.
        scale = min(_MAX_SIDE / max(w, h), 1.0) if max(w, h) > 0 else 1.0
        tw, th = _even(w * scale), _even(h * scale)
        n = min(total, _MAX_FRAMES)
        bg = Image.new("RGBA", (tw, th), _BG)
        out = os.path.join(workdir, "out.mp4")
        errf = os.path.join(workdir, "err.txt")
        cmd = [ff, "-y", "-f", "rawvideo", "-pixel_format", "rgb24",
               "-video_size", f"{tw}x{th}", "-framerate", f"{max(1.0, fps):.3f}",
               "-i", "pipe:0", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", out]
        # stderr → файл (не PIPE): иначе при заполнении буфера stderr ffmpeg перестанет
        # читать stdin и запись кадров зависнет (deadlock). stdout не нужен.
        with open(errf, "wb") as e:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                    stdout=subprocess.DEVNULL, stderr=e)
            try:
                for i in range(n):
                    frame = anim.render_pillow_frame(frame_num=i, width=tw, height=th)
                    rgb = Image.alpha_composite(bg, frame.convert("RGBA")).convert("RGB")
                    proc.stdin.write(rgb.tobytes())
            finally:
                if proc.stdin:
                    proc.stdin.close()
                rc = proc.wait()
        if rc != 0:
            log.warning("ffmpeg(tgs) rc=%s: %s", rc, _tail(errf))
            return None
        with open(out, "rb") as fh:
            mp4 = fh.read()
        if not mp4:
            log.warning("ffmpeg(tgs) дал пустой вывод при rc=0")
        return mp4 or None
    finally:
        try:
            anim.lottie_animation_destroy()
        except Exception:  # noqa: BLE001
            pass


def _webm_to_mp4_blocking(data: bytes, ff: str, workdir: str) -> bytes | None:
    src = os.path.join(workdir, "in.webm")
    out = os.path.join(workdir, "out.mp4")
    errf = os.path.join(workdir, "err.txt")
    with open(src, "wb") as fh:
        fh.write(data)
    # Прозрачность webm-стикера флэттим (yuv420p), стороны округляем до чётных.
    cmd = [ff, "-y", "-i", src, "-an",
           "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
           "-c:v", "libx264", "-movflags", "+faststart", out]
    with open(errf, "wb") as e:
        rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=e).returncode
    if rc != 0:
        log.warning("ffmpeg(webm) rc=%s: %s", rc, _tail(errf))
        return None
    try:
        with open(out, "rb") as fh:
            mp4 = fh.read()
    except OSError:
        return None
    if not mp4:
        log.warning("ffmpeg(webm) дал пустой вывод при rc=0")
    return mp4 or None


def _convert_blocking(data: bytes, is_animated: bool, is_video: bool) -> bytes | None:
    ff = _ffmpeg_exe()
    if ff is None:
        return None
    with tempfile.TemporaryDirectory(prefix="mesync-stk-") as d:
        try:
            if is_animated:
                return _tgs_to_mp4_blocking(data, ff, d)
            if is_video:
                return _webm_to_mp4_blocking(data, ff, d)
        except Exception:  # noqa: BLE001
            log.warning("конвертация стикера в mp4 не удалась", exc_info=True)
    return None


async def sticker_to_mp4(data: bytes, *, is_animated: bool, is_video: bool) -> bytes | None:
    """Анимированный (TGS) или видео (WebM) стикер → mp4 (bytes) или None при неудаче.

    Неблокирующе: рендер+ffmpeg выполняются в пуле потоков. None означает «не вышло»
    (нет тулинга/битый стикер/ошибка ffmpeg) — вызывающий деградирует на статичное превью."""
    if not data or not (is_animated or is_video):
        return None
    return await asyncio.to_thread(_convert_blocking, data, is_animated, is_video)

"""Cut evenly spaced JPEG frames out of a video file.

Immich only produces one poster thumbnail per video. To let a model "watch" a
clip, the server downloads the original and decodes frames locally with one of
two backends, tried in this order:

1. PyAV (``pip install immich-photo-manager[video]``), in-process, no binary.
2. The ``ffmpeg`` binary on PATH (``ffprobe`` for the duration when present).

Every frame is one image for the model, so ``count`` is capped at MAX_FRAMES.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile
from fractions import Fraction

MAX_FRAMES = 12
SIZES = {"thumbnail": 250, "preview": 1440}


class NoVideoBackend(RuntimeError):
    """Neither PyAV nor ffmpeg is available."""


def clamp_count(count: int) -> int:
    return max(1, min(int(count or 1), MAX_FRAMES))


def frame_timestamps(duration: float, count: int) -> list[float]:
    """Centres of `count` equal bins over [0, duration] (skips the black first frame)."""
    if duration <= 0:
        return [0.0] * count
    return [round(duration * (i + 0.5) / count, 3) for i in range(count)]


def _pyav_available() -> bool:
    try:
        import av  # noqa: F401
    except Exception:
        return False
    return True


def _scaled(width: int, height: int, target: int) -> tuple[int, int]:
    """Scale so the longer side is `target` (never upscale), even dimensions."""
    longest = max(width, height)
    if longest <= target:
        w, h = width, height
    else:
        ratio = target / longest
        w, h = round(width * ratio), round(height * ratio)
    return max(2, w - w % 2), max(2, h - h % 2)


# ── backend: PyAV ───────────────────────────────────────────


def _extract_pyav(path: str, count: int, target: int) -> dict:
    import av

    frames = []
    with av.open(path) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        duration = (
            float(container.duration / av.time_base) if container.duration
            else float(stream.duration * stream.time_base) if stream.duration else 0.0
        )
        w, h = _scaled(stream.codec_context.width, stream.codec_context.height, target)
        for ts in frame_timestamps(duration, count):
            container.seek(int(ts / stream.time_base), stream=stream, backward=True)
            picked = None
            for frame in container.decode(stream):
                picked = frame
                if frame.time is not None and frame.time >= ts:
                    break
            if picked is None:
                continue
            codec = av.CodecContext.create("mjpeg", "w")
            codec.width, codec.height = w, h
            codec.pix_fmt = "yuvj420p"
            codec.time_base = Fraction(1, 25)
            out = picked.reformat(width=w, height=h, format="yuvj420p")
            packets = codec.encode(out) + codec.encode(None)
            frames.append(_entry(ts, b"".join(bytes(p) for p in packets)))
    return {"duration": round(duration, 3), "backend": "pyav", "frames": frames}


# ── backend: ffmpeg binary ──────────────────────────────────

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def _ffmpeg_duration(path: str) -> float:
    if shutil.which("ffprobe"):
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True,
        ).stdout.strip()
        try:
            return float(out)
        except ValueError:
            pass
    err = subprocess.run(["ffmpeg", "-i", path], capture_output=True, text=True).stderr
    m = _DURATION_RE.search(err)
    if not m:
        return 0.0
    hh, mm, ss = m.groups()
    return int(hh) * 3600 + int(mm) * 60 + float(ss)


def _extract_ffmpeg(path: str, count: int, target: int) -> dict:
    duration = _ffmpeg_duration(path)
    scale = f"scale='if(gt(iw,ih),min({target},iw),-2)':'if(gt(iw,ih),-2,min({target},ih))'"
    frames = []
    for ts in frame_timestamps(duration, count):
        proc = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-ss", f"{ts:.3f}", "-i", path,
             "-frames:v", "1", "-vf", scale, "-f", "image2", "-c:v", "mjpeg", "pipe:1"],
            capture_output=True,
        )
        if proc.returncode == 0 and proc.stdout:
            frames.append(_entry(ts, proc.stdout))
    return {"duration": round(duration, 3), "backend": "ffmpeg", "frames": frames}


# ── public entry point ──────────────────────────────────────


def _entry(ts: float, jpeg: bytes) -> dict:
    return {"timestamp": ts, "data": base64.b64encode(jpeg).decode("ascii"), "type": "image/jpeg"}


def extract_frames(data: bytes, count: int, size: str = "thumbnail", backend: str | None = None) -> dict:
    """Decode `count` JPEG frames from video bytes.

    Returns {"duration": s, "backend": name, "frames": [{timestamp, data(b64), type}]}.
    Raises NoVideoBackend when neither PyAV nor ffmpeg can be used.
    """
    count = clamp_count(count)
    target = SIZES.get(size, SIZES["thumbnail"])
    if backend is None:
        backend = "pyav" if _pyav_available() else "ffmpeg" if shutil.which("ffmpeg") else None
    if backend is None:
        raise NoVideoBackend(
            "Video frame extraction needs a decoder: install the optional extra "
            "`pip install immich-photo-manager[video]` (PyAV) or put `ffmpeg` on PATH."
        )
    fd, path = tempfile.mkstemp(suffix=".mp4", prefix="immich-video-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        if backend == "pyav":
            return _extract_pyav(path, count, target)
        return _extract_ffmpeg(path, count, target)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

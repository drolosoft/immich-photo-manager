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

MAX_FRAMES = 120       # hard cap per call (model tools) and per video (PDF)
CONFIRM_ABOVE = 12     # model tools ask for confirm=True above this
TOKENS_PER_FRAME = {"thumbnail": 1600, "preview": 6400}  # measured 2026-08-26 / upper-bound guess
SIZES = {"thumbnail": 250, "preview": 1440}


class NoVideoBackend(RuntimeError):
    """Neither PyAV nor ffmpeg is available."""


class TooManyFrames(ValueError):
    """The request would exceed MAX_FRAMES."""


def clamp_count(count: int) -> int:
    return max(1, min(int(count or 1), MAX_FRAMES))


def segment_bounds(duration: float, start: float, end: float) -> tuple[float, float]:
    """Clamp segment bounds to valid range [0, duration]."""
    start = max(0.0, float(start or 0.0))
    end = float(end or 0.0)
    if end <= 0 or end > duration:
        end = duration
    if end <= start:
        end = duration if duration > start else start
    return start, end


def frame_timestamps(duration: float, count: int, start: float = 0.0, end: float = 0.0) -> list[float]:
    """Centres of `count` equal bins over [start, end] (skips the black first frame)."""
    if duration <= 0:
        return [0.0] * count
    segment_start, segment_end = segment_bounds(duration, start, end)
    span = segment_end - segment_start
    return [round(segment_start + span * (i + 0.5) / count, 3) for i in range(count)]


def interval_timestamps(duration: float, interval: float, start: float = 0.0, end: float = 0.0) -> list[float]:
    """One frame every `interval` seconds over [start, end]: the centres of n = max(1, span // interval) equal bins."""
    if duration <= 0 or interval <= 0:
        return []
    segment_start, segment_end = segment_bounds(duration, start, end)
    span = segment_end - segment_start
    slots = max(1, int(span // interval))
    if slots > 10 * MAX_FRAMES:
        raise TooManyFrames(_too_many(slots))
    return [round(segment_start + span * (i + 0.5) / slots, 3) for i in range(slots)]


def _too_many(slots: int) -> str:
    """Error message for exceeding frame cap."""
    return (
        f"{slots} frames requested; the cap is {MAX_FRAMES} per call. "
        f"Narrow the segment with start/end or use a larger interval."
    )


def plan_timestamps(duration: float, count: int, interval: float, start: float, end: float) -> list[float]:
    """Timestamps for a request; `interval` wins over `count`. Raises TooManyFrames above MAX_FRAMES."""
    if interval and interval > 0:
        timestamp = interval_timestamps(duration, interval, start, end)
    else:
        timestamp = frame_timestamps(duration, clamp_count(count), start, end)
    if len(timestamp) > MAX_FRAMES:
        raise TooManyFrames(_too_many(len(timestamp)))
    return timestamp


def estimate_tokens(slots: int, size: str = "thumbnail") -> int:
    return slots * TOKENS_PER_FRAME.get(size, TOKENS_PER_FRAME["thumbnail"])


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
        width, height = width, height
    else:
        ratio = target / longest
        width, height = round(width * ratio), round(height * ratio)
    return max(2, width - width % 2), max(2, height - height % 2)


# ── backend: PyAV ───────────────────────────────────────────


def _extract_pyav(path: str, timestamps: list[float], target: int) -> dict:
    import av

    frames = []
    with av.open(path) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        duration = (
            float(container.duration / av.time_base) if container.duration
            else float(stream.duration * stream.time_base) if stream.duration else 0.0
        )
        width, height = _scaled(stream.codec_context.width, stream.codec_context.height, target)
        for timestamp in timestamps:
            container.seek(int(timestamp / stream.time_base), stream=stream, backward=True)
            picked = None
            for frame in container.decode(stream):
                picked = frame
                if frame.time is not None and frame.time >= timestamp:
                    break
            if picked is None:
                continue
            codec = av.CodecContext.create("mjpeg", "w")
            codec.width, codec.height = width, height
            codec.pix_fmt = "yuvj420p"
            codec.time_base = Fraction(1, 25)
            out = picked.reformat(width=width, height=height, format="yuvj420p")
            packets = codec.encode(out) + codec.encode(None)
            frames.append(_entry(timestamp, b"".join(bytes(packet) for packet in packets)))
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
    match = _DURATION_RE.search(err)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _extract_ffmpeg(path: str, timestamps: list[float], target: int) -> dict:
    duration = _ffmpeg_duration(path)
    scale = f"scale='if(gt(iw,ih),min({target},iw),-2)':'if(gt(iw,ih),-2,min({target},ih))'"
    frames = []
    for timestamp in timestamps:
        proc = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-ss", f"{timestamp:.3f}", "-i", path,
             "-frames:v", "1", "-vf", scale, "-f", "image2", "-c:v", "mjpeg", "pipe:1"],
            capture_output=True,
        )
        if proc.returncode == 0 and proc.stdout:
            frames.append(_entry(timestamp, proc.stdout))
    return {"duration": round(duration, 3), "backend": "ffmpeg", "frames": frames}


# ── public entry point ──────────────────────────────────────


def _entry(timestamp: float, jpeg: bytes) -> dict:
    return {"timestamp": timestamp, "data": base64.b64encode(jpeg).decode("ascii"), "type": "image/jpeg"}


def _duration(path: str) -> float:
    if _pyav_available():
        import av
        with av.open(path) as container:
            stream = container.streams.video[0]
            if container.duration:
                return float(container.duration / av.time_base)
            if stream.duration:
                return float(stream.duration * stream.time_base)
            return 0.0
    return _ffmpeg_duration(path)


def _to_tempfile(data: bytes) -> str:
    descriptor, path = tempfile.mkstemp(suffix=".mp4", prefix="immich-video-")
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
    return path


def probe_duration(data: bytes) -> float:
    path = _to_tempfile(data)
    try:
        return round(_duration(path), 3)
    finally:
        os.unlink(path)


def extract_frames(
    data: bytes, count: int = 6, size: str = "thumbnail", backend: str | None = None,
    start: float = 0.0, end: float = 0.0, interval: float = 0.0,
) -> dict:
    """Decode frames from video bytes; `interval` (seconds) wins over `count`.

    Returns {"duration": s, "backend": name, "frames": [{timestamp, data(b64), type}]}.
    Raises NoVideoBackend when neither PyAV nor ffmpeg can be used, TooManyFrames above MAX_FRAMES.
    """
    target = SIZES.get(size, SIZES["thumbnail"])
    if backend is None:
        backend = "pyav" if _pyav_available() else "ffmpeg" if shutil.which("ffmpeg") else None
    if backend is None:
        raise NoVideoBackend(
            "Video frame extraction needs a decoder: install the optional extra "
            "`pip install immich-photo-manager[video]` (PyAV) or put `ffmpeg` on PATH."
        )
    path = _to_tempfile(data)
    try:
        duration = _duration(path)
        timestamps = plan_timestamps(duration, count, interval, start, end)
        if backend == "pyav":
            return _extract_pyav(path, timestamps, target)
        return _extract_ffmpeg(path, timestamps, target)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

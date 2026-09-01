"""Cut evenly spaced JPEG frames out of a video file.

Immich only produces one poster thumbnail per video. To let a model "watch" a
clip, the server downloads the original and decodes frames locally with one of
two backends, tried in this order:

1. PyAV (a dependency of the package since 1.7.1), in-process, no binary.
2. The ``ffmpeg`` binary on PATH (``ffprobe`` for the duration when present).

The planning functions (`frame_timestamps`, `interval_timestamps`,
`plan_timestamps`) are pure and decide where to cut; `extract_frames` does the
decoding. Every frame is one image for the model, so the number of frames per
call is capped at MAX_FRAMES and the tools ask for confirmation above CONFIRM_ABOVE.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile

# Hard cap on frames per call (model tools) and per video (PDF export).
MAX_FRAMES = 120

# Above this many frames the model tools return a plan and wait for confirm=True.
CONFIRM_ABOVE = 12

# Rough context cost of one frame. The thumbnail figure was measured in Claude
# Code on 2026-08-26 (12 thumbnails of a 568x320 clip = 19.2k tokens); the
# preview figure is an upper-bound guess scaled by pixel count.
TOKENS_PER_FRAME = {"thumbnail": 1600, "preview": 6400}

# Longest side of a frame in pixels, same sizes Immich uses for its thumbnails.
SIZES = {"thumbnail": 250, "preview": 1440}

# Interval requests are refused early when they would plan this many times the
# cap, so a 1 ms interval over an hour never builds a million timestamps.
INTERVAL_OVERFLOW_FACTOR = 10

# The "Duration: 00:00:03.00" line ffmpeg prints on stderr for any input.
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


class NoVideoBackend(RuntimeError):
    """Neither PyAV nor ffmpeg is available."""


class TooManyFrames(ValueError):
    """The request would exceed MAX_FRAMES."""


def clamp_count(count: int) -> int:
    """`count` forced into 1..MAX_FRAMES (a missing or zero count means one frame)."""
    return max(1, min(int(count or 1), MAX_FRAMES))


def segment_bounds(duration: float, start: float, end: float) -> tuple[float, float]:
    """The [start, end] segment clamped to the video: end 0 means "to the end"."""
    start = max(0.0, float(start or 0.0))
    end = float(end or 0.0)
    if end <= 0 or end > duration:
        end = duration
    if end <= start:
        end = duration if duration > start else start
    return start, end


def frame_timestamps(duration: float, count: int, start: float = 0.0, end: float = 0.0) -> list[float]:
    """Centres of `count` equal bins over [start, end].

    Bin centres rather than bin edges so the first frame is never the black
    frame at second zero and the last one is never the fade-out.
    """
    if duration <= 0:
        return [0.0] * count
    segment_start, segment_end = segment_bounds(duration, start, end)
    span = segment_end - segment_start
    return [round(segment_start + span * (position + 0.5) / count, 3) for position in range(count)]


def interval_timestamps(duration: float, interval: float, start: float = 0.0, end: float = 0.0) -> list[float]:
    """One frame every `interval` seconds over [start, end].

    Implemented as the centres of `span // interval` equal bins (at least one),
    so a short segment still yields a frame and none lands on the boundaries.
    """
    if duration <= 0 or interval <= 0:
        return []
    segment_start, segment_end = segment_bounds(duration, start, end)
    span = segment_end - segment_start
    slots = max(1, int(span // interval))
    if slots > INTERVAL_OVERFLOW_FACTOR * MAX_FRAMES:
        raise TooManyFrames(_too_many(slots))
    return [round(segment_start + span * (position + 0.5) / slots, 3) for position in range(slots)]


def _too_many(requested: int) -> str:
    """The error text for a request above the cap, with the way out."""
    return (
        f"{requested} frames requested; the cap is {MAX_FRAMES} per call. "
        f"Narrow the segment with start/end or use a larger interval."
    )


def plan_timestamps(duration: float, count: int, interval: float, start: float, end: float) -> list[float]:
    """Timestamps for a request; `interval` wins over `count`. Raises TooManyFrames above MAX_FRAMES."""
    if interval and interval > 0:
        timestamps = interval_timestamps(duration, interval, start, end)
    else:
        timestamps = frame_timestamps(duration, clamp_count(count), start, end)
    if len(timestamps) > MAX_FRAMES:
        raise TooManyFrames(_too_many(len(timestamps)))
    return timestamps


def estimate_tokens(frames: int, size: str = "thumbnail") -> int:
    """Approximate context cost of `frames` frames at `size`, for the confirmation plan."""
    return frames * TOKENS_PER_FRAME.get(size, TOKENS_PER_FRAME["thumbnail"])


# A frame must beat the bin centre by this much grayscale spread to replace it,
# so stable footage keeps its exact centres and only dead frames get dodged.
DODGE_MARGIN = 5.0


def _liveliness(image) -> float:
    """How much a frame has to show: the grayscale spread. A black (or blown-out,
    or uniform) frame scores near zero; anything with detail scores far above."""
    from PIL import ImageStat

    small = image.convert("L")
    small.thumbnail((64, 64))
    return ImageStat.Stat(small).stddev[0]


def _candidates(timestamp: float, radius: float, duration: float) -> list[float]:
    """The centre first (it wins ties), then a step to each side, clamped to the clip."""
    if radius <= 0:
        return [timestamp]
    moments = [timestamp, timestamp - radius, timestamp + radius]
    return [min(max(moment, 0.05), max(duration - 0.05, 0.05)) for moment in moments]


def _dodge_radius(timestamps: list[float], duration: float) -> float:
    """A quarter of the spacing between frames: far enough to escape a dead patch,
    close enough that the label still names the same moment of the video."""
    if len(timestamps) > 1:
        return (timestamps[1] - timestamps[0]) / 4
    return duration / 4


def _pyav_available() -> bool:
    """True when the optional PyAV extra is installed."""
    try:
        import av  # noqa: F401
    except Exception:
        return False
    return True


def _entry(timestamp: float, jpeg: bytes) -> dict:
    """One frame as the tools return it: timestamp plus base64 JPEG."""
    return {"timestamp": timestamp, "data": base64.b64encode(jpeg).decode("ascii"), "type": "image/jpeg"}


# ── backend: PyAV ───────────────────────────────────────


def _pyav_duration(container, stream) -> float:
    """Seconds of video from the container, else from the stream, else unknown (0)."""
    import av

    if container.duration:
        return float(container.duration / av.time_base)
    if stream.duration:
        return float(stream.duration * stream.time_base)
    return 0.0


def _pyav_frame_at(container, stream, timestamp: float):
    """The first decoded frame at or after `timestamp`, or None when the seek finds nothing."""
    # Seek to the keyframe before the timestamp, then decode forward to it.
    container.seek(int(timestamp / stream.time_base), stream=stream, backward=True)
    picked = None
    for frame in container.decode(stream):
        picked = frame
        if frame.time is not None and frame.time >= timestamp:
            break
    return picked


def _pyav_jpeg(frame, target: int, rotation: int) -> bytes:
    """One decoded frame as a JPEG: rotated the way the display matrix asks, longest side at `target`."""
    import io

    image = frame.to_image()
    # Phone videos are stored sideways with a rotation flag; PyAV decodes the
    # stored pixels and, unlike ffmpeg, never applies the flag. `frame.rotation`
    # carries the flag's angle in degrees counterclockwise, the same convention
    # Pillow uses (the direction is pinned against ffmpeg's auto-rotation in the tests).
    if rotation % 360:
        image = image.rotate(rotation % 360, expand=True)
    image.thumbnail((target, target))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def _extract_pyav(path: str, timestamps: list[float], target: int, radius: float = 0.0) -> dict:
    """Decode the frames at `timestamps` with PyAV, in process.

    With a `radius`, each timestamp is a bin centre, not an exact order: the
    centre and one step to each side are decoded, and the liveliest one goes
    in, so an evenly spaced strip does not waste slots on dead black frames.
    """
    import av

    frames = []
    with av.open(path) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        duration = _pyav_duration(container, stream)
        for timestamp in timestamps:
            best = None
            for candidate in _candidates(timestamp, radius, duration):
                frame = _pyav_frame_at(container, stream, candidate)
                if frame is None:
                    continue
                score = _liveliness(frame.to_image())
                if best is None or score > best[0] + DODGE_MARGIN:
                    best = (score, candidate, frame)
            if best is None:
                continue
            _score, moment, frame = best
            rotation = int(getattr(frame, "rotation", 0) or 0)
            frames.append(_entry(moment, _pyav_jpeg(frame, target, rotation)))
    return {"duration": round(duration, 3), "backend": "pyav", "frames": frames}


# ── backend: ffmpeg binary ──────────────────────────────


def _ffmpeg_duration(path: str) -> float:
    """Seconds of video via ffprobe when present, else parsed from ffmpeg's banner."""
    if shutil.which("ffprobe"):
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True,
        ).stdout.strip()
        try:
            return float(probe)
        except ValueError:
            pass
    # ffmpeg with an input and no output exits with an error but still prints
    # the "Duration:" line on stderr, which is all we need here.
    banner = subprocess.run(["ffmpeg", "-i", path], capture_output=True, text=True).stderr
    match = _DURATION_RE.search(banner)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _extract_ffmpeg(path: str, timestamps: list[float], target: int, radius: float = 0.0) -> dict:
    """Decode the frames at `timestamps` with the ffmpeg binary, one process per frame.

    With a `radius` the same dodge as the PyAV backend applies: the bin centre
    and one step to each side are decoded, and the liveliest frame goes in.
    """
    import io as io_module

    from PIL import Image

    duration = _ffmpeg_duration(path)
    # Scale the longer side to `target` and keep the other side even (-2).
    scale = f"scale='if(gt(iw,ih),min({target},iw),-2)':'if(gt(iw,ih),-2,min({target},ih))'"
    frames = []
    for timestamp in timestamps:
        best = None
        for candidate in _candidates(timestamp, radius, duration):
            proc = subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-ss", f"{candidate:.3f}", "-i", path,
                 "-frames:v", "1", "-vf", scale, "-f", "image2", "-c:v", "mjpeg", "pipe:1"],
                capture_output=True,
            )
            if proc.returncode != 0 or not proc.stdout:
                continue
            with Image.open(io_module.BytesIO(proc.stdout)) as decoded:
                score = _liveliness(decoded)
            if best is None or score > best[0] + DODGE_MARGIN:
                best = (score, candidate, proc.stdout)
        if best is not None:
            _score, moment, data = best
            frames.append(_entry(moment, data))
    return {"duration": round(duration, 3), "backend": "ffmpeg", "frames": frames}


# ── public entry point ──────────────────────────────────


def _duration(path: str) -> float:
    """Seconds of video at `path`, through whichever backend is installed."""
    if _pyav_available():
        import av

        with av.open(path) as container:
            return _pyav_duration(container, container.streams.video[0])
    return _ffmpeg_duration(path)


def _to_tempfile(data: bytes) -> str:
    """Write the video bytes to a temp file (both backends want a path) and return it."""
    descriptor, path = tempfile.mkstemp(suffix=".mp4", prefix="immich-video-")
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
    return path


def probe_duration(data: bytes) -> float:
    """Seconds of video in `data`, without decoding any frame."""
    path = _to_tempfile(data)
    try:
        return round(_duration(path), 3)
    finally:
        os.unlink(path)


def contact_sheets(frames: list[dict], columns: int = 6, per_sheet: int = 30) -> list[dict]:
    """Pack frame entries into contact-sheet images, the timestamp burned under each cell.

    Sixty frames become two images instead of sixty, which is the difference
    between a model being able to skim a long video and not affording to.
    Returns entries shaped like frames plus a `timestamps` list per sheet.
    """
    import io

    from PIL import Image, ImageDraw

    cell_w, cell_h, label_h = 250, 141, 16
    sheets = []
    for start in range(0, len(frames), per_sheet):
        batch = frames[start:start + per_sheet]
        rows = (len(batch) + columns - 1) // columns
        canvas = Image.new("RGB", (columns * cell_w, rows * (cell_h + label_h)), "white")
        draw = ImageDraw.Draw(canvas)
        for position, frame in enumerate(batch):
            image = Image.open(io.BytesIO(base64.b64decode(frame["data"]))).convert("RGB")
            image.thumbnail((cell_w, cell_h))
            left = (position % columns) * cell_w
            top = (position // columns) * (cell_h + label_h)
            canvas.paste(image, (left, top))
            draw.text((left + 4, top + cell_h + 2), f"{frame['timestamp']:.1f}s", fill="black")
        buffer = io.BytesIO()
        canvas.save(buffer, format="JPEG", quality=85)
        sheets.append({
            "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
            "type": "image/jpeg",
            "timestamps": [frame["timestamp"] for frame in batch],
        })
    return sheets


def extract_frames_at(data: bytes, times: list[float], size: str = "thumbnail",
                      backend: str | None = None) -> dict:
    """Decode frames at exact moments (seconds), for a caller that already chose them.

    The moments are clamped to the video, sorted, and cut in one decoding pass.
    Same return shape and errors as `extract_frames`; the MAX_FRAMES cap applies.
    """
    if len(times) > MAX_FRAMES:
        raise TooManyFrames(_too_many(len(times)))
    target = SIZES.get(size, SIZES["thumbnail"])
    if backend is None:
        backend = "pyav" if _pyav_available() else "ffmpeg" if shutil.which("ffmpeg") else None
    if backend is None:
        raise NoVideoBackend(
            "Video frame extraction needs a decoder: install PyAV (`pip install av`, "
            "it ships with immich-photo-manager since 1.7.1) or put `ffmpeg` on PATH."
        )
    path = _to_tempfile(data)
    try:
        duration = _duration(path)
        upper = duration if duration > 0 else max(times, default=0.0)
        timestamps = sorted(round(min(max(moment, 0.0), upper), 3) for moment in times)
        if backend == "pyav":
            return _extract_pyav(path, timestamps, target)
        return _extract_ffmpeg(path, timestamps, target)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


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
            "Video frame extraction needs a decoder: install PyAV (`pip install av`, "
            "it ships with immich-photo-manager since 1.7.1) or put `ffmpeg` on PATH."
        )
    path = _to_tempfile(data)
    try:
        duration = _duration(path)
        timestamps = plan_timestamps(duration, count, interval, start, end)
        # Spaced frames are bin centres, not exact orders: each may be swapped
        # for a livelier neighbour inside its own bin (a time-lapse can be
        # pitch black at the centre and full of sky a quarter-bin away).
        radius = _dodge_radius(timestamps, duration)
        if backend == "pyav":
            return _extract_pyav(path, timestamps, target, radius)
        return _extract_ffmpeg(path, timestamps, target, radius)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

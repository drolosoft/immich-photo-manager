"""get_video_frames: playback download → evenly spaced frames → image blocks.

Immich generates one poster thumbnail per video and no per-frame previews
for any client. The plugin goes one step further: it downloads the original
via GET /assets/{id}/video/playback and cuts `count` frames evenly spaced over
the duration, with PyAV (optional extra `[video]`) or the `ffmpeg` binary.
"""

import base64
import json
import shutil
import subprocess

import httpx
import pytest
import respx
from mcp.server.fastmcp import Image

from immich_mcp_server import server, video_frames
from immich_mcp_server.immich_client import ImmichClient


# ── the client fetches the playback bytes ───────────────────


@pytest.mark.asyncio
async def test_get_video_playback_streams_bytes(env_credentials, isolated_cache):
    client = ImmichClient()
    with respx.mock(base_url="https://env.example.com") as mock:
        mock.get("/api/assets/vid1/video/playback").mock(
            return_value=httpx.Response(200, content=b"MP4BYTES",
                                        headers={"content-type": "video/mp4"})
        )
        data = await client.get_video_playback("vid1")
    assert data == b"MP4BYTES"


# ── timestamps are evenly spaced, never at the very edges ───


def test_frame_timestamps_are_centered_bins():
    assert video_frames.frame_timestamps(3.0, 3) == [0.5, 1.5, 2.5]
    assert video_frames.frame_timestamps(10.0, 1) == [5.0]
    assert video_frames.frame_timestamps(0.0, 4) == [0.0, 0.0, 0.0, 0.0]


def test_count_is_clamped_to_1_120():
    assert video_frames.clamp_count(0) == 1
    assert video_frames.clamp_count(6) == 6
    assert video_frames.clamp_count(99) == 99
    assert video_frames.clamp_count(999) == video_frames.MAX_FRAMES == 120


def test_segment_timestamps_are_centered_inside_segment():
    assert video_frames.frame_timestamps(24.0, 2, start=8.0, end=12.0) == [9.0, 11.0]
    assert video_frames.frame_timestamps(24.0, 2, start=20.0) == [21.0, 23.0]  # end=0 → to the end


def test_interval_timestamps_one_per_second():
    assert video_frames.interval_timestamps(3.0, 1.0) == [0.5, 1.5, 2.5]
    assert video_frames.interval_timestamps(24.0, 10.0, start=8.0, end=12.0) == [10.0]
    # Segment-relative formula: n = max(1, span // interval), frames at centers of n equal bins
    assert video_frames.interval_timestamps(100.0, 10.0, start=25.0, end=35.0) == [30.0]
    assert video_frames.interval_timestamps(100.0, 10.0, start=8.0, end=9.0) == [8.5]


def test_plan_timestamps_caps_at_120():
    with pytest.raises(video_frames.TooManyFrames) as exc:
        video_frames.plan_timestamps(300.0, count=0, interval=1.0, start=0.0, end=0.0)
    assert "120" in str(exc.value) and "start" in str(exc.value)
    assert len(video_frames.plan_timestamps(300.0, count=0, interval=5.0, start=0.0, end=0.0)) == 60
    assert video_frames.plan_timestamps(3.0, count=2, interval=0.0, start=0.0, end=0.0) == [0.75, 2.25]
    # Early bailout: interval_timestamps raises before building millions of floats
    with pytest.raises(video_frames.TooManyFrames) as exc:
        video_frames.plan_timestamps(3600.0, count=0, interval=0.001, start=0.0, end=0.0)
    assert "frames requested" in str(exc.value) and int(str(exc.value).split()[0]) > 1000000


def test_estimate_tokens():
    assert video_frames.estimate_tokens(12, "thumbnail") == 19200
    assert video_frames.estimate_tokens(2, "preview") == 12800


def test_extract_frames_segment_and_interval(clip):
    seg = video_frames.extract_frames(clip, count=2, size="thumbnail", start=1.0, end=2.0)
    assert [frame["timestamp"] for frame in seg["frames"]] == [1.25, 1.75]
    every = video_frames.extract_frames(clip, count=0, size="thumbnail", interval=1.0)
    assert [frame["timestamp"] for frame in every["frames"]] == [0.5, 1.5]  # 2 s clip


def test_probe_duration(clip):
    assert 1.9 <= video_frames.probe_duration(clip) <= 2.1


# ── backends: a real 2-second clip, decoded by whatever is installed ──


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not on PATH; cannot synthesize a clip")
    path = tmp_path_factory.mktemp("clip") / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
         "color=c=purple:s=320x240:d=2", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )
    return path.read_bytes()


def _assert_jpeg_frames(frames, count, duration):
    assert len(frames) == count
    for frame in frames:
        assert frame["type"] == "image/jpeg"
        assert base64.b64decode(frame["data"])[:2] == b"\xff\xd8"  # JPEG SOI
        assert 0 <= frame["timestamp"] <= duration


def test_ffmpeg_backend_extracts_frames(clip):
    result = video_frames.extract_frames(clip, count=3, size="thumbnail", backend="ffmpeg")
    assert 1.9 <= result["duration"] <= 2.1
    _assert_jpeg_frames(result["frames"], 3, result["duration"])


def test_pyav_backend_extracts_frames(clip):
    pytest.importorskip("av")
    result = video_frames.extract_frames(clip, count=3, size="thumbnail", backend="pyav")
    assert 1.9 <= result["duration"] <= 2.1
    _assert_jpeg_frames(result["frames"], 3, result["duration"])


def test_no_backend_names_both_options(monkeypatch):
    monkeypatch.setattr(video_frames, "_pyav_available", lambda: False)
    monkeypatch.setattr(video_frames.shutil, "which", lambda name: None)
    with pytest.raises(video_frames.NoVideoBackend) as exc:
        video_frames.extract_frames(b"", count=2, size="thumbnail")
    msg = str(exc.value)
    assert "immich-photo-manager[video]" in msg and "ffmpeg" in msg


# ── the tools ───────────────────────────────────────────────

JPEG = b"\xff\xd8\xff\xe0FAKE"
JPEG_B64 = base64.b64encode(JPEG).decode("ascii")


class StubClient:
    async def get_video_playback(self, asset_id):
        return b"MP4"


def _fake_extract(data, count, size, backend=None, start=0.0, end=0.0, interval=0.0):
    return {
        "duration": 3.0,
        "backend": "stub",
        "frames": [{"timestamp": float(i), "data": JPEG_B64, "type": "image/jpeg"}
                   for i in range(count)],
    }


@pytest.mark.asyncio
async def test_get_video_frames_gate_above_12_returns_plan(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "probe_duration", lambda data: 24.0)
    monkeypatch.setattr(video_frames, "extract_frames", _fake_extract)
    raw = await server.get_video_frames(fake_ctx(StubClient()), asset_id="vid1", count=0, interval=1.0)
    data = json.loads(raw)
    assert data["confirm_required"] is True and data["frames_planned"] == 24
    assert data["estimated_tokens"] == 24 * 1600 and data["segment"] == [0.0, 24.0]


@pytest.mark.asyncio
async def test_get_video_frames_confirm_true_extracts(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "probe_duration", lambda data: 24.0)
    monkeypatch.setattr(video_frames, "extract_frames", _fake_extract)
    result = await server.get_video_frames(fake_ctx(StubClient()), asset_id="vid1", count=20, confirm=True)
    assert len(result) == 20 and all(isinstance(item, Image) for item in result)


@pytest.mark.asyncio
async def test_get_video_frames_over_cap_is_error_json(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "probe_duration", lambda data: 300.0)
    raw = await server.get_video_frames(fake_ctx(StubClient()), asset_id="vid1", interval=1.0, confirm=True)
    assert "120" in json.loads(raw)["error"]


@pytest.mark.asyncio
async def test_get_video_frames_zero_duration_with_interval_is_error_json(fake_ctx, monkeypatch):
    """A duration probe that returns 0 (unreadable container, etc.) combined with
    `interval` must not silently plan zero frames; it must surface a clear error."""
    monkeypatch.setattr(video_frames, "probe_duration", lambda data: 0.0)
    raw = await server.get_video_frames(fake_ctx(StubClient()), asset_id="vid1", interval=1.0)
    data = json.loads(raw)
    assert "error" in data and "duration" in data["error"]
    assert data["duration"] == 0.0


@pytest.mark.asyncio
async def test_get_video_frames_returns_image_blocks(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "probe_duration", lambda data: 10.0)
    monkeypatch.setattr(video_frames, "extract_frames", _fake_extract)
    result = await server.get_video_frames(fake_ctx(StubClient()), asset_id="vid1", count=4)
    assert [type(item) for item in result] == [Image] * 4
    assert result[0].data == JPEG
    assert result[0].to_image_content().mimeType == "image/jpeg"


@pytest.mark.asyncio
async def test_get_video_frames_caps_count(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "probe_duration", lambda data: 60.0)
    monkeypatch.setattr(video_frames, "extract_frames", _fake_extract)
    raw = await server.get_video_frames(fake_ctx(StubClient()), asset_id="vid1", count=50)
    data = json.loads(raw)
    assert data["confirm_required"] is True and data["frames_planned"] == 50


@pytest.mark.asyncio
async def test_get_video_frames_json_has_timestamps_and_base64(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "probe_duration", lambda data: 10.0)
    monkeypatch.setattr(video_frames, "extract_frames", _fake_extract)
    raw = await server.get_video_frames_json(fake_ctx(StubClient()), asset_id="vid1", count=2)
    assert isinstance(raw, str)
    data = json.loads(raw)
    assert data["asset_id"] == "vid1" and data["duration"] == 3.0 and data["count"] == 2
    assert data["frames"][1]["timestamp"] == 1.0
    assert data["frames"][1]["data"] == JPEG_B64 and data["frames"][1]["type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_get_video_frames_json_reports_missing_backend(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "probe_duration", lambda data: 10.0)
    def boom(*args, **kwargs):
        raise video_frames.NoVideoBackend("install immich-photo-manager[video] or ffmpeg")
    monkeypatch.setattr(video_frames, "extract_frames", boom)
    data = json.loads(await server.get_video_frames_json(fake_ctx(StubClient()), asset_id="vid1"))
    assert "immich-photo-manager[video]" in data["error"]


@pytest.mark.asyncio
async def test_get_video_frames_gate_segment_clamps_end(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "probe_duration", lambda data: 24.0)
    monkeypatch.setattr(video_frames, "extract_frames", _fake_extract)
    raw = await server.get_video_frames(fake_ctx(StubClient()), asset_id="vid1", count=20, end=1000.0)
    data = json.loads(raw)
    assert data["segment"] == [0.0, 24.0]


@pytest.mark.asyncio
async def test_get_video_frames_reports_missing_backend(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "probe_duration", lambda data: 10.0)
    def boom(*args, **kwargs):
        raise video_frames.NoVideoBackend("no decoder")
    monkeypatch.setattr(video_frames, "extract_frames", boom)
    raw = await server.get_video_frames(fake_ctx(StubClient()), asset_id="vid1")
    data = json.loads(raw)
    assert "no decoder" in data["error"]

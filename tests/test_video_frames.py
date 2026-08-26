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


def test_count_is_clamped_to_1_12():
    assert video_frames.clamp_count(0) == 1
    assert video_frames.clamp_count(6) == 6
    assert video_frames.clamp_count(99) == video_frames.MAX_FRAMES == 12


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
    for f in frames:
        assert f["type"] == "image/jpeg"
        assert base64.b64decode(f["data"])[:2] == b"\xff\xd8"  # JPEG SOI
        assert 0 <= f["timestamp"] <= duration


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


def _fake_extract(data, count, size, backend=None):
    return {
        "duration": 3.0,
        "backend": "stub",
        "frames": [{"timestamp": float(i), "data": JPEG_B64, "type": "image/jpeg"}
                   for i in range(count)],
    }


@pytest.mark.asyncio
async def test_get_video_frames_returns_image_blocks(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "extract_frames", _fake_extract)
    result = await server.get_video_frames(fake_ctx(StubClient()), asset_id="vid1", count=4)
    assert [type(x) for x in result] == [Image] * 4
    assert result[0].data == JPEG
    assert result[0].to_image_content().mimeType == "image/jpeg"


@pytest.mark.asyncio
async def test_get_video_frames_caps_count(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "extract_frames", _fake_extract)
    result = await server.get_video_frames(fake_ctx(StubClient()), asset_id="vid1", count=50)
    assert len(result) == 12


@pytest.mark.asyncio
async def test_get_video_frames_json_has_timestamps_and_base64(fake_ctx, monkeypatch):
    monkeypatch.setattr(video_frames, "extract_frames", _fake_extract)
    raw = await server.get_video_frames_json(fake_ctx(StubClient()), asset_id="vid1", count=2)
    assert isinstance(raw, str)
    d = json.loads(raw)
    assert d["asset_id"] == "vid1" and d["duration"] == 3.0 and d["count"] == 2
    assert d["frames"][1]["timestamp"] == 1.0
    assert d["frames"][1]["data"] == JPEG_B64 and d["frames"][1]["type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_get_video_frames_json_reports_missing_backend(fake_ctx, monkeypatch):
    def boom(*a, **k):
        raise video_frames.NoVideoBackend("install immich-photo-manager[video] or ffmpeg")
    monkeypatch.setattr(video_frames, "extract_frames", boom)
    d = json.loads(await server.get_video_frames_json(fake_ctx(StubClient()), asset_id="vid1"))
    assert "immich-photo-manager[video]" in d["error"]

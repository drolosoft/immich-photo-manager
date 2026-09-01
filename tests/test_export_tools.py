"""export_pdf / get_export_preview: client helpers and tools."""
import base64
import io
import json
import os

import httpx
import pytest
import respx

from immich_mcp_server import pdf_export, server
from immich_mcp_server.tools.export import _duration_seconds
from immich_mcp_server.immich_client import ImmichClient

BASE = "https://env.example.com"


def _png(color):
    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (64, 40), color).save(buf, format="PNG")
    return buf.getvalue()


PNG_RED = _png("red")


def _asset(i, kind="IMAGE"):
    return {"id": f"a{i}", "type": kind, "originalFileName": f"{i}.jpg", "fileCreatedAt": "2026-01-0%dT10:00:00Z" % i,
            "duration": "0:00:03.000" if kind == "VIDEO" else None,
            "exifInfo": {"city": "Barcelona", "country": "Spain", "make": "Apple", "model": "iPhone", "latitude": 41.4, "longitude": 2.2},
            "people": [{"name": "Curie"}], "tags": [{"name": "trip"}]}


@pytest.mark.asyncio
async def test_get_assets_by_ids_keeps_order_and_drops_missing(env_credentials, isolated_cache):
    with respx.mock(base_url=BASE) as mock:
        route = mock.post("/api/search/metadata").mock(
            return_value=httpx.Response(200, json={"assets": {"items": [_asset(2), _asset(1)], "nextPage": None}}))
        mock.get("/api/assets/zz").mock(return_value=httpx.Response(404, json={"message": "not found"}))
        got = await ImmichClient().get_assets_by_ids(["a1", "a2", "zz"])
    body = json.loads(route.calls[0].request.content)
    assert body["ids"] == ["a1", "a2", "zz"] and body["withExif"] is True and body["withPeople"] is True
    assert [args["id"] for args in got] == ["a1", "a2"]


@pytest.mark.asyncio
async def test_get_assets_by_ids_falls_back_to_get_asset_when_ids_filter_ignored(env_credentials, isolated_cache):
    """Immich 2.7.5 ignores `ids` on /search/metadata and returns unrelated assets instead;
    any requested id missing from the response must be fetched via GET /assets/{id}."""
    with respx.mock(base_url=BASE) as mock:
        mock.post("/api/search/metadata").mock(
            return_value=httpx.Response(200, json={"assets": {"items": [_asset(9)], "nextPage": None}}))
        mock.get("/api/assets/a1").mock(return_value=httpx.Response(200, json=_asset(1)))
        mock.get("/api/assets/a2").mock(return_value=httpx.Response(200, json=_asset(2)))
        got = await ImmichClient().get_assets_by_ids(["a1", "a2"])
    assert [args["id"] for args in got] == ["a1", "a2"]


@pytest.mark.asyncio
async def test_get_assets_by_ids_fallback_reraises_non_404(env_credentials, isolated_cache):
    """A 500 (or any non-404) from the per-id fallback must propagate, not be dropped
    silently like a genuinely missing asset."""
    with respx.mock(base_url=BASE) as mock:
        mock.post("/api/search/metadata").mock(
            return_value=httpx.Response(200, json={"assets": {"items": [], "nextPage": None}}))
        mock.get("/api/assets/a1").mock(return_value=httpx.Response(500, json={"message": "boom"}))
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await ImmichClient().get_assets_by_ids(["a1"])
    assert exc_info.value.response.status_code == 500


@pytest.mark.asyncio
async def test_fetch_tile_sets_user_agent(env_credentials, isolated_cache):
    with respx.mock() as mock:
        route = mock.get("https://tile.openstreetmap.org/3/4/2.png").mock(return_value=httpx.Response(200, content=b"PNG"))
        assert await ImmichClient().fetch_tile(3, 4, 2) == b"PNG"
    assert route.calls[0].request.headers["user-agent"].startswith("immich-photo-manager/")


@pytest.mark.asyncio
async def test_fetch_tile_raises_on_server_error(env_credentials, isolated_cache):
    with respx.mock() as mock:
        mock.get("https://tile.openstreetmap.org/3/4/2.png").mock(return_value=httpx.Response(500))
        with pytest.raises(httpx.HTTPStatusError):
            await ImmichClient().fetch_tile(3, 4, 2)


class StubClient:
    def __init__(self, assets=None, video_ok=True):
        self.assets = assets or [_asset(1), _asset(2), _asset(3, "VIDEO")]
        self.video_ok = video_ok

    async def get_album(self, album_id):
        return {"id": album_id, "albumName": "Hypercars"}

    async def get_album_assets(self, album_id, limit=None, with_exif=False):
        return self.assets[:limit] if limit else self.assets

    async def get_assets_by_ids(self, ids, with_exif=True):
        return [asset for asset in self.assets if asset["id"] in ids]

    async def get_asset_thumbnail(self, asset_id, size="thumbnail"):
        return {"data": base64.b64encode(PNG_RED).decode(), "type": "image/png"}

    async def get_video_playback(self, asset_id):
        return b"MP4"

    async def fetch_tile(self, zoom, tile_x, tile_y):
        return PNG_RED

    base_url = "https://env.example.com"


class FailingThumbClient(StubClient):
    """StubClient whose get_asset_thumbnail raises for one asset id."""

    async def get_asset_thumbnail(self, asset_id, size="thumbnail"):
        if asset_id == "a2":
            raise RuntimeError("boom 500")
        return await super().get_asset_thumbnail(asset_id, size)


@pytest.mark.asyncio
async def test_get_export_preview_album(fake_ctx):
    data = json.loads(await server.get_export_preview(fake_ctx(StubClient()), album_id="alb"))
    assert data["title"] == "Hypercars" and data["count"] == 3
    assert data["assets"][2] == {"id": "a3", "type": "VIDEO", "filename": "3.jpg", "taken_at": "2026-01-03T10:00:00Z",
                              "place": "Barcelona, Spain", "people": ["Curie"], "duration": 3.0}
    assert data["assets"][0]["duration"] is None


@pytest.mark.asyncio
async def test_get_export_preview_requires_exactly_one_source(fake_ctx):
    assert "error" in json.loads(await server.get_export_preview(fake_ctx(StubClient())))
    assert "error" in json.loads(await server.get_export_preview(fake_ctx(StubClient()), album_id="a", asset_ids=["x"]))


@pytest.mark.asyncio
async def test_get_export_preview_limit_warns(fake_ctx):
    data = json.loads(await server.get_export_preview(fake_ctx(StubClient()), asset_ids=["a1", "a2", "a3"], limit=2))
    assert data["count"] == 2 and any("limit" in warning for warning in data["warnings"])


def test_duration_seconds_numeric_is_milliseconds():
    assert _duration_seconds({"duration": 900}) == 0.9
    assert _duration_seconds({"duration": 23567}) == 23.567
    assert _duration_seconds({"duration": "0:00:03.000"}) == 3.0
    assert _duration_seconds({"duration": None}) == 0.0


def _fake_frames(data, count=6, size="thumbnail", backend=None, start=0.0, end=0.0, interval=0.0):
    count = count if not interval else 3
    return {"duration": 3.0, "backend": "stub",
            "frames": [{"timestamp": float(i), "data": base64.b64encode(PNG_RED).decode(), "type": "image/jpeg"} for i in range(count)]}


@pytest.mark.asyncio
async def test_export_pdf_writes_file_and_reports(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    monkeypatch.setattr(video_frames, "extract_frames", _fake_frames)
    out = tmp_path / "out.pdf"
    data = json.loads(await server.export_pdf(fake_ctx(StubClient()), album_id="alb", output_path=str(out),
                                           captions={"a1": "A red car"}, frames_per_video=3))
    assert data["path"] == str(out) and out.read_bytes()[:4] == b"%PDF"
    assert data["pages"] == 3 + 3 and data["assets_included"] == 3 and data["assets_skipped"] == []
    from pypdf import PdfReader
    assert "A red car" in PdfReader(str(out)).pages[3].extract_text()


@pytest.mark.asyncio
async def test_export_pdf_never_overwrites(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    monkeypatch.setattr(video_frames, "extract_frames", _fake_frames)
    out = tmp_path / "out.pdf"
    out.write_bytes(b"old")
    data = json.loads(await server.export_pdf(fake_ctx(StubClient()), album_id="alb", output_path=str(out)))
    assert data["path"] == str(tmp_path / "out-2.pdf") and out.read_bytes() == b"old"


@pytest.mark.asyncio
async def test_export_pdf_output_path_directory_gets_slugged_filename(fake_ctx, tmp_path, monkeypatch):
    """Passing a directory as output_path must write <slug(title)>.pdf inside it."""
    from immich_mcp_server import video_frames
    monkeypatch.setattr(video_frames, "extract_frames", _fake_frames)
    data = json.loads(await server.export_pdf(fake_ctx(StubClient()), album_id="alb", output_path=str(tmp_path)))
    assert data["path"] == str(tmp_path / "hypercars.pdf")
    assert os.path.exists(data["path"])


@pytest.mark.asyncio
async def test_export_pdf_output_path_without_extension_gets_pdf_suffix(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    monkeypatch.setattr(video_frames, "extract_frames", _fake_frames)
    data = json.loads(await server.export_pdf(fake_ctx(StubClient()), album_id="alb",
                                           output_path=str(tmp_path / "report")))
    assert data["path"] == str(tmp_path / "report.pdf")
    assert os.path.exists(data["path"])


@pytest.mark.asyncio
async def test_export_pdf_video_without_decoder_uses_poster(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    def boom(*args, **kwargs):
        raise video_frames.NoVideoBackend("no decoder")
    monkeypatch.setattr(video_frames, "extract_frames", boom)
    data = json.loads(await server.export_pdf(fake_ctx(StubClient()), album_id="alb", output_path=str(tmp_path / "p.pdf")))
    assert data["assets_included"] == 3 and any("poster" in warning for warning in data["warnings"])


@pytest.mark.asyncio
async def test_export_pdf_too_many_frames_uses_poster(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    def boom(*args, **kwargs):
        raise video_frames.TooManyFrames("999 frames requested; the cap is 120")
    monkeypatch.setattr(video_frames, "extract_frames", boom)
    data = json.loads(await server.export_pdf(fake_ctx(StubClient()), album_id="alb", output_path=str(tmp_path / "tmf.pdf")))
    assert data["assets_included"] == 3
    assert any("poster used" in warning for warning in data["warnings"])


@pytest.mark.asyncio
async def test_export_pdf_skips_failing_asset(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    monkeypatch.setattr(video_frames, "extract_frames", _fake_frames)
    data = json.loads(await server.export_pdf(fake_ctx(FailingThumbClient()), album_id="alb", output_path=str(tmp_path / "sk.pdf")))
    assert data["assets_included"] == 2
    assert data["assets_skipped"] == [{"id": "a2", "reason": "boom 500"}]


@pytest.mark.asyncio
async def test_export_pdf_base64_and_errors(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    monkeypatch.setattr(video_frames, "extract_frames", _fake_frames)
    data = json.loads(await server.export_pdf(fake_ctx(StubClient()), asset_ids=["a1"], output_path=str(tmp_path / "b.pdf"),
                                           return_base64=True, map=True))
    assert base64.b64decode(data["pdf_base64"])[:4] == b"%PDF"
    assert data["warnings"] == []
    assert "error" in json.loads(await server.export_pdf(fake_ctx(StubClient()), output_path=str(tmp_path / "e.pdf")))


@pytest.mark.asyncio
async def test_export_pdf_no_fpdf(fake_ctx, tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_export, "_fpdf_available", lambda: False)
    data = json.loads(await server.export_pdf(fake_ctx(StubClient()), asset_ids=["a1"], output_path=str(tmp_path / "n.pdf")))
    assert "fpdf2" in data["error"]


# ── v1.8.0: frame size in the PDF and the photobook layout ──


@pytest.mark.asyncio
async def test_export_pdf_single_frame_uses_preview_size(fake_ctx, tmp_path, monkeypatch):
    """With few frames per video the PDF gets preview-sized frames, not 250px thumbnails."""
    from immich_mcp_server import video_frames
    seen_sizes = []

    def fake_frames(data, count=6, size="thumbnail", backend=None, start=0.0, end=0.0, interval=0.0):
        seen_sizes.append(size)
        return _fake_frames(data, count, size, backend, start, end, interval)

    monkeypatch.setattr(video_frames, "extract_frames", fake_frames)
    await server.export_pdf(fake_ctx(StubClient()), album_id="alb", output_path=str(tmp_path / "a.pdf"),
                            frames_per_video=1)
    await server.export_pdf(fake_ctx(StubClient()), album_id="alb", output_path=str(tmp_path / "b.pdf"),
                            frames_per_video=12)
    await server.export_pdf(fake_ctx(StubClient()), album_id="alb", output_path=str(tmp_path / "c.pdf"),
                            frames_per_video=12, frame_size="preview")
    assert seen_sizes == ["preview", "thumbnail", "preview"]


@pytest.mark.asyncio
async def test_export_pdf_accepts_photobook_layout(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    monkeypatch.setattr(video_frames, "extract_frames", _fake_frames)
    data = json.loads(await server.export_pdf(fake_ctx(StubClient()), album_id="alb",
                                              output_path=str(tmp_path / "p.pdf"), layout="photobook"))
    # Front matter (cover, index, places), one page per photo, and the video
    # unfolds into one page per extracted frame (the fake extractor cuts 4).
    assert data["assets_included"] == 3 and data["pages"] == 3 + 2 + 4


# ── v1.9.0: original-quality photos and Live Photo folding ──


@pytest.mark.asyncio
async def test_get_asset_original_returns_bytes(env_credentials, isolated_cache):
    with respx.mock(base_url=BASE) as mock:
        mock.get("/api/assets/a1/original").mock(
            return_value=httpx.Response(200, content=b"JPEGBYTES", headers={"content-type": "image/jpeg"})
        )
        original = await ImmichClient().get_asset_original("a1")
    assert original == {"data": b"JPEGBYTES", "type": "image/jpeg"}


def _big_jpeg(width, height):
    from PIL import Image as PILImage
    buffer = io.BytesIO()
    PILImage.new("RGB", (width, height), "purple").save(buffer, format="JPEG")
    return buffer.getvalue()


class OriginalsClient(StubClient):
    """Serves a 4000px original for a1 and an undecodable one for a2."""

    async def get_asset_original(self, asset_id):
        if asset_id == "a2":
            return {"data": b"HEIC-THAT-PILLOW-CANNOT-OPEN", "type": "image/heic"}
        return {"data": _big_jpeg(4000, 3000), "type": "image/jpeg"}


@pytest.mark.asyncio
async def test_export_pdf_original_size_downscales_and_falls_back(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    monkeypatch.setattr(video_frames, "extract_frames", _fake_frames)
    data = json.loads(await server.export_pdf(fake_ctx(OriginalsClient()), album_id="alb",
                                              output_path=str(tmp_path / "o.pdf"), image_size="original"))
    assert data["assets_included"] == 3
    assert any("a2" in note and "preview" in note for note in data["warnings"])
    from pypdf import PdfReader
    from PIL import Image as PILImage
    reader = PdfReader(str(tmp_path / "o.pdf"))
    sizes = [PILImage.open(io.BytesIO(image.data)).size for page in reader.pages for image in page.images]
    # The 4000px original must come in capped at 3000 on the long side, not at 4000.
    assert (3000, 2250) in sizes and all(size[0] <= 3000 for size in sizes)


class LivePhotoClient(StubClient):
    """A photo whose motion clip is also in the album, plus a plain video."""

    def __init__(self):
        photo = _asset(1)
        photo["livePhotoVideoId"] = "a3"
        super().__init__(assets=[photo, _asset(2), _asset(3, "VIDEO")])


@pytest.mark.asyncio
async def test_live_photo_motion_clip_is_folded_into_its_photo(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    monkeypatch.setattr(video_frames, "extract_frames", _fake_frames)
    preview = json.loads(await server.get_export_preview(fake_ctx(LivePhotoClient()), album_id="alb"))
    assert preview["count"] == 2 and [asset["id"] for asset in preview["assets"]] == ["a1", "a2"]
    assert any("live" in note.lower() for note in preview["warnings"])
    data = json.loads(await server.export_pdf(fake_ctx(LivePhotoClient()), album_id="alb",
                                              output_path=str(tmp_path / "l.pdf")))
    assert data["assets_included"] == 2 and data["assets_skipped"] == []


# ── v1.10.0: frame_times picks the representative frames ────


@pytest.mark.asyncio
async def test_export_pdf_frame_times_win_for_that_video(fake_ctx, tmp_path, monkeypatch):
    """A video listed in frame_times gets exactly those moments; the rest keep frames_per_video."""
    from immich_mcp_server import video_frames
    JPEG_B64 = base64.b64encode(PNG_RED).decode("ascii")
    calls = []

    def fake_at(data, times, size="thumbnail", backend=None):
        calls.append(("at", tuple(times), size))
        return {"duration": 3.0, "backend": "stub",
                "frames": [{"timestamp": float(t), "data": JPEG_B64, "type": "image/jpeg"} for t in times]}

    def fake_extract(data, count=6, size="thumbnail", backend=None, start=0.0, end=0.0, interval=0.0):
        calls.append(("spread", count, size))
        return _fake_frames(data, count, size, backend, start, end, interval)

    monkeypatch.setattr(video_frames, "extract_frames_at", fake_at)
    monkeypatch.setattr(video_frames, "extract_frames", fake_extract)
    client = StubClient(assets=[_asset(1), _asset(3, "VIDEO"), _asset(4, "VIDEO")])
    data = json.loads(await server.export_pdf(
        fake_ctx(client), album_id="alb", output_path=str(tmp_path / "t.pdf"),
        layout="photobook", frames_per_video=1, frame_times={"a3": [73.5]},
    ))
    assert data["assets_included"] == 3 and data["warnings"] == []
    assert ("at", (73.5,), "preview") in calls          # the chosen moment, at preview quality
    assert ("spread", 1, "preview") in calls            # the other video keeps the default


# ── v1.12.0: frame_captions travel with frame_times ─────────


@pytest.mark.asyncio
async def test_export_pdf_passes_frame_captions_to_the_entries(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    JPEG_B64 = base64.b64encode(PNG_RED).decode("ascii")

    def fake_at(data, times, size="thumbnail", backend=None):
        return {"duration": 30.0, "backend": "stub",
                "frames": [{"timestamp": float(t), "data": JPEG_B64, "type": "image/jpeg"} for t in times]}

    monkeypatch.setattr(video_frames, "extract_frames_at", fake_at)
    client = StubClient(assets=[_asset(3, "VIDEO")])
    data = json.loads(await server.export_pdf(
        fake_ctx(client), album_id="alb", output_path=str(tmp_path / "c.pdf"), layout="photobook",
        frame_times={"a3": [5.0, 15.0]}, frame_captions={"a3": ["First moment.", "Second moment."]},
    ))
    assert data["assets_included"] == 1 and data["warnings"] == []
    from pypdf import PdfReader
    reader = PdfReader(str(tmp_path / "c.pdf"))
    assert len(reader.pages) == 3 + 2
    assert "First moment." in reader.pages[3].extract_text()
    assert "Second moment." in reader.pages[4].extract_text()


# ── v1.12.0: optional front matter and the options catalogue ─


@pytest.mark.asyncio
async def test_export_pdf_can_skip_the_front_matter(fake_ctx, tmp_path, monkeypatch):
    from immich_mcp_server import video_frames
    monkeypatch.setattr(video_frames, "extract_frames", _fake_frames)
    data = json.loads(await server.export_pdf(
        fake_ctx(StubClient()), album_id="alb", output_path=str(tmp_path / "n.pdf"),
        layout="photobook", cover=False, index=False, places=False,
    ))
    # 2 photo pages plus 4 frame pages for the video; no cover, index or places.
    assert data["assets_included"] == 3 and data["pages"] == 2 + 4


@pytest.mark.asyncio
async def test_preview_lists_every_export_option(fake_ctx):
    data = json.loads(await server.get_export_preview(fake_ctx(StubClient()), album_id="alb"))
    options = data["options"]
    for name in ("layout", "cover", "index", "places", "frames_per_video", "frame_times",
                 "frame_captions", "image_size", "frame_size", "language", "map", "captions"):
        assert name in options, name
    assert "photobook" in options["layout"]


# ── v1.12.2: footer modes and the title header ──────────────


@pytest.mark.asyncio
async def test_export_pdf_footer_and_header_reach_the_pages(fake_ctx, tmp_path):
    result = json.loads(await server.export_pdf(
        fake_ctx(StubClient(assets=[_asset(1, "IMAGE")])), asset_ids=["a1"],
        output_path=str(tmp_path / "f.pdf"), title="Bare book",
        layout="photobook", cover=False, index=False, places=False,
        footer="none", header=True,
    ))
    assert result["pages"] == 1
    from pypdf import PdfReader
    page_text = PdfReader(str(tmp_path / "f.pdf")).pages[0].extract_text()
    assert "immich-photo-manager" not in page_text and "page" not in page_text
    assert "Bare book" in page_text

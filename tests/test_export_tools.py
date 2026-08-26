"""export_pdf / get_export_preview: client helpers and tools."""
import base64
import io
import json

import httpx
import pytest
import respx

from immich_mcp_server import server
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
        got = await ImmichClient().get_assets_by_ids(["a1", "a2", "zz"])
    body = json.loads(route.calls[0].request.content)
    assert body["ids"] == ["a1", "a2", "zz"] and body["withExif"] is True and body["withPeople"] is True
    assert [a["id"] for a in got] == ["a1", "a2"]


@pytest.mark.asyncio
async def test_fetch_tile_sets_user_agent(env_credentials, isolated_cache):
    with respx.mock() as mock:
        route = mock.get("https://tile.openstreetmap.org/3/4/2.png").mock(return_value=httpx.Response(200, content=b"PNG"))
        assert await ImmichClient().fetch_tile(3, 4, 2) == b"PNG"
    assert route.calls[0].request.headers["user-agent"].startswith("immich-photo-manager/")


class StubClient:
    def __init__(self, assets=None, video_ok=True):
        self.assets = assets or [_asset(1), _asset(2), _asset(3, "VIDEO")]
        self.video_ok = video_ok

    async def get_album(self, album_id):
        return {"id": album_id, "albumName": "Hypercars"}

    async def get_album_assets(self, album_id, limit=None, with_exif=False):
        return self.assets[:limit] if limit else self.assets

    async def get_assets_by_ids(self, ids, with_exif=True):
        return [a for a in self.assets if a["id"] in ids]

    async def get_asset_thumbnail(self, asset_id, size="thumbnail"):
        return {"data": base64.b64encode(PNG_RED).decode(), "type": "image/png"}

    async def get_video_playback(self, asset_id):
        return b"MP4"

    async def fetch_tile(self, z, x, y):
        return PNG_RED

    def _base(self):
        return "https://env.example.com"


@pytest.mark.asyncio
async def test_get_export_preview_album(fake_ctx):
    d = json.loads(await server.get_export_preview(fake_ctx(StubClient()), album_id="alb"))
    assert d["title"] == "Hypercars" and d["count"] == 3
    assert d["assets"][2] == {"id": "a3", "type": "VIDEO", "filename": "3.jpg", "taken_at": "2026-01-03T10:00:00Z",
                              "place": "Barcelona, Spain", "people": ["Curie"], "duration": 3.0}
    assert d["assets"][0]["duration"] is None


@pytest.mark.asyncio
async def test_get_export_preview_requires_exactly_one_source(fake_ctx):
    assert "error" in json.loads(await server.get_export_preview(fake_ctx(StubClient())))
    assert "error" in json.loads(await server.get_export_preview(fake_ctx(StubClient()), album_id="a", asset_ids=["x"]))


@pytest.mark.asyncio
async def test_get_export_preview_limit_warns(fake_ctx):
    d = json.loads(await server.get_export_preview(fake_ctx(StubClient()), asset_ids=["a1", "a2", "a3"], limit=2))
    assert d["count"] == 2 and any("limit" in w for w in d["warnings"])


def test_duration_seconds_numeric_is_milliseconds():
    assert server._duration_seconds({"duration": 900}) == 0.9
    assert server._duration_seconds({"duration": 23567}) == 23.567
    assert server._duration_seconds({"duration": "0:00:03.000"}) == 3.0
    assert server._duration_seconds({"duration": None}) == 0.0

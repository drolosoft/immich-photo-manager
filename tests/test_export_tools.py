"""export_pdf / get_export_preview: client helpers and tools."""
import json

import httpx
import pytest
import respx

from immich_mcp_server.immich_client import ImmichClient

BASE = "https://env.example.com"


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

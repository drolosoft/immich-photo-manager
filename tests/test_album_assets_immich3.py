"""Immich >= 3.0 dropped `assets` from GET /albums/{id}.

Every album-content flow must fall back to POST /search/metadata with
`albumIds`, which exists on 2.x and 3.x. On 2.x the inline `assets` list
is still used (no extra request).
"""

import json

import pytest
import respx
from httpx import Response

from immich_mcp_server import server
from immich_mcp_server.immich_client import ImmichClient

BASE = "https://immich.test"


def _asset(i):
    return {"id": f"a{i}", "type": "IMAGE", "originalFileName": f"{i}.jpg", "fileCreatedAt": "2026-01-01"}


@pytest.fixture
def client():
    return ImmichClient(base_url=BASE, api_key="k")


@pytest.mark.asyncio
@respx.mock
async def test_get_album_assets_paginates_search_metadata(client):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body["albumIds"] == ["alb1"]
        if body["page"] == 1:
            return Response(200, json={"albums": {}, "assets": {"items": [_asset(1), _asset(2)], "nextPage": "2", "total": 3}})
        return Response(200, json={"albums": {}, "assets": {"items": [_asset(3)], "nextPage": None, "total": 3}})

    respx.post(f"{BASE}/api/search/metadata").mock(side_effect=handler)
    assets = await client.get_album_assets("alb1")
    assert [a["id"] for a in assets] == ["a1", "a2", "a3"]
    assert [c["page"] for c in calls] == [1, 2]


@pytest.mark.asyncio
@respx.mock
async def test_get_album_assets_respects_limit(client):
    respx.post(f"{BASE}/api/search/metadata").mock(
        return_value=Response(200, json={"albums": {}, "assets": {"items": [_asset(i) for i in range(5)], "nextPage": "2", "total": 50}})
    )
    assets = await client.get_album_assets("alb1", limit=3)
    assert len(assets) == 3


@pytest.mark.asyncio
@respx.mock
async def test_get_album_thumbnails_on_immich3(client):
    respx.get(f"{BASE}/api/albums/alb1").mock(return_value=Response(200, json={"id": "alb1", "albumName": "Trip", "assetCount": 2}))
    respx.post(f"{BASE}/api/search/metadata").mock(
        return_value=Response(200, json={"albums": {}, "assets": {"items": [_asset(1), _asset(2)], "nextPage": None, "total": 2}})
    )
    respx.get(url__regex=rf"{BASE}/api/assets/a\d/thumbnail.*").mock(return_value=Response(200, content=b"img", headers={"content-type": "image/webp"}))
    result = await client.get_album_thumbnails("alb1")
    assert result["fetchedCount"] == 2
    assert result["thumbnails"][0]["originalFileName"] == "1.jpg"


@pytest.mark.asyncio
@respx.mock
async def test_get_album_thumbnails_on_immich2_uses_inline_assets(client):
    respx.get(f"{BASE}/api/albums/alb1").mock(return_value=Response(200, json={"id": "alb1", "albumName": "Trip", "assetCount": 1, "assets": [_asset(9)]}))
    search = respx.post(f"{BASE}/api/search/metadata")
    respx.get(url__regex=rf"{BASE}/api/assets/a\d/thumbnail.*").mock(return_value=Response(200, content=b"img", headers={"content-type": "image/webp"}))
    result = await client.get_album_thumbnails("alb1")
    assert [t["id"] for t in result["thumbnails"]] == ["a9"]
    assert not search.called


class StubClient3:
    """Immich 3.x shape: album without `assets`."""

    def __init__(self):
        self.searched = []

    async def get_album(self, album_id):
        return {"id": album_id, "albumName": "Trip", "assetCount": 2}

    async def get_album_assets(self, album_id, limit=None):
        self.searched.append(album_id)
        return [_asset(1), _asset(2)]

    async def get_asset_edits(self, asset_id):
        return {"edits": []}

    async def apply_asset_edits(self, asset_id, edits):
        return {}


@pytest.mark.asyncio
async def test_server_get_album_returns_ids_on_immich3(fake_ctx):
    stub = StubClient3()
    out = json.loads(await server.get_album(fake_ctx(stub), album_id="alb1"))
    assert out["asset_ids"] == ["a1", "a2"]
    assert stub.searched == ["alb1"]


@pytest.mark.asyncio
async def test_server_rotate_by_album_on_immich3(fake_ctx):
    stub = StubClient3()
    out = json.loads(await server.rotate_assets(fake_ctx(stub), angle=90, album_id="alb1"))
    assert "error" not in out
    assert out["rotated"] == 2

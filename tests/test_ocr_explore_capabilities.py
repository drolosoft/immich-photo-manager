"""The 2.0.2 API batch: `ocr` filter on both searches, search_explore and
get_capabilities.

All three are dual: the `ocr` string filter lives in MetadataSearchDto and
SmartSearchDto of Immich 2.7.5 AND 3.1.0, and /search/explore plus
/server/features exist unchanged in both OpenAPI specs (verified 2026-09-01).
"""

import json

import pytest
import respx
from httpx import Response

from immich_mcp_server import server
from immich_mcp_server.immich_client import ImmichClient

BASE = "https://immich.test"


@pytest.fixture
def client():
    return ImmichClient(base_url=BASE, api_key="k")


# ── Client: the ocr filter reaches the wire ──────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_search_metadata_sends_ocr_filter_when_given(client):
    route = respx.post(f"{BASE}/api/search/metadata").mock(
        return_value=Response(200, json={"assets": {"items": [], "total": 0}}))
    await client.search_metadata(ocr="boarding pass")
    body = json.loads(route.calls[0].request.content)
    assert body["ocr"] == "boarding pass"


@pytest.mark.asyncio
@respx.mock
async def test_search_metadata_omits_ocr_when_not_given(client):
    route = respx.post(f"{BASE}/api/search/metadata").mock(
        return_value=Response(200, json={"assets": {"items": [], "total": 0}}))
    await client.search_metadata(city="Barcelona")
    body = json.loads(route.calls[0].request.content)
    assert "ocr" not in body


@pytest.mark.asyncio
@respx.mock
async def test_search_smart_sends_ocr_filter_when_given(client):
    route = respx.post(f"{BASE}/api/search/smart").mock(
        return_value=Response(200, json={"assets": {"items": [], "total": 0}}))
    await client.search_smart(query="tickets", ocr="Renfe")
    body = json.loads(route.calls[0].request.content)
    assert body["ocr"] == "Renfe"


# ── Client: search_explore and server features ───────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_search_explore_fetches_the_explore_endpoint(client):
    payload = [{"fieldName": "exifInfo.city",
                "items": [{"value": "Barcelona", "data": {"id": "a1"}}]}]
    respx.get(f"{BASE}/api/search/explore").mock(
        return_value=Response(200, json=payload))
    assert await client.search_explore() == payload


@pytest.mark.asyncio
@respx.mock
async def test_get_server_features_fetches_the_features_endpoint(client):
    respx.get(f"{BASE}/api/server/features").mock(
        return_value=Response(200, json={"ocr": True, "smartSearch": True}))
    assert await client.get_server_features() == {"ocr": True, "smartSearch": True}


# ── Tools ────────────────────────────────────────────────────────────────────

class StubSearchClient:
    """Records the kwargs each search call receives."""

    def __init__(self):
        self.metadata_kwargs = None
        self.smart_kwargs = None

    async def search_metadata(self, **kwargs):
        self.metadata_kwargs = kwargs
        return {"assets": {"items": [], "total": 0}}

    async def search_smart(self, **kwargs):
        self.smart_kwargs = kwargs
        return {"assets": {"items": [], "total": 0}}


@pytest.mark.asyncio
async def test_search_metadata_tool_passes_ocr_through(fake_ctx):
    stub = StubSearchClient()
    await server.search_metadata(fake_ctx(stub), ocr="boarding pass")
    assert stub.metadata_kwargs["ocr"] == "boarding pass"


@pytest.mark.asyncio
async def test_search_metadata_tool_drops_empty_ocr(fake_ctx):
    stub = StubSearchClient()
    await server.search_metadata(fake_ctx(stub), city="Barcelona")
    assert stub.metadata_kwargs["ocr"] is None


@pytest.mark.asyncio
async def test_search_smart_tool_passes_ocr_through(fake_ctx):
    stub = StubSearchClient()
    await server.search_smart(fake_ctx(stub), query="tickets", ocr="Renfe")
    assert stub.smart_kwargs["ocr"] == "Renfe"


class StubExploreClient:
    async def search_explore(self):
        return [
            {"fieldName": "exifInfo.city",
             "items": [{"value": "Barcelona", "data": {"id": "a1"}},
                       {"value": "Paris", "data": {"id": "a2"}}]},
            {"fieldName": "smartInfo.tags",
             "items": [{"value": "beach", "data": {"id": "a3"}}]},
        ]


@pytest.mark.asyncio
async def test_search_explore_tool_trims_assets_to_ids(fake_ctx):
    raw = await server.search_explore(fake_ctx(StubExploreClient()))
    result = json.loads(raw)
    cities = result["fields"][0]
    assert cities["field"] == "exifInfo.city"
    assert cities["items"] == [{"value": "Barcelona", "asset_id": "a1"},
                               {"value": "Paris", "asset_id": "a2"}]
    assert result["fields"][1]["items"] == [{"value": "beach", "asset_id": "a3"}]


class StubCapabilitiesClient:
    def __init__(self, major):
        self.major = major

    async def get_server_version(self):
        return {"major": self.major, "minor": 1, "patch": 0}

    async def get_server_features(self):
        return {"ocr": True, "smartSearch": True, "facialRecognition": False}


@pytest.mark.asyncio
async def test_get_capabilities_reports_version_and_features(fake_ctx):
    raw = await server.get_capabilities(fake_ctx(StubCapabilitiesClient(3)))
    result = json.loads(raw)
    assert result["server_version"] == "3.1.0"
    assert result["immich_major"] == 3
    assert result["features"]["ocr"] is True
    assert result["features"]["facialRecognition"] is False


@pytest.mark.asyncio
async def test_get_capabilities_lists_immich3_album_quirk(fake_ctx):
    raw = await server.get_capabilities(fake_ctx(StubCapabilitiesClient(3)))
    quirks = json.loads(raw)["quirks"]
    assert any("album" in quirk.lower() for quirk in quirks)


@pytest.mark.asyncio
async def test_get_capabilities_lists_immich2_ids_quirk(fake_ctx):
    raw = await server.get_capabilities(fake_ctx(StubCapabilitiesClient(2)))
    quirks = json.loads(raw)["quirks"]
    assert any("ids" in quirk for quirk in quirks)


@pytest.mark.asyncio
async def test_get_capabilities_always_warns_edits_are_image_only(fake_ctx):
    quirks_v2 = json.loads(await server.get_capabilities(fake_ctx(StubCapabilitiesClient(2))))["quirks"]
    quirks_v3 = json.loads(await server.get_capabilities(fake_ctx(StubCapabilitiesClient(3))))["quirks"]
    for quirks in (quirks_v2, quirks_v3):
        assert any("image" in quirk.lower() for quirk in quirks)

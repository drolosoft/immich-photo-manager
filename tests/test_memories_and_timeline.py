"""The 2.0.3 batch, part one: memories CRUD and timeline buckets.

Both areas exist identically in the Immich 2.7.5 and 3.1.0 OpenAPI specs
(verified 2026-09-01). The timeline bucket endpoint answers columnar
(struct-of-arrays); the tool must hand rows to the model.
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


# ── Client: memories ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_list_memories_sends_for_date_and_saved_filter(client):
    route = respx.get(f"{BASE}/api/memories").mock(return_value=Response(200, json=[]))
    await client.list_memories(for_date="2026-09-01T00:00:00Z", is_saved=True)
    params = route.calls[0].request.url.params
    assert params["for"] == "2026-09-01T00:00:00Z"
    assert params["isSaved"] == "true"


@pytest.mark.asyncio
@respx.mock
async def test_create_memory_posts_type_year_and_assets(client):
    route = respx.post(f"{BASE}/api/memories").mock(
        return_value=Response(201, json={"id": "m1"}))
    await client.create_memory(
        memory_at="2026-09-01T00:00:00Z", year=2020, asset_ids=["a1", "a2"])
    body = json.loads(route.calls[0].request.content)
    assert body["type"] == "on_this_day"
    assert body["data"] == {"year": 2020}
    assert body["memoryAt"] == "2026-09-01T00:00:00Z"
    assert body["assetIds"] == ["a1", "a2"]


@pytest.mark.asyncio
@respx.mock
async def test_update_memory_sends_only_the_given_fields(client):
    route = respx.put(f"{BASE}/api/memories/m1").mock(
        return_value=Response(200, json={"id": "m1"}))
    await client.update_memory("m1", is_saved=True)
    body = json.loads(route.calls[0].request.content)
    assert body == {"isSaved": True}


@pytest.mark.asyncio
@respx.mock
async def test_delete_memory_calls_the_delete_endpoint(client):
    route = respx.delete(f"{BASE}/api/memories/m1").mock(return_value=Response(204))
    await client.delete_memory("m1")
    assert route.called


# ── Client: timeline ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_get_timeline_buckets_sends_album_filter(client):
    route = respx.get(f"{BASE}/api/timeline/buckets").mock(
        return_value=Response(200, json=[{"timeBucket": "2026-03-01", "count": 4}]))
    got = await client.get_timeline_buckets(album_id="alb1")
    assert route.calls[0].request.url.params["albumId"] == "alb1"
    assert got == [{"timeBucket": "2026-03-01", "count": 4}]


@pytest.mark.asyncio
@respx.mock
async def test_get_timeline_bucket_sends_the_bucket_key(client):
    route = respx.get(f"{BASE}/api/timeline/bucket").mock(
        return_value=Response(200, json={"id": [], "fileCreatedAt": []}))
    await client.get_timeline_bucket("2026-03-01")
    assert route.calls[0].request.url.params["timeBucket"] == "2026-03-01"


# ── Tools ────────────────────────────────────────────────────────────────────

class StubMemoriesClient:
    """Records kwargs and answers one canned memory."""

    def __init__(self):
        self.kwargs = None

    async def list_memories(self, **kwargs):
        self.kwargs = kwargs
        return [{
            "id": "m1", "type": "on_this_day", "memoryAt": "2026-09-01T00:00:00Z",
            "isSaved": False, "data": {"year": 2020},
            "assets": [{"id": "a1", "originalFileName": "sunset.jpg",
                        "fileCreatedAt": "2020-09-01T18:00:00Z",
                        "exifInfo": {"city": "Barcelona"}}],
        }]

    async def create_memory(self, **kwargs):
        self.kwargs = kwargs
        return {"id": "m9", "type": "on_this_day", "assets": []}

    async def update_memory(self, memory_id, **kwargs):
        self.kwargs = {"memory_id": memory_id, **kwargs}
        return {"id": memory_id, "isSaved": True, "assets": []}

    async def delete_memory(self, memory_id):
        self.kwargs = {"memory_id": memory_id}


@pytest.mark.asyncio
async def test_list_memories_tool_trims_assets_to_essentials(fake_ctx):
    raw = await server.list_memories(fake_ctx(StubMemoriesClient()))
    memory = json.loads(raw)["memories"][0]
    assert memory["year"] == 2020
    assert memory["asset_count"] == 1
    assert memory["assets"][0] == {"asset_id": "a1", "filename": "sunset.jpg",
                                   "date": "2020-09-01T18:00:00Z"}


@pytest.mark.asyncio
async def test_create_memory_tool_passes_year_and_asset_ids(fake_ctx):
    stub = StubMemoriesClient()
    raw = await server.create_memory(
        fake_ctx(stub), memory_at="2026-09-01T00:00:00Z", year=2020,
        asset_ids=["a1", "a2"])
    assert stub.kwargs["year"] == 2020
    assert stub.kwargs["asset_ids"] == ["a1", "a2"]
    assert json.loads(raw)["id"] == "m9"


@pytest.mark.asyncio
async def test_update_memory_tool_drops_unset_fields(fake_ctx):
    stub = StubMemoriesClient()
    await server.update_memory(fake_ctx(stub), memory_id="m1", is_saved=True)
    assert stub.kwargs == {"memory_id": "m1", "is_saved": True,
                           "memory_at": None, "seen_at": None}


@pytest.mark.asyncio
async def test_delete_memory_tool_reports_success(fake_ctx):
    stub = StubMemoriesClient()
    raw = await server.delete_memory(fake_ctx(stub), memory_id="m1")
    assert stub.kwargs == {"memory_id": "m1"}
    assert json.loads(raw)["success"] is True


class StubTimelineClient:
    async def get_timeline_buckets(self, **kwargs):
        return [{"timeBucket": "2026-03-01", "count": 4},
                {"timeBucket": "2026-02-01", "count": 2}]

    async def get_timeline_bucket(self, time_bucket, **kwargs):
        return {
            "id": ["a1", "a2"],
            "fileCreatedAt": ["2026-03-06T10:00:00Z", "2026-03-02T09:00:00Z"],
            "isImage": [True, False],
            "isFavorite": [False, True],
            "duration": [None, "0:00:03.000"],
            "city": ["Lisbon", None],
            "country": ["Portugal", None],
            "thumbhash": ["xx", "yy"],
        }


@pytest.mark.asyncio
async def test_get_timeline_buckets_tool_returns_month_counts(fake_ctx):
    raw = await server.get_timeline_buckets(fake_ctx(StubTimelineClient()))
    result = json.loads(raw)
    assert result["buckets"][0] == {"timeBucket": "2026-03-01", "count": 4}
    assert result["total_buckets"] == 2


@pytest.mark.asyncio
async def test_get_timeline_bucket_tool_zips_columns_into_rows(fake_ctx):
    raw = await server.get_timeline_bucket(
        fake_ctx(StubTimelineClient()), time_bucket="2026-03-01")
    rows = json.loads(raw)["assets"]
    assert rows[0] == {"asset_id": "a1", "date": "2026-03-06T10:00:00Z",
                       "is_image": True, "is_favorite": False, "duration": None,
                       "city": "Lisbon", "country": "Portugal"}
    assert rows[1]["asset_id"] == "a2"
    assert rows[1]["duration"] == "0:00:03.000"

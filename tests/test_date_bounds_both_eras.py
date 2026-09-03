"""One date format that works on both Immich majors.

Immich 2.7.5 accepts a bare `2019-07-14` on every search and map filter, which
is what the tool docstrings tell a model to send. Immich 3.1.0 validates the
same fields as full ISO 8601 and answers 400 for the bare date, so the identical
call succeeded on one major and failed on the other — verified live against both
labs on 2026-09-03:

    POST /api/search/statistics {"takenAfter": "2000-01-01"}
        2.7.5 -> 200 {"total": 11}
        3.1.0 -> 400 Validation failed, expected ISO 8601 date

The client widens a bare date to midnight UTC, exactly how 2.7.5 read it, so
2.x behaviour is unchanged and 3.x stops refusing the documented value.
"""

import json

import pytest
import respx
from httpx import Response

from immich_mcp_server.client.base import to_immich_datetime
from immich_mcp_server.immich_client import ImmichClient

BASE = "https://immich.test"


@pytest.fixture
def client():
    return ImmichClient(base_url=BASE, api_key="k")


@pytest.mark.parametrize("value, expected", [
    ("2019-07-14", "2019-07-14T00:00:00.000Z"),
    ("2019-07-14T15:23:41.000Z", "2019-07-14T15:23:41.000Z"),
    ("2019-07-14T15:23:41+02:00", "2019-07-14T15:23:41+02:00"),
    ("", ""),
    (None, None),
])
def test_only_a_bare_date_is_widened(value, expected):
    assert to_immich_datetime(value) == expected


@pytest.mark.asyncio
@respx.mock
async def test_search_metadata_widens_a_bare_taken_date(client):
    route = respx.post(f"{BASE}/api/search/metadata").mock(
        return_value=Response(200, json={"assets": {"items": [], "total": 0}}))
    await client.search_metadata(taken_after="2019-01-01", taken_before="2019-12-31")
    body = json.loads(route.calls[0].request.content)
    assert body["takenAfter"] == "2019-01-01T00:00:00.000Z"
    assert body["takenBefore"] == "2019-12-31T00:00:00.000Z"


@pytest.mark.asyncio
@respx.mock
async def test_search_smart_widens_a_bare_taken_date(client):
    route = respx.post(f"{BASE}/api/search/smart").mock(
        return_value=Response(200, json={"assets": {"items": [], "total": 0}}))
    await client.search_smart("beach", taken_after="2019-01-01")
    assert json.loads(route.calls[0].request.content)["takenAfter"] == "2019-01-01T00:00:00.000Z"


@pytest.mark.asyncio
@respx.mock
async def test_map_markers_widen_a_bare_created_date(client):
    route = respx.get(f"{BASE}/api/map/markers").mock(return_value=Response(200, json=[]))
    await client.get_map_markers(file_created_after="2019-01-01",
                                 file_created_before="2019-12-31")
    params = route.calls[0].request.url.params
    assert params["fileCreatedAfter"] == "2019-01-01T00:00:00.000Z"
    assert params["fileCreatedBefore"] == "2019-12-31T00:00:00.000Z"


@pytest.mark.asyncio
@respx.mock
async def test_a_timestamp_the_caller_supplied_is_sent_untouched(client):
    """A caller that already knows the exact moment must not have it rewritten."""
    route = respx.post(f"{BASE}/api/search/metadata").mock(
        return_value=Response(200, json={"assets": {"items": [], "total": 0}}))
    await client.search_metadata(taken_after="2019-07-14T15:23:41.000Z")
    assert json.loads(route.calls[0].request.content)["takenAfter"] == "2019-07-14T15:23:41.000Z"


@pytest.mark.asyncio
@respx.mock
async def test_memory_dates_are_widened_for_immich3(client):
    """A real Claude Code session on 3.1.0 hit it: create_memory with a bare
    memory_at date was refused, the retry with a full timestamp went through.
    memoryAt, seenAt and the `for` filter follow the same rule as the searches."""
    create = respx.post(f"{BASE}/api/memories").mock(return_value=Response(201, json={"id": "m1"}))
    update = respx.put(f"{BASE}/api/memories/m1").mock(return_value=Response(200, json={"id": "m1"}))
    listing = respx.get(f"{BASE}/api/memories").mock(return_value=Response(200, json=[]))
    await client.create_memory(memory_at="2026-09-03", year=2020, asset_ids=["a1"])
    await client.update_memory("m1", memory_at="2026-09-04", seen_at="2026-09-05")
    await client.list_memories(for_date="2026-09-03")
    assert json.loads(create.calls[0].request.content)["memoryAt"] == "2026-09-03T00:00:00.000Z"
    body = json.loads(update.calls[0].request.content)
    assert body["memoryAt"] == "2026-09-04T00:00:00.000Z"
    assert body["seenAt"] == "2026-09-05T00:00:00.000Z"
    assert listing.calls[0].request.url.params["for"] == "2026-09-03T00:00:00.000Z"

"""The 2.0.7 batch, part one: person/tag/album search filters, bulk metadata
update, and the confirmation gate on merge_people.

personIds, tagIds and albumIds live in MetadataSearchDto AND SmartSearchDto of
Immich 2.7.5 and 3.1.0; PUT /assets (AssetBulkUpdateDto) is identical in both
(verified 2026-09-03).

It also pins the one rating rule the two majors disagree on: 3.1.0 refuses a
rating of 0 ("no longer valid") while 2.7.5 accepts it, so both metadata tools
refuse it themselves and neither lets an Immich rejection escape as a crash.
"""

import json

import httpx
import pytest
import respx
from httpx import Response

from immich_mcp_server import server
from immich_mcp_server.immich_client import ImmichClient

BASE = "https://immich.test"


@pytest.fixture
def client():
    return ImmichClient(base_url=BASE, api_key="k")


# ── Client: search filters ───────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_search_metadata_sends_person_tag_and_album_ids(client):
    route = respx.post(f"{BASE}/api/search/metadata").mock(
        return_value=Response(200, json={"assets": {"items": [], "total": 0}}))
    await client.search_metadata(person_ids=["p1"], tag_ids=["t1"], album_ids=["alb1"])
    body = json.loads(route.calls[0].request.content)
    assert body["personIds"] == ["p1"]
    assert body["tagIds"] == ["t1"]
    assert body["albumIds"] == ["alb1"]


@pytest.mark.asyncio
@respx.mock
async def test_search_smart_sends_person_ids(client):
    route = respx.post(f"{BASE}/api/search/smart").mock(
        return_value=Response(200, json={"assets": {"items": [], "total": 0}}))
    await client.search_smart(query="beach", person_ids=["p1"], album_ids=["alb1"])
    body = json.loads(route.calls[0].request.content)
    assert body["personIds"] == ["p1"]
    assert body["albumIds"] == ["alb1"]


# ── Client: bulk update ──────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_update_assets_metadata_puts_ids_and_given_fields_only(client):
    route = respx.put(f"{BASE}/api/assets").mock(return_value=Response(204))
    await client.update_assets_metadata(
        ["a1", "a2"], date_time_original="2020-05-01T10:00:00Z", rating=4)
    body = json.loads(route.calls[0].request.content)
    assert body == {"ids": ["a1", "a2"], "dateTimeOriginal": "2020-05-01T10:00:00Z", "rating": 4}


# ── Tools ────────────────────────────────────────────────────────────────────

class StubSearchClient:
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
async def test_search_metadata_tool_passes_the_id_filters(fake_ctx):
    stub = StubSearchClient()
    await server.search_metadata(
        fake_ctx(stub), person_ids=["p1"], tag_ids=["t1"], album_ids=["alb1"])
    assert stub.metadata_kwargs["person_ids"] == ["p1"]
    assert stub.metadata_kwargs["tag_ids"] == ["t1"]
    assert stub.metadata_kwargs["album_ids"] == ["alb1"]


@pytest.mark.asyncio
async def test_search_smart_tool_passes_the_id_filters(fake_ctx):
    stub = StubSearchClient()
    await server.search_smart(fake_ctx(stub), query="beach", person_ids=["p1"])
    assert stub.smart_kwargs["person_ids"] == ["p1"]


class StubBulkClient:
    def __init__(self):
        self.kwargs = None

    async def update_assets_metadata(self, asset_ids, **kwargs):
        self.kwargs = {"asset_ids": asset_ids, **kwargs}


@pytest.mark.asyncio
async def test_update_assets_metadata_tool_reports_how_many_it_touched(fake_ctx):
    stub = StubBulkClient()
    raw = await server.update_assets_metadata(
        fake_ctx(stub), asset_ids=["a1", "a2"], latitude=41.4, longitude=2.2)
    result = json.loads(raw)
    assert stub.kwargs["asset_ids"] == ["a1", "a2"]
    assert stub.kwargs["latitude"] == 41.4
    assert stub.kwargs["date_time_original"] is None
    assert result == {"success": True, "updated": 2}


@pytest.mark.asyncio
async def test_update_assets_metadata_tool_refuses_an_empty_change(fake_ctx):
    raw = await server.update_assets_metadata(fake_ctx(StubBulkClient()), asset_ids=["a1"])
    assert "error" in json.loads(raw)


@pytest.mark.asyncio
async def test_update_assets_metadata_tool_refuses_an_empty_asset_list(fake_ctx):
    stub = StubBulkClient()
    raw = await server.update_assets_metadata(fake_ctx(stub), asset_ids=[], rating=3)
    assert json.loads(raw) == {"error": "asset_ids cannot be empty."}
    assert stub.kwargs is None


def _http_error(status, detail):
    """An httpx.HTTPStatusError carrying `status` and Immich's own message."""
    request = httpx.Request("PUT", "https://immich.test/api/assets")
    response = httpx.Response(status, request=request, text=detail)
    return httpx.HTTPStatusError(str(status), request=request, response=response)


class StubRatingClient:
    """Records the single-asset update, or refuses it the way Immich 3.x does."""

    def __init__(self, status=None):
        self.status = status
        self.fields = None

    async def update_asset(self, asset_id, **fields):
        self.fields = {"asset_id": asset_id, **fields}
        if self.status:
            raise _http_error(self.status, "Rating must be -1 (rejected), 1-5 (starred), "
                                           "or null (unrated); 0 is not valid")
        return {"id": asset_id, **fields}

    async def update_assets_metadata(self, asset_ids, **kwargs):
        self.fields = {"asset_ids": asset_ids, **kwargs}
        if self.status:
            raise _http_error(self.status, "Rating must be -1 (rejected), 1-5 (starred), "
                                           "or null (unrated); 0 is not valid")


@pytest.mark.asyncio
async def test_update_asset_metadata_refuses_rating_zero_without_asking_immich(fake_ctx):
    """Immich 3.x rejects a 0 rating and 2.7.5 quietly accepts it, so the plugin
    refuses it on both rather than letting the majors disagree."""
    stub = StubRatingClient()
    raw = await server.update_asset_metadata(fake_ctx(stub), asset_id="a1", rating=0)
    assert "-1" in json.loads(raw)["error"]
    assert stub.fields is None


@pytest.mark.asyncio
async def test_update_assets_metadata_refuses_rating_zero_without_asking_immich(fake_ctx):
    stub = StubRatingClient()
    raw = await server.update_assets_metadata(fake_ctx(stub), asset_ids=["a1"], rating=0)
    assert "-1" in json.loads(raw)["error"]
    assert stub.fields is None


@pytest.mark.asyncio
async def test_update_asset_metadata_sends_a_rejected_rating_of_minus_one(fake_ctx):
    stub = StubRatingClient()
    await server.update_asset_metadata(fake_ctx(stub), asset_id="a1", rating=-1)
    assert stub.fields["rating"] == -1


@pytest.mark.asyncio
async def test_update_assets_metadata_sends_a_rejected_rating_of_minus_one(fake_ctx):
    stub = StubRatingClient()
    await server.update_assets_metadata(fake_ctx(stub), asset_ids=["a1"], rating=-1)
    assert stub.fields["rating"] == -1


@pytest.mark.asyncio
async def test_update_asset_metadata_reports_an_immich_rejection_as_an_error(fake_ctx):
    stub = StubRatingClient(status=400)
    raw = await server.update_asset_metadata(
        fake_ctx(stub), asset_id="a1", date_time_original="not-a-date")
    result = json.loads(raw)
    assert result["error"] == "Immich API error: 400"
    assert "Rating must be" in result["detail"]


@pytest.mark.asyncio
async def test_update_assets_metadata_reports_an_immich_rejection_as_an_error(fake_ctx):
    stub = StubRatingClient(status=400)
    raw = await server.update_assets_metadata(
        fake_ctx(stub), asset_ids=["a1"], date_time_original="not-a-date")
    assert json.loads(raw)["error"] == "Immich API error: 400"


class StubPeopleClient:
    def __init__(self):
        self.merged = None

    async def get_person(self, person_id):
        return {"id": person_id, "name": {"p1": "Marie", "p2": "Marie Curie"}[person_id]}

    async def merge_people(self, person_id, merge_ids):
        self.merged = (person_id, merge_ids)
        return {"id": person_id}


@pytest.mark.asyncio
async def test_merge_people_without_confirm_previews_and_does_nothing(fake_ctx):
    stub = StubPeopleClient()
    raw = await server.merge_people(fake_ctx(stub), person_id="p1", merge_ids=["p2"])
    result = json.loads(raw)
    assert result["confirm_required"] is True
    assert result["keep"] == {"id": "p1", "name": "Marie"}
    assert result["merge"] == [{"id": "p2", "name": "Marie Curie"}]
    assert stub.merged is None


@pytest.mark.asyncio
async def test_merge_people_with_confirm_merges(fake_ctx):
    stub = StubPeopleClient()
    await server.merge_people(fake_ctx(stub), person_id="p1", merge_ids=["p2"], confirm=True)
    assert stub.merged == ("p1", ["p2"])

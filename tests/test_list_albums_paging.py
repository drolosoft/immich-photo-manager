"""
list_albums on a library with thousands of albums (issue #31).

GET /albums on Immich returns every album and has no filter or paging of its
own, so the tool filters by name, pages and trims the fields itself. Without
arguments the answer must be exactly what it was before, so existing clients
do not notice the change.
"""

import json

import pytest
import respx
from httpx import Response

from immich_mcp_server.immich_client import ImmichClient
from immich_mcp_server.tools.albums import list_albums

BASE = "https://immich.test"


def _album(index: int, name: str) -> dict:
    return {
        "id": f"album-{index:04d}",
        "albumName": name,
        "description": f"about {name}",
        "assetCount": index,
        "shared": index % 2 == 0,
        "hasSharedLink": False,
        "createdAt": f"2026-01-{(index % 28) + 1:02d}T00:00:00Z",
    }


# Nine albums, three of them about Paris in different cases, in Immich's order.
ALBUMS = [
    _album(1, "Paris 2024"),
    _album(2, "Lisbon"),
    _album(3, "paris in spring"),
    _album(4, "Berlin"),
    _album(5, "Rome"),
    _album(6, "Trip to PARIS"),
    _album(7, "Madrid"),
    _album(8, "Oslo"),
    _album(9, "Vienna"),
]


@pytest.fixture
def ctx(fake_ctx):
    return fake_ctx(ImmichClient(base_url=BASE, api_key="key"))


def _mock_albums():
    return respx.get(f"{BASE}/api/albums").mock(return_value=Response(200, json=ALBUMS))


@pytest.mark.asyncio
@respx.mock
async def test_without_arguments_the_answer_is_what_it_always_was(ctx):
    _mock_albums()

    data = json.loads(await list_albums(ctx))

    assert set(data) == {"total", "albums"}
    assert data["total"] == 9
    assert [album["id"] for album in data["albums"]] == [album["id"] for album in ALBUMS]
    assert set(data["albums"][0]) == {
        "id", "albumName", "description", "assetCount", "shared", "hasSharedLink", "createdAt",
    }


@pytest.mark.asyncio
@respx.mock
async def test_name_contains_is_case_insensitive_and_sets_total(ctx):
    _mock_albums()

    data = json.loads(await list_albums(ctx, name_contains="paris"))

    assert data["total"] == 3
    assert [album["albumName"] for album in data["albums"]] == ["Paris 2024", "paris in spring", "Trip to PARIS"]


@pytest.mark.asyncio
@respx.mock
async def test_paging_slices_the_list_and_reports_pages(ctx):
    _mock_albums()

    first = json.loads(await list_albums(ctx, page=1, size=4))
    last = json.loads(await list_albums(ctx, page=3, size=4))
    beyond = json.loads(await list_albums(ctx, page=4, size=4))

    assert (first["total"], first["page"], first["size"], first["pages"]) == (9, 1, 4, 3)
    assert [album["id"] for album in first["albums"]] == ["album-0001", "album-0002", "album-0003", "album-0004"]
    assert [album["id"] for album in last["albums"]] == ["album-0009"]
    assert beyond["albums"] == [] and beyond["total"] == 9


@pytest.mark.asyncio
@respx.mock
async def test_filter_and_paging_combine(ctx):
    _mock_albums()

    data = json.loads(await list_albums(ctx, name_contains="PARIS", page=2, size=2))

    assert data["total"] == 3 and data["pages"] == 2
    assert [album["albumName"] for album in data["albums"]] == ["Trip to PARIS"]


@pytest.mark.asyncio
@respx.mock
async def test_compact_keeps_only_id_name_and_count(ctx):
    _mock_albums()

    data = json.loads(await list_albums(ctx, compact=True, size=1))

    assert data["albums"] == [{"id": "album-0001", "albumName": "Paris 2024", "assetCount": 1}]


@pytest.mark.asyncio
@respx.mock
async def test_size_is_capped_and_page_floored(ctx):
    _mock_albums()

    data = json.loads(await list_albums(ctx, page=0, size=5000))

    assert (data["page"], data["size"], data["pages"]) == (1, 500, 1)
    assert len(data["albums"]) == 9


@pytest.mark.asyncio
@respx.mock
async def test_shared_still_reaches_immich(ctx):
    route = _mock_albums()

    await list_albums(ctx, shared=True, name_contains="x")

    assert route.calls.last.request.url.params["shared"] == "true"

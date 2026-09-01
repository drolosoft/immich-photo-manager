"""The 2.0.3 batch, part two: search extras and reverse geocoding.

cities, places, suggestions, random, statistics and large-assets under
/search, plus /map/reverse-geocode — all identical in the Immich 2.7.5 and
3.1.0 OpenAPI specs (verified 2026-09-01). Oddity to protect: large-assets
is a POST that takes QUERY parameters, not a body.
"""

import json

import pytest
import respx
from httpx import Response

from immich_mcp_server import server
from immich_mcp_server.immich_client import ImmichClient

BASE = "https://immich.test"


def _asset(i, city="Lisbon"):
    return {"id": f"a{i}", "type": "IMAGE", "originalFileName": f"{i}.jpg",
            "fileCreatedAt": "2026-03-0%dT10:00:00Z" % i,
            "exifInfo": {"city": city, "country": "Portugal",
                         "fileSizeInByte": 1000000 * i}}


@pytest.fixture
def client():
    return ImmichClient(base_url=BASE, api_key="k")


# ── Client ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_search_cities_fetches_the_cities_endpoint(client):
    respx.get(f"{BASE}/api/search/cities").mock(
        return_value=Response(200, json=[_asset(1)]))
    got = await client.search_cities()
    assert got[0]["id"] == "a1"


@pytest.mark.asyncio
@respx.mock
async def test_search_places_sends_the_name_param(client):
    route = respx.get(f"{BASE}/api/search/places").mock(
        return_value=Response(200, json=[{"name": "Lisbon"}]))
    await client.search_places("Lisbon")
    assert route.calls[0].request.url.params["name"] == "Lisbon"


@pytest.mark.asyncio
@respx.mock
async def test_search_suggestions_sends_type_and_filters(client):
    route = respx.get(f"{BASE}/api/search/suggestions").mock(
        return_value=Response(200, json=["Lisbon"]))
    await client.search_suggestions("city", country="Portugal")
    params = route.calls[0].request.url.params
    assert params["type"] == "city"
    assert params["country"] == "Portugal"


@pytest.mark.asyncio
@respx.mock
async def test_search_random_posts_size_and_filters(client):
    route = respx.post(f"{BASE}/api/search/random").mock(
        return_value=Response(200, json=[_asset(1)]))
    await client.search_random(size=3, city="Lisbon", ocr="ticket")
    body = json.loads(route.calls[0].request.content)
    assert body["size"] == 3
    assert body["city"] == "Lisbon"
    assert body["ocr"] == "ticket"


@pytest.mark.asyncio
@respx.mock
async def test_search_statistics_posts_filters_and_returns_total(client):
    route = respx.post(f"{BASE}/api/search/statistics").mock(
        return_value=Response(200, json={"total": 42}))
    got = await client.search_statistics(make="Apple", is_favorite=True)
    body = json.loads(route.calls[0].request.content)
    assert body["make"] == "Apple"
    assert body["isFavorite"] is True
    assert got == {"total": 42}


@pytest.mark.asyncio
@respx.mock
async def test_search_large_assets_sends_query_params_not_a_body(client):
    route = respx.post(f"{BASE}/api/search/large-assets").mock(
        return_value=Response(200, json=[_asset(2)]))
    await client.search_large_assets(min_file_size=5000000, size=10)
    request = route.calls[0].request
    assert request.url.params["minFileSize"] == "5000000"
    assert request.url.params["size"] == "10"
    assert request.content == b""


@pytest.mark.asyncio
@respx.mock
async def test_reverse_geocode_sends_lat_and_lon(client):
    route = respx.get(f"{BASE}/api/map/reverse-geocode").mock(
        return_value=Response(200, json=[{"city": "Barcelona", "state": "Catalonia",
                                          "country": "Spain"}]))
    got = await client.reverse_geocode(41.4, 2.2)
    params = route.calls[0].request.url.params
    assert params["lat"] == "41.4"
    assert params["lon"] == "2.2"
    assert got[0]["city"] == "Barcelona"


# ── Tools ────────────────────────────────────────────────────────────────────

class StubExtrasClient:
    def __init__(self):
        self.kwargs = None

    async def search_cities(self):
        return [_asset(1, "Lisbon"), _asset(2, "Porto")]

    async def search_places(self, name):
        self.kwargs = {"name": name}
        return [{"name": "Lisbon", "admin1name": "Lisboa", "admin2name": "Lisboa",
                 "latitude": 38.7, "longitude": -9.1}]

    async def search_suggestions(self, suggestion_type, **kwargs):
        self.kwargs = {"suggestion_type": suggestion_type, **kwargs}
        return ["Lisbon", "Porto"]

    async def search_random(self, **kwargs):
        self.kwargs = kwargs
        return [_asset(1)]

    async def search_statistics(self, **kwargs):
        self.kwargs = kwargs
        return {"total": 42}

    async def search_large_assets(self, **kwargs):
        self.kwargs = kwargs
        return [_asset(3), _asset(2)]

    async def reverse_geocode(self, lat, lon):
        self.kwargs = {"lat": lat, "lon": lon}
        return [{"city": "Barcelona", "state": "Catalonia", "country": "Spain"}]


@pytest.mark.asyncio
async def test_search_cities_tool_trims_to_one_row_per_city(fake_ctx):
    raw = await server.search_cities(fake_ctx(StubExtrasClient()))
    cities = json.loads(raw)["cities"]
    assert cities[0] == {"city": "Lisbon", "country": "Portugal", "asset_id": "a1",
                        "date": "2026-03-01T10:00:00Z"}
    assert cities[1]["city"] == "Porto"


@pytest.mark.asyncio
async def test_search_places_tool_passes_the_name_through(fake_ctx):
    stub = StubExtrasClient()
    raw = await server.search_places(fake_ctx(stub), name="Lisbon")
    assert stub.kwargs == {"name": "Lisbon"}
    assert json.loads(raw)["places"][0]["name"] == "Lisbon"


@pytest.mark.asyncio
async def test_search_suggestions_tool_returns_the_value_list(fake_ctx):
    stub = StubExtrasClient()
    raw = await server.search_suggestions(fake_ctx(stub), type="city")
    assert stub.kwargs["suggestion_type"] == "city"
    assert json.loads(raw)["suggestions"] == ["Lisbon", "Porto"]


@pytest.mark.asyncio
async def test_search_random_tool_caps_size_at_100(fake_ctx):
    stub = StubExtrasClient()
    await server.search_random(fake_ctx(stub), size=500)
    assert stub.kwargs["size"] == 100


@pytest.mark.asyncio
async def test_search_statistics_tool_returns_the_bare_total(fake_ctx):
    stub = StubExtrasClient()
    raw = await server.search_statistics(fake_ctx(stub), make="Apple")
    assert stub.kwargs["make"] == "Apple"
    assert json.loads(raw) == {"total": 42}


@pytest.mark.asyncio
async def test_search_large_assets_tool_converts_mb_and_reports_sizes(fake_ctx):
    stub = StubExtrasClient()
    raw = await server.search_large_assets(fake_ctx(stub), min_size_mb=5)
    assert stub.kwargs["min_file_size"] == 5 * 1024 * 1024
    biggest = json.loads(raw)["assets"][0]
    assert biggest == {"asset_id": "a3", "filename": "3.jpg",
                       "size_mb": round(3000000 / 1024 / 1024, 1),
                       "date": "2026-03-03T10:00:00Z"}


@pytest.mark.asyncio
async def test_reverse_geocode_tool_returns_city_state_country(fake_ctx):
    stub = StubExtrasClient()
    raw = await server.reverse_geocode(fake_ctx(stub), lat=41.4, lon=2.2)
    assert stub.kwargs == {"lat": 41.4, "lon": 2.2}
    assert json.loads(raw)["places"][0]["city"] == "Barcelona"

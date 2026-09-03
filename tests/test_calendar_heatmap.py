"""The 2.0.7 batch, part two: get_calendar_heatmap, the first tool with an
Immich 3.x-only endpoint behind a 2.x fallback.

Immich 3.1.0 serves GET /users/me/calendar-heatmap (per-day counts, type
Upload or Taken). Immich 2.7.5 has no such route (404), so the tool derives
the same shape from the timeline buckets, which exist in both. Verified in
the OpenAPI specs 2026-09-03.
"""

import json
from datetime import datetime, timedelta, timezone

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


@pytest.mark.asyncio
@respx.mock
async def test_get_calendar_heatmap_sends_range_and_type(client):
    route = respx.get(f"{BASE}/api/users/me/calendar-heatmap").mock(
        return_value=Response(200, json={"from": "2026-01-01", "to": "2026-12-31",
                                         "series": [], "totalCount": 0}))
    await client.get_calendar_heatmap(from_date="2026-01-01", to_date="2026-12-31",
                                      heatmap_type="Taken")
    params = route.calls[0].request.url.params
    assert params["from"] == "2026-01-01"
    assert params["to"] == "2026-12-31"
    assert params["type"] == "Taken"


class StubNativeClient:
    async def get_calendar_heatmap(self, **kwargs):
        return {"from": "2026-03-01", "to": "2026-03-31", "totalCount": 3,
                "series": [{"date": "2026-03-02", "count": 1},
                           {"date": "2026-03-06", "count": 2}]}


@pytest.mark.asyncio
async def test_heatmap_tool_uses_the_native_endpoint_when_it_exists(fake_ctx):
    raw = await server.get_calendar_heatmap(
        fake_ctx(StubNativeClient()), from_date="2026-03-01", to_date="2026-03-31")
    result = json.loads(raw)
    assert result["source"] == "immich"
    assert result["total"] == 3
    assert result["series"] == [{"date": "2026-03-02", "count": 1},
                                {"date": "2026-03-06", "count": 2}]


class StubFallbackClient:
    """Immich 2.x: the heatmap route answers 404; the timeline still exists."""

    def __init__(self):
        self.fetched_buckets = []

    async def get_calendar_heatmap(self, **kwargs):
        request = httpx.Request("GET", f"{BASE}/api/users/me/calendar-heatmap")
        raise httpx.HTTPStatusError("404", request=request,
                                    response=httpx.Response(404, request=request))

    async def get_timeline_buckets(self, **kwargs):
        return [{"timeBucket": "2026-04-01", "count": 1},
                {"timeBucket": "2026-03-01", "count": 3},
                {"timeBucket": "2025-12-01", "count": 5}]

    async def get_timeline_bucket(self, time_bucket, **kwargs):
        self.fetched_buckets.append(time_bucket)
        rows = {
            "2026-04-01": ["2026-04-10T09:00:00Z"],
            "2026-03-01": ["2026-03-06T10:00:00Z", "2026-03-06T18:00:00Z", "2026-03-02T09:00:00Z"],
        }[time_bucket]
        return {"id": [f"a{index}" for index in range(len(rows))], "fileCreatedAt": rows}


@pytest.mark.asyncio
async def test_heatmap_tool_falls_back_to_the_timeline_on_immich2(fake_ctx):
    stub = StubFallbackClient()
    raw = await server.get_calendar_heatmap(
        fake_ctx(stub), from_date="2026-03-01", to_date="2026-04-30")
    result = json.loads(raw)
    assert result["source"] == "timeline"
    assert result["total"] == 4
    assert result["series"] == [{"date": "2026-03-02", "count": 1},
                                {"date": "2026-03-06", "count": 2},
                                {"date": "2026-04-10", "count": 1}]
    # The December bucket is outside the range and must not be fetched.
    assert sorted(stub.fetched_buckets) == ["2026-03-01", "2026-04-01"]


class StubOpenEndedFallbackClient:
    """Immich 2.x with buckets on both sides of the one-year mark."""

    def __init__(self, recent_month, old_month):
        self.recent_month = recent_month
        self.old_month = old_month
        self.fetched_buckets = []

    async def get_calendar_heatmap(self, **kwargs):
        request = httpx.Request("GET", f"{BASE}/api/users/me/calendar-heatmap")
        raise httpx.HTTPStatusError("404", request=request,
                                    response=httpx.Response(404, request=request))

    async def get_timeline_buckets(self, **kwargs):
        return [{"timeBucket": f"{self.recent_month}-01", "count": 1},
                {"timeBucket": f"{self.old_month}-01", "count": 1}]

    async def get_timeline_bucket(self, time_bucket, **kwargs):
        self.fetched_buckets.append(time_bucket)
        return {"id": ["a1"], "fileCreatedAt": [f"{time_bucket[:7]}-15T09:00:00Z"]}


@pytest.mark.asyncio
async def test_heatmap_fallback_defaults_to_the_last_year(fake_ctx):
    """Without a lower bound the fallback used to issue one request per month
    the library has ever held — 120 sequential calls for a ten-year library,
    inside a single tool call. An open-ended range now means the last 365 days."""
    today = datetime.now(timezone.utc).date()
    recent_month = (today - timedelta(days=30)).strftime("%Y-%m")
    old_month = (today - timedelta(days=800)).strftime("%Y-%m")
    stub = StubOpenEndedFallbackClient(recent_month, old_month)

    raw = await server.get_calendar_heatmap(fake_ctx(stub))

    result = json.loads(raw)
    assert result["source"] == "timeline"
    assert stub.fetched_buckets == [f"{recent_month}-01"]
    assert [entry["date"][:7] for entry in result["series"]] == [recent_month]


@pytest.mark.asyncio
async def test_heatmap_fallback_cannot_do_upload_dates(fake_ctx):
    raw = await server.get_calendar_heatmap(
        fake_ctx(StubFallbackClient()), from_date="2026-03-01", to_date="2026-04-30",
        heatmap_type="Upload")
    result = json.loads(raw)
    assert "error" in result
    assert "Taken" in result["error"]


class StubNativeWithZerosClient:
    async def get_calendar_heatmap(self, **kwargs):
        return {"totalCount": 2, "series": [{"date": "2026-03-01", "count": 0},
                                            {"date": "2026-03-02", "count": 2},
                                            {"date": "2026-03-03", "count": 0}]}


@pytest.mark.asyncio
async def test_heatmap_tool_drops_empty_days_from_the_native_series(fake_ctx):
    """Immich 3.x lists every day of the range, zeros included; the fallback
    only knows days with photos. One shape for the model: days with activity."""
    raw = await server.get_calendar_heatmap(fake_ctx(StubNativeWithZerosClient()))
    result = json.loads(raw)
    assert result["series"] == [{"date": "2026-03-02", "count": 2}]
    assert result["total"] == 2

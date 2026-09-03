"""Timeline: month buckets and their assets, the cheap way to browse by date.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json
from datetime import datetime, timedelta, timezone

import httpx

from mcp.server.mcpserver import Context

from ..app import mcp, _client
from ._common import _api_error

# How far back an open-ended heatmap looks on Immich 2.x. The fallback costs one
# request per month in range, so an unbounded call would walk the whole library.
HEATMAP_DEFAULT_DAYS = 365


@mcp.tool()
async def get_timeline_buckets(
    ctx: Context,
    album_id: str = "",
    person_id: str = "",
    tag_id: str = "",
    is_favorite: bool | None = None,
    order: str = "",
) -> str:
    """Month-by-month map of the library: one bucket per month with its asset count.
    Use this before fetching assets — it shows in one cheap call which months hold
    photos and how many, ideal for finding gaps, busy periods, or navigating a large
    library without paging through everything. Read-only.

    Args:
        album_id: Only count assets in this album.
        person_id: Only count assets showing this person.
        tag_id: Only count assets carrying this tag.
        is_favorite: If true, only count favorites.
        order: 'desc' for newest month first (the default), 'asc' for oldest first.

    Returns: JSON with total_buckets and a buckets array of {timeBucket, count},
    newest month first unless order='asc'.
    """
    # The ordering is asked for explicitly rather than inherited from whatever
    # Immich happens to return, so the documented "newest first" is a guarantee.
    result = await _client(ctx).get_timeline_buckets(
        album_id=album_id or None,
        person_id=person_id or None,
        tag_id=tag_id or None,
        is_favorite=is_favorite,
        order=order or "desc",
    )
    return json.dumps({"total_buckets": len(result), "buckets": result}, default=str)


@mcp.tool()
async def get_timeline_bucket(
    ctx: Context,
    time_bucket: str,
    album_id: str = "",
    person_id: str = "",
    tag_id: str = "",
    is_favorite: bool | None = None,
) -> str:
    """The assets of one month bucket from get_timeline_buckets. Use the two tools
    together to walk a library month by month without expensive searches. Read-only.

    Args:
        time_bucket: The bucket key exactly as get_timeline_buckets returned it
            (e.g. '2026-03-01').
        album_id: Only assets in this album.
        person_id: Only assets showing this person.
        tag_id: Only assets carrying this tag.
        is_favorite: If true, only favorites.

    Returns: JSON with an assets array; each row has asset_id, date, is_image,
    is_favorite, duration, city and country.
    """
    # A key that is not a real bucket (a month Immich never returned, or a
    # free-form date) answers 400; the status says so instead of failing bare.
    try:
        result = await _client(ctx).get_timeline_bucket(
            time_bucket,
            album_id=album_id or None,
            person_id=person_id or None,
            tag_id=tag_id or None,
            is_favorite=is_favorite,
        )
    except httpx.HTTPStatusError as exc:
        return _api_error(exc)

    # Immich answers columnar (one array per field, same length); rows are what
    # a model can actually read, so zip the interesting columns back together.
    ids = result.get("id") or []
    dates = result.get("fileCreatedAt") or []
    is_image = result.get("isImage") or []
    favorites = result.get("isFavorite") or []
    durations = result.get("duration") or []
    cities = result.get("city") or []
    countries = result.get("country") or []

    def column(values, index):
        return values[index] if index < len(values) else None

    rows = []
    for index, asset_id in enumerate(ids):
        rows.append({
            "asset_id": asset_id,
            "date": column(dates, index),
            "is_image": column(is_image, index),
            "is_favorite": column(favorites, index),
            "duration": column(durations, index),
            "city": column(cities, index),
            "country": column(countries, index),
        })
    return json.dumps({"time_bucket": time_bucket, "total": len(rows), "assets": rows},
                      default=str)


def _bucket_in_range(time_bucket: str, from_date: str, to_date: str) -> bool:
    """A month bucket overlaps [from, to] when its month is not entirely
    before `from` nor entirely after `to`. Bucket keys look like 2026-03-01."""
    month = time_bucket[:7]
    if from_date and month < from_date[:7]:
        return False
    if to_date and month > to_date[:7]:
        return False
    return True


def _default_from_date() -> str:
    """The lower bound an open-ended 2.x heatmap falls back to: one year ago
    today, in UTC. Isolated so tests can pin the arithmetic."""
    return (datetime.now(timezone.utc) - timedelta(days=HEATMAP_DEFAULT_DAYS)).date().isoformat()


async def _heatmap_from_timeline(client, from_date: str, to_date: str) -> dict:
    """Immich 2.x has no heatmap route: count the timeline's assets per taken
    day instead. One request per month in range, none outside it."""
    # Without a lower bound this would fetch every month the library has ever
    # held, so an open-ended call is narrowed to the last year instead.
    if not from_date:
        from_date = _default_from_date()

    buckets = await client.get_timeline_buckets()
    counts: dict[str, int] = {}

    for bucket in buckets:
        key = bucket.get("timeBucket") or ""
        if not _bucket_in_range(key, from_date, to_date):
            continue
        rows = await client.get_timeline_bucket(key)
        for taken_at in rows.get("fileCreatedAt") or []:
            day = (taken_at or "")[:10]
            if from_date and day < from_date:
                continue
            if to_date and day > to_date:
                continue
            counts[day] = counts.get(day, 0) + 1

    series = [{"date": day, "count": counts[day]} for day in sorted(counts)]
    return {"source": "timeline", "total": sum(counts.values()), "series": series}


@mcp.tool()
async def get_calendar_heatmap(
    ctx: Context,
    from_date: str = "",
    to_date: str = "",
    heatmap_type: str = "Taken",
) -> str:
    """How many photos per day, over a date range — the data behind a calendar
    heatmap. Use this to find gaps (months with nothing), busy periods, or to
    check a library's health at a glance without listing assets. Immich 3.x
    answers natively; on Immich 2.x the same shape is built from the timeline
    (taken dates only), which costs one request per month in the range, so pass
    the narrowest range that answers the question. Read-only.

    Args:
        from_date: ISO date lower bound (e.g. '2026-01-01'). Omit for the server
            default on Immich 3.x; on 2.x an omitted bound means the last 365 days,
            because an open-ended range would walk every month of the library.
        to_date: ISO date upper bound. Omit for the server default.
        heatmap_type: 'Taken' (capture date, default) or 'Upload' (when it reached
            Immich; 3.x only).

    Returns: JSON with source ('immich' or 'timeline'), total and a series of
    {date, count} for the days that have activity, oldest first (a day missing
    from the series had nothing).
    """
    try:
        result = await _client(ctx).get_calendar_heatmap(
            from_date=from_date or None,
            to_date=to_date or None,
            heatmap_type=heatmap_type,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise
        # 404 means Immich 2.x: no heatmap route at all.
        if heatmap_type != "Taken":
            return json.dumps({
                "error": "This Immich version has no upload-date heatmap; only "
                         "type='Taken' is available here (built from the timeline).",
            })
        fallback = await _heatmap_from_timeline(_client(ctx), from_date, to_date)
        return json.dumps(fallback)

    # Immich 3.x lists every day of the range, zeros included (365 entries for a
    # year); the 2.x fallback only knows days with photos. One shape for the
    # model, and far fewer tokens: days with activity only.
    series = [{"date": entry.get("date"), "count": entry.get("count", 0)}
              for entry in result.get("series") or []
              if entry.get("count", 0) > 0]
    return json.dumps({
        "source": "immich",
        "total": result.get("totalCount", sum(entry["count"] for entry in series)),
        "series": series,
    })

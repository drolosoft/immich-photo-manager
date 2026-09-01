"""Timeline: month buckets and their assets, the cheap way to browse by date.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

from mcp.server.mcpserver import Context

from ..app import mcp, _client


@mcp.tool()
async def get_timeline_buckets(
    ctx: Context,
    album_id: str = "",
    person_id: str = "",
    tag_id: str = "",
    is_favorite: bool | None = None,
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

    Returns: JSON with total_buckets and a buckets array of {timeBucket, count},
    newest month first.
    """
    result = await _client(ctx).get_timeline_buckets(
        album_id=album_id or None,
        person_id=person_id or None,
        tag_id=tag_id or None,
        is_favorite=is_favorite,
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
    result = await _client(ctx).get_timeline_bucket(
        time_bucket,
        album_id=album_id or None,
        person_id=person_id or None,
        tag_id=tag_id or None,
        is_favorite=is_favorite,
    )

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

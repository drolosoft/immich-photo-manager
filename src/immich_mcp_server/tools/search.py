"""Search: EXIF metadata filters and CLIP smart search.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

import httpx
from mcp.server.mcpserver import Context

from ..app import mcp, _client
from ._common import _api_error

@mcp.tool()
async def search_metadata(
    ctx: Context,
    city: str = "",
    state: str = "",
    country: str = "",
    make: str = "",
    model: str = "",
    taken_after: str = "",
    taken_before: str = "",
    is_favorite: bool | None = None,
    asset_type: str = "",
    ocr: str = "",
    person_ids: list[str] | None = None,
    tag_ids: list[str] | None = None,
    album_ids: list[str] | None = None,
    page: int = 1,
    size: int = 50,
) -> str:
    """Search assets by EXIF metadata fields. Use this when you know specific criteria
    like city, camera model, or date range. For natural language visual queries (e.g.
    'sunset at the beach'), use search_smart instead. For browsing without criteria,
    use list_assets. Read-only.

    Args:
        city: City name from EXIF GPS reverse-geocoding (case-sensitive, e.g. 'Barcelona').
        state: State or region name.
        country: Country name (e.g. 'Spain', 'Egypt').
        make: Camera manufacturer (e.g. 'Apple', 'Canon', 'Sony').
        model: Camera model string (e.g. 'iPhone 14 Pro', 'EOS R5').
        taken_after: ISO date — return only assets captured after this date.
        taken_before: ISO date — return only assets captured before this date.
        is_favorite: If true, only return favorites.
        asset_type: 'IMAGE' or 'VIDEO'. Omit for both.
        ocr: Text recognized inside the image (tickets, signs, documents). Needs
            OCR enabled on the server — check with get_capabilities.
        person_ids: Only assets showing ALL of these people (ids from list_people).
        tag_ids: Only assets carrying these tags (ids from list_tags).
        album_ids: Only assets inside these albums.
        page: Page number, starting from 1 (default 1).
        size: Results per page (1-200, default 50).

    Returns: JSON with total match count, current page, and assets array with IDs, filenames, and dates.
    """
    # An id that is not a UUID (a person or tag name passed by mistake) makes
    # Immich answer 400; the status and its message say more than a bare failure.
    try:
        result = await _client(ctx).search_metadata(
            city=city or None,
            state=state or None,
            country=country or None,
            make=make or None,
            model=model or None,
            taken_after=taken_after or None,
            taken_before=taken_before or None,
            is_favorite=is_favorite,
            asset_type=asset_type or None,
            ocr=ocr or None,
            person_ids=person_ids or None,
            tag_ids=tag_ids or None,
            album_ids=album_ids or None,
            page=page,
            size=min(size, 200),
        )
    except httpx.HTTPStatusError as exc:
        return _api_error(exc)

    # Flatten the response for easier consumption
    assets = result.get("assets", {}).get("items", [])
    total = result.get("assets", {}).get("total", 0)
    return json.dumps({"total": total, "page": page, "assets": assets}, default=str)


@mcp.tool()
async def search_explore(ctx: Context) -> str:
    """Overview of what the library contains, grouped by explore field: one
    representative asset per city and per detected concept (Immich's Explore page).
    Use this to get oriented in an unknown library before searching for anything
    specific — it answers 'what is in here?' in one call. A city only appears once
    it holds at least 5 assets (Immich's own threshold), so small libraries can
    come back empty. Read-only.

    Returns: JSON with total (how many fields came back) and a fields array; each
    field has its name (e.g. 'exifInfo.city') and items pairing each value with one
    representative asset_id.
    """
    result = await _client(ctx).search_explore()

    # Each item carries a full AssetResponseDto; only the id is worth the tokens
    # here — the caller can fetch details or a thumbnail for any id that interests it.
    fields = []
    for field in result:
        items = [{"value": item.get("value"), "asset_id": item.get("data", {}).get("id")}
                 for item in field.get("items", [])]
        fields.append({"field": field.get("fieldName"), "items": items})
    return json.dumps({"total": len(fields), "fields": fields}, default=str)


@mcp.tool()
async def search_cities(ctx: Context) -> str:
    """Every city that appears in the library, one representative asset each.
    Unlike search_explore this has no minimum-asset threshold, so it is the
    reliable way to answer 'which places are in this library?'. Read-only.

    Returns: JSON with a cities array of {city, country, asset_id, date}.
    """
    result = await _client(ctx).search_cities()

    cities = []
    for asset in result:
        exif = asset.get("exifInfo") or {}
        cities.append({
            "city": exif.get("city"),
            "country": exif.get("country"),
            "asset_id": asset.get("id"),
            "date": asset.get("fileCreatedAt"),
        })
    return json.dumps({"total": len(cities), "cities": cities}, default=str)


@mcp.tool()
async def search_places(ctx: Context, name: str) -> str:
    """Look a place name up in Immich's built-in gazetteer (no assets involved).
    Use this to resolve a spelling or get coordinates for a place before a
    geographic search. Read-only.

    Args:
        name: Place name to look for (e.g. 'Lisbon').

    Returns: JSON with a places array of {name, admin1name, admin2name, latitude,
    longitude}.
    """
    result = await _client(ctx).search_places(name)
    return json.dumps({"total": len(result), "places": result}, default=str)


@mcp.tool()
async def search_suggestions(
    ctx: Context,
    suggestion_type: str,
    country: str = "",
    state: str = "",
    make: str = "",
    model: str = "",
) -> str:
    """Distinct values present in the library for one field — the exact spellings
    search_metadata expects. Use this before filtering by city or camera to avoid
    guessing (e.g. 'iPhone 14 Pro' vs 'iPhone14,3'). Read-only.

    Args:
        suggestion_type: One of 'country', 'state', 'city', 'camera-make',
            'camera-model', 'camera-lens-model'.
        country: Narrow city/state suggestions to this country.
        state: Narrow city suggestions to this state.
        make: Narrow model suggestions to this camera make.
        model: Narrow lens suggestions to this camera model.

    Returns: JSON with total and a suggestions array of strings.
    """
    # A suggestion_type outside Immich's enum answers 400; the message names the
    # values it accepts, which is exactly what the caller needs to see.
    try:
        result = await _client(ctx).search_suggestions(
            suggestion_type,
            country=country or None,
            state=state or None,
            make=make or None,
            model=model or None,
        )
    except httpx.HTTPStatusError as exc:
        return _api_error(exc)

    return json.dumps({"total": len(result), "suggestions": result}, default=str)


@mcp.tool()
async def search_random(
    ctx: Context,
    size: int = 10,
    city: str = "",
    country: str = "",
    make: str = "",
    model: str = "",
    is_favorite: bool | None = None,
    ocr: str = "",
) -> str:
    """Random assets from the library, optionally filtered. Use this for sampling —
    a quick feel of what a filter matches, a surprise pick for a story, or spot
    checks over a big library. Read-only.

    Args:
        size: How many random assets to return (default 10, max 100).
        city: Only assets from this city.
        country: Only assets from this country.
        make: Only assets from this camera make.
        model: Only assets from this camera model.
        is_favorite: If true, only favorites.
        ocr: Only assets whose recognized text matches (needs OCR on the server).

    Returns: JSON with the matching assets array.
    """
    result = await _client(ctx).search_random(
        size=min(size, 100),
        city=city or None,
        country=country or None,
        make=make or None,
        model=model or None,
        is_favorite=is_favorite,
        ocr=ocr or None,
    )
    return json.dumps({"total": len(result), "assets": result}, default=str)


@mcp.tool()
async def search_statistics(
    ctx: Context,
    city: str = "",
    country: str = "",
    state: str = "",
    make: str = "",
    model: str = "",
    is_favorite: bool | None = None,
    ocr: str = "",
    created_after: str = "",
    created_before: str = "",
    taken_after: str = "",
    taken_before: str = "",
) -> str:
    """Count how many assets match a filter WITHOUT fetching them. Use this instead
    of search_metadata whenever only the number matters ('how many photos from
    Spain?', 'how many did I take in 2019?') — it costs one integer instead of
    pages of assets. Read-only.

    Args:
        city: Count assets from this city.
        country: Count assets from this country.
        state: Count assets from this state/region.
        make: Count assets from this camera make.
        model: Count assets from this camera model.
        is_favorite: If true, count only favorites.
        ocr: Count assets whose recognized text matches (needs OCR on the server).
        created_after: ISO date lower bound on upload date (when it reached Immich).
        created_before: ISO date upper bound on upload date.
        taken_after: ISO date lower bound on capture date (when the photo was taken).
        taken_before: ISO date upper bound on capture date.

    Returns: JSON {total}.
    """
    # A bound Immich cannot parse answers 400; its message names the field.
    try:
        result = await _client(ctx).search_statistics(
            city=city or None,
            country=country or None,
            state=state or None,
            make=make or None,
            model=model or None,
            is_favorite=is_favorite,
            ocr=ocr or None,
            created_after=created_after or None,
            created_before=created_before or None,
            taken_after=taken_after or None,
            taken_before=taken_before or None,
        )
    except httpx.HTTPStatusError as exc:
        return _api_error(exc)

    return json.dumps({"total": result.get("total", 0)})


@mcp.tool()
async def search_large_assets(
    ctx: Context,
    min_size_mb: int = 0,
    size: int = 20,
    asset_type: str = "",
) -> str:
    """The biggest files in the library, largest first. Use this to find what is
    eating storage before a cleanup — videos and originals show up immediately.
    Read-only.

    Args:
        min_size_mb: Only assets at least this many megabytes (0 = no minimum).
        size: How many assets to return (1-200, default 20).
        asset_type: 'IMAGE' or 'VIDEO'. Omit for both.

    Returns: JSON with total and an assets array of {asset_id, filename, size_mb,
    date}, largest first.
    """
    # The same page-size cap the other searches apply, and 0 means the tool's own
    # default rather than the server's, so `size` reads the same everywhere.
    result = await _client(ctx).search_large_assets(
        min_file_size=min_size_mb * 1024 * 1024 if min_size_mb else None,
        size=min(size, 200) if size else 20,
        asset_type=asset_type or None,
    )

    assets = []
    for asset in result:
        size_bytes = (asset.get("exifInfo") or {}).get("fileSizeInByte") or 0
        assets.append({
            "asset_id": asset.get("id"),
            "filename": asset.get("originalFileName"),
            "size_mb": round(size_bytes / 1024 / 1024, 1),
            "date": asset.get("fileCreatedAt"),
        })
    return json.dumps({"total": len(assets), "assets": assets}, default=str)


@mcp.tool()
async def search_smart(
    ctx: Context,
    query: str,
    city: str = "",
    state: str = "",
    country: str = "",
    taken_after: str = "",
    taken_before: str = "",
    ocr: str = "",
    person_ids: list[str] | None = None,
    tag_ids: list[str] | None = None,
    album_ids: list[str] | None = None,
    page: int = 1,
    size: int = 50,
) -> str:
    """AI-powered visual search using CLIP embeddings. Use this when describing what a
    photo looks like in natural language (e.g. 'sunset at the beach', 'dog playing fetch').
    For structured criteria (city, camera, date), use search_metadata instead. Requires
    Immich ML service with Smart Search enabled. Read-only.

    Args:
        query: Natural language description of the visual content to find.
        city: Optional city filter to narrow results geographically.
        state: Optional state/region filter.
        country: Optional country filter.
        taken_after: ISO date — only assets captured after this date.
        taken_before: ISO date — only assets captured before this date.
        ocr: Text recognized inside the image, combined with the visual query.
            Needs OCR enabled on the server — check with get_capabilities.
        person_ids: Only assets showing ALL of these people (ids from list_people).
        tag_ids: Only assets carrying these tags (ids from list_tags).
        album_ids: Only assets inside these albums.
        page: Page number, starting from 1 (default 1).
        size: Results per page (1-200, default 50).

    Returns: JSON with total count, page, and assets ranked by visual similarity to the query.
    """
    try:
        result = await _client(ctx).search_smart(
            query=query,
            city=city or None,
            state=state or None,
            country=country or None,
            taken_after=taken_after or None,
            taken_before=taken_before or None,
            ocr=ocr or None,
            person_ids=person_ids or None,
            tag_ids=tag_ids or None,
            album_ids=album_ids or None,
            page=page,
            size=min(size, 200),
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 500:
            return json.dumps({
                "error": "Smart search is not available on this Immich server.",
                "detail": (
                    "The Immich machine learning service may not be running, "
                    "or Smart Search (CLIP) is disabled. "
                    "Enable it in Administration > Settings > Machine Learning Settings > Smart Search. "
                    "See https://immich.app/docs/features/smart-search for details."
                ),
                "http_status": 500,
            })
        # Any other status is Immich rejecting the request itself, most often a
        # 400 on a person, tag or album id that is not a UUID.
        return _api_error(exc)

    assets = result.get("assets", {}).get("items", [])
    total = result.get("assets", {}).get("total", 0)
    return json.dumps({"total": total, "page": page, "assets": assets}, default=str)

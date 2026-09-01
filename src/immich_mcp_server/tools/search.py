"""Search: EXIF metadata filters and CLIP smart search.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

import httpx
from mcp.server.mcpserver import Context

from ..app import mcp, _client

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
        page: Page number, starting from 1 (default 1).
        size: Results per page (1-200, default 50).

    Returns: JSON with total match count, current page, and assets array with IDs, filenames, and dates.
    """
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
        page=page,
        size=min(size, 200),
    )
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

    Returns: JSON with a fields array; each field has its name (e.g. 'exifInfo.city')
    and items pairing each value with one representative asset_id.
    """
    result = await _client(ctx).search_explore()

    # Each item carries a full AssetResponseDto; only the id is worth the tokens
    # here — the caller can fetch details or a thumbnail for any id that interests it.
    fields = []
    for field in result:
        items = [{"value": item.get("value"), "asset_id": item.get("data", {}).get("id")}
                 for item in field.get("items", [])]
        fields.append({"field": field.get("fieldName"), "items": items})
    return json.dumps({"fields": fields}, default=str)


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
        raise
    assets = result.get("assets", {}).get("items", [])
    total = result.get("assets", {}).get("total", 0)
    return json.dumps({"total": total, "page": page, "assets": assets}, default=str)

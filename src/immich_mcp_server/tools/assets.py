"""Single-asset tools: info, metadata repair, rotation edits and their revert, map markers.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

import httpx
from mcp.server.mcpserver import Context

from ..app import mcp, _client
from ._common import _album_assets

@mcp.tool()
async def get_asset_info(ctx: Context, asset_id: str) -> str:
    """Get full metadata for a single asset. Use this when you need EXIF details,
    GPS coordinates, camera info, or file properties for a known asset ID.
    For finding assets, use search_metadata or search_smart instead. Read-only.

    Args:
        asset_id: The asset's UUID (from search results, album listings, or list_assets).

    Returns: JSON with EXIF data, GPS, dates, dimensions, file size, camera make/model, and owner.
    """
    result = await _client(ctx).get_asset(asset_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def update_asset_metadata(
    ctx: Context,
    asset_id: str,
    date_time_original: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    description: str = "",
    is_favorite: bool | None = None,
    rating: int | None = None,
) -> str:
    """Update metadata fields on a specific asset. Use this to fix dates, correct GPS,
    add descriptions, or change favorite/rating status. Only provided fields are modified.
    Side effect: permanently changes asset metadata in Immich.

    Args:
        asset_id: The asset's UUID.
        date_time_original: ISO 8601 datetime (e.g. '2019-07-14T15:23:41.000Z').
        latitude: GPS latitude, decimal degrees (-90.0 to 90.0).
        longitude: GPS longitude, decimal degrees (-180.0 to 180.0).
        description: Free-text description/caption for the asset.
        is_favorite: Set favorite status (true/false).
        rating: Star rating (1-5), or null to clear.

    Returns: JSON with the updated asset object.
    """
    fields: dict = {}
    if date_time_original:
        fields["dateTimeOriginal"] = date_time_original
    if latitude is not None:
        fields["latitude"] = latitude
    if longitude is not None:
        fields["longitude"] = longitude
    if description:
        fields["description"] = description
    if is_favorite is not None:
        fields["isFavorite"] = is_favorite
    if rating is not None:
        fields["rating"] = rating
    if not fields:
        return json.dumps({"error": "No fields to update. Provide at least one field."})
    result = await _client(ctx).update_asset(asset_id, **fields)
    return json.dumps(result, default=str)


async def _rotate_one(client, asset_id: str, angle: int) -> None:
    """Add `angle` degrees to the asset's current rotation, keeping its other edits.

    Immich's edits API replaces the whole edit list on every write, so the
    existing crop or mirror entries are read first and written back untouched.
    A rotation that lands on 0 removes the record instead of storing a no-op.
    """
    try:
        existing = (await client.get_asset_edits(asset_id)).get("edits", []) or []
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise  # unreadable edits: fail the asset rather than guess the angle
        existing = []  # the asset simply has no edits yet
    current_angle = 0
    for edit in existing:
        if edit.get("action") == "rotate":
            current_angle = edit.get("parameters", {}).get("angle", 0)
    other_edits = [edit for edit in existing if edit.get("action") != "rotate"]
    new_angle = (current_angle + angle) % 360
    new_edits = list(other_edits)
    if new_angle:
        new_edits.append({"action": "rotate", "parameters": {"angle": new_angle}})
    if new_edits:
        await client.apply_asset_edits(asset_id, new_edits)
    else:
        await client.delete_asset_edits(asset_id)


@mcp.tool()
async def rotate_assets(
    ctx: Context,
    angle: int = 90,
    asset_ids: list[str] | None = None,
    album_id: str = "",
) -> str:
    """Apply a non-destructive clockwise rotation to one or more assets. Use this to
    fix orientation issues. The original file is never modified — rotation is a display
    transform only. Use revert_asset_edits to undo. Provide EITHER asset_ids OR album_id.
    Side effect: writes rotation edits to Immich; accumulates with existing rotation.

    Args:
        angle: Clockwise degrees, must be a multiple of 90 (90, 180, or 270). Default: 90.
        asset_ids: List of asset UUIDs to rotate. Mutually exclusive with album_id.
        album_id: Rotate all assets in this album. Mutually exclusive with asset_ids.

    Returns: JSON with rotated/failed counts and the applied angle.
    """
    if angle % 90 != 0:
        return json.dumps({"error": "Angle must be a multiple of 90 (90, 180, 270)."})

    client = _client(ctx)

    # Resolve asset IDs from album if provided
    ids: list[str] = []
    album_name = ""
    if album_id:
        album = await client.get_album(album_id)
        album_name = album.get("albumName", "")
        ids = [asset["id"] for asset in await _album_assets(client, album_id, album)]
        if not ids:
            return json.dumps({"error": f"Album '{album_name}' is empty."})
    elif asset_ids:
        ids = asset_ids
    else:
        return json.dumps({"error": "Provide either asset_ids or album_id."})

    results: dict = {"rotated": 0, "failed": 0, "errors": []}
    for asset_id in ids:
        try:
            await _rotate_one(client, asset_id, angle)
            results["rotated"] += 1
        except Exception as exc:
            results["failed"] += 1
            results["errors"].append({"asset_id": asset_id, "error": str(exc)})

    results["angle"] = angle
    results["total_requested"] = len(ids)
    if album_name:
        results["album"] = album_name
    if not results["errors"]:
        del results["errors"]
    return json.dumps(results, default=str)


@mcp.tool()
async def revert_asset_edits(
    ctx: Context,
    asset_ids: list[str] | None = None,
    album_id: str = "",
) -> str:
    """Remove all non-destructive edits (rotation, crop, mirror) from assets, restoring
    original appearance. Use this to undo rotate_assets or any other display transforms.
    Provide EITHER asset_ids OR album_id. Side effect: deletes all edit records for the assets.

    Args:
        asset_ids: List of asset UUIDs to revert. Mutually exclusive with album_id.
        album_id: Revert all assets in this album. Mutually exclusive with asset_ids.

    Returns: JSON with reverted/failed counts.
    """
    client = _client(ctx)

    ids: list[str] = []
    album_name = ""
    if album_id:
        album = await client.get_album(album_id)
        album_name = album.get("albumName", "")
        ids = [asset["id"] for asset in await _album_assets(client, album_id, album)]
        if not ids:
            return json.dumps({"error": f"Album '{album_name}' is empty."})
    elif asset_ids:
        ids = asset_ids
    else:
        return json.dumps({"error": "Provide either asset_ids or album_id."})

    results: dict = {"reverted": 0, "failed": 0, "errors": []}
    for aid in ids:
        try:
            await client.delete_asset_edits(aid)
            results["reverted"] += 1
        except Exception as exc:
            results["failed"] += 1
            results["errors"].append({"asset_id": aid, "error": str(exc)})

    results["total_requested"] = len(ids)
    if album_name:
        results["album"] = album_name
    if not results["errors"]:
        del results["errors"]
    return json.dumps(results, default=str)


@mcp.tool()
async def get_map_markers(
    ctx: Context,
    file_created_after: str = "",
    file_created_before: str = "",
    is_favorite: bool | None = None,
) -> str:
    """Get GPS map markers for all geotagged assets. Use this to discover where photos
    were taken or to build travel maps. For searching by city/country name, use
    search_metadata instead. Read-only. Returns up to 500 markers.

    Args:
        file_created_after: ISO date lower bound (e.g. '2023-01-01').
        file_created_before: ISO date upper bound.
        is_favorite: If true, only return favorites.

    Returns: JSON with total count and markers array (each with asset ID, lat, lon).
    """
    result = await _client(ctx).get_map_markers(
        file_created_after=file_created_after or None,
        file_created_before=file_created_before or None,
        is_favorite=is_favorite,
    )
    return json.dumps({"total": len(result), "markers": result[:500]}, default=str)

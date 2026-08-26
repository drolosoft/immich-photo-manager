"""
Immich MCP Server — Photo management tools for Claude.

Part of the immich-photo-manager plugin.
License: MIT
"""

import asyncio
import base64
import json
import os
import sys
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from mcp.server.fastmcp import FastMCP, Context, Image
from mcp.server.transport_security import TransportSecuritySettings

from . import video_frames
from .immich_client import ImmichClient

# FastMCP's Settings model declares `lifespan` using a forward reference to the
# FastMCP class (defined later in the SDK), which pydantic-settings reports as an
# incomplete definition at startup. The field is never populated from environment
# variables, so this is harmless — silence it to keep startup logs clean.
try:
    from pydantic_settings.sources.utils import IncompleteFieldDefinitionWarning
except ImportError:  # pragma: no cover
    IncompleteFieldDefinitionWarning = None

if IncompleteFieldDefinitionWarning is not None:
    warnings.filterwarnings("ignore", category=IncompleteFieldDefinitionWarning)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialize the Immich client on server startup."""
    client = ImmichClient()
    # Verify connection at startup. Diagnostics go to stderr — under the
    # stdio transport stdout carries JSON-RPC and must stay pristine.
    try:
        await client.ping()
    except Exception as e:
        print(
            f"Warning: Could not connect to Immich at {client.base_url}: {e}",
            file=sys.stderr,
        )
    yield {"immich": client}


# When served over HTTP behind a reverse proxy, the proxied Host header (e.g.
# photos-mcp.example.com) must be allowed explicitly: FastMCP auto-enables DNS
# rebinding protection that accepts only 127.0.0.1/localhost Hosts, answering
# 421 Misdirected Request otherwise. MCP_ALLOWED_HOSTS is a comma-separated
# list of additional allowed Host values; localhost stays allowed and
# protection stays ON. Unset = SDK default behavior, unchanged.
_extra_hosts = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
_transport_security = None
if _extra_hosts:
    # A configured host may be a bare host/IP (allow any port via the SDK's
    # ":*" wildcard) or already include a port. The Host header always carries
    # the port, so a bare value like "192.168.1.10" would never match
    # "192.168.1.10:8626" — append a ":*" variant for portless entries.
    _allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    _allowed_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    for h in _extra_hosts:
        _allowed_hosts.append(h)
        if ":" not in h:
            _allowed_hosts.append(f"{h}:*")
        _allowed_origins.extend((f"http://{h}", f"https://{h}"))
    _transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_allowed_hosts,
        allowed_origins=_allowed_origins,
    )

mcp = FastMCP(
    "immich-photo-manager",
    instructions="Intelligent photo management for Immich. Search, curate albums, and publish galleries.",
    lifespan=app_lifespan,
    transport_security=_transport_security,
)


def _client(ctx: Context) -> ImmichClient:
    """Get the Immich client from the request context."""
    return ctx.request_context.lifespan_context["immich"]


# ── Health & Stats ──────────────────────────────────────────


async def _album_assets(client, album_id: str, album: dict) -> list[dict]:
    """Album assets across Immich versions, always via POST /search/metadata
    (albumIds, withPeople). Immich >= 3.0 no longer inlines `assets` in the album,
    and the inline list on 2.x lacks recognized people, so the search path is the
    only one that is both version-independent and complete."""
    return await client.get_album_assets(album_id)


@mcp.tool()
async def ping(ctx: Context) -> str:
    """Check Immich server connectivity. Use this to verify the server is reachable
    before running other operations. Read-only.

    Returns: JSON with 'server' status ('pong' if healthy).
    """
    result = await _client(ctx).ping()
    return json.dumps(result)


@mcp.tool()
async def get_server_version(ctx: Context) -> str:
    """Get the Immich server version. Use this to check compatibility or report
    the running server version. Read-only.

    Returns: JSON with major, minor, and patch version numbers.
    """
    result = await _client(ctx).get_server_version()
    return json.dumps(result)


@mcp.tool()
async def get_statistics(ctx: Context) -> str:
    """Get library statistics. Use this for a quick overview of library size
    without listing individual assets. Read-only.

    Returns: JSON with total photo count, video count, and storage usage in bytes.
    """
    result = await _client(ctx).get_statistics()
    return json.dumps(result)


# ── Credential Management ──────────────────────────────────


@mcp.tool()
async def update_credentials(ctx: Context, base_url: str, api_key: str) -> str:
    """Update the Immich connection credentials. Use this when the API key has been
    rotated or the server URL changed. Validates credentials before applying.
    Side effect: persists new credentials to disk and hot-swaps the live connection.

    Args:
        base_url: Full Immich server URL including protocol (e.g. 'https://photos.example.com').
        api_key: A valid Immich API key (generated in Immich > User Settings > API Keys).

    Returns: JSON with success status, photo/video counts confirming access, and persistence path.
    """
    # 1. Create a new client carrying exactly the provided credentials
    # (explicit args bypass the config.json override and the environment)
    try:
        new_client = ImmichClient(base_url=base_url, api_key=api_key)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Invalid credentials: {e}",
        })

    # 2. Verify the new credentials actually work. /server/ping is public and
    # would accept any key; verify_access() needs the key to be honoured.
    try:
        await new_client.verify_access()
    except httpx.HTTPStatusError as e:
        return json.dumps({
            "success": False,
            "error": (
                f"Immich at {base_url} rejected the API key "
                f"(HTTP {e.response.status_code}). Check the API key is correct."
            ),
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": (
                f"Could not connect to Immich at {base_url}: {e}. "
                "Check the URL and API key are correct."
            ),
        })

    # 3. Persist to cache dir so they survive restarts
    try:
        config_path = ImmichClient.save_config(base_url, api_key)
    except RuntimeError:
        # Credentials work but can't persist — still swap the live client
        config_path = None

    # 4. Hot-swap the live client (no restart needed)
    ctx.request_context.lifespan_context["immich"] = new_client

    # 5. Get stats to confirm everything works
    try:
        stats = await new_client.get_statistics()
        photo_count = stats.get("photos", 0)
        video_count = stats.get("videos", 0)
    except Exception:
        photo_count = "?"
        video_count = "?"

    result = {
        "success": True,
        "base_url": base_url,
        "photos": photo_count,
        "videos": video_count,
    }
    if config_path:
        result["persisted_to"] = config_path
    else:
        result["warning"] = (
            "Credentials updated for this session but could NOT be persisted to disk. "
            "They will be lost on restart."
        )

    return json.dumps(result, default=str)


# ── Asset Info ──────────────────────────────────────────────


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
        ids = [a["id"] for a in await _album_assets(client, album_id, album)]
        if not ids:
            return json.dumps({"error": f"Album '{album_name}' is empty."})
    elif asset_ids:
        ids = asset_ids
    else:
        return json.dumps({"error": "Provide either asset_ids or album_id."})

    results: dict = {"rotated": 0, "failed": 0, "errors": []}
    for aid in ids:
        try:
            # Read the full current edit list — apply replaces it wholesale,
            # so anything not carried over (crop, mirror) would be lost.
            try:
                existing = (await client.get_asset_edits(aid)).get("edits", []) or []
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    existing = []  # asset simply has no edits yet
                else:
                    raise  # unreadable edits: fail the asset, never guess the angle
            current_angle = 0
            for edit in existing:
                if edit.get("action") == "rotate":
                    current_angle = edit.get("parameters", {}).get("angle", 0)
            other_edits = [e for e in existing if e.get("action") != "rotate"]
            new_angle = (current_angle + angle) % 360
            new_edits = other_edits + (
                [{"action": "rotate", "parameters": {"angle": new_angle}}]
                if new_angle else []
            )
            if new_edits:
                await client.apply_asset_edits(aid, new_edits)
            else:
                # Nothing left at all — remove the (rotation-only) edit record
                await client.delete_asset_edits(aid)
            results["rotated"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"asset_id": aid, "error": str(e)})

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
        ids = [a["id"] for a in await _album_assets(client, album_id, album)]
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
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"asset_id": aid, "error": str(e)})

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


# ── Search ──────────────────────────────────────────────────


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
        page=page,
        size=min(size, 200),
    )
    # Flatten the response for easier consumption
    assets = result.get("assets", {}).get("items", [])
    total = result.get("assets", {}).get("total", 0)
    return json.dumps({"total": total, "page": page, "assets": assets}, default=str)


@mcp.tool()
async def search_smart(
    ctx: Context,
    query: str,
    city: str = "",
    state: str = "",
    country: str = "",
    taken_after: str = "",
    taken_before: str = "",
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
            page=page,
            size=min(size, 200),
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 500:
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


# ── Albums ──────────────────────────────────────────────────


@mcp.tool()
async def list_albums(ctx: Context, shared: bool | None = None) -> str:
    """List all albums in the library with summary info. Use this to discover existing
    albums before creating new ones or to find an album ID. Read-only.

    Args:
        shared: true = only shared albums, false = only non-shared, omit = all albums.

    Returns: JSON with total count and albums array (each with id, name, description, assetCount, shared status).
    """
    result = await _client(ctx).list_albums(shared=shared)
    albums = [
        {
            "id": a["id"],
            "albumName": a.get("albumName", ""),
            "description": a.get("description", ""),
            "assetCount": a.get("assetCount", 0),
            "shared": a.get("shared", False),
            "hasSharedLink": a.get("hasSharedLink", False),
            "createdAt": a.get("createdAt", ""),
        }
        for a in result
    ]
    return json.dumps({"total": len(albums), "albums": albums}, default=str)


@mcp.tool()
async def get_album(ctx: Context, album_id: str) -> str:
    """Get full details for a specific album including all its asset IDs. Use this to
    inspect album contents or retrieve asset IDs for further operations (thumbnails,
    metadata, rotation). For listing all albums, use list_albums instead. Read-only.

    Args:
        album_id: The album's UUID (from list_albums or create_album).

    Returns: JSON with album metadata, a flat list of all asset_ids, and an assets array
    (id, filename, type, date, recognized people) so "who appears in this album / who
    repeats" can be answered without further calls.
    """
    client = _client(ctx)
    result = await client.get_album(album_id)
    assets = await _album_assets(client, album_id, result)
    return json.dumps(
        {
            "id": result["id"],
            "albumName": result.get("albumName", ""),
            "description": result.get("description", ""),
            "assetCount": result.get("assetCount", 0),
            "shared": result.get("shared", False),
            "hasSharedLink": result.get("hasSharedLink", False),
            "createdAt": result.get("createdAt", ""),
            "updatedAt": result.get("updatedAt", ""),
            "asset_ids": [a["id"] for a in assets],
            "assets": [
                {
                    "id": a["id"],
                    "originalFileName": a.get("originalFileName", ""),
                    "type": a.get("type", ""),
                    "fileCreatedAt": a.get("fileCreatedAt", ""),
                    "people": [
                        {"id": p.get("id"), "name": p.get("name") or ""}
                        for p in (a.get("people") or [])
                    ],
                }
                for a in assets
            ],
        },
        default=str,
    )


@mcp.tool()
async def create_album(
    ctx: Context, name: str, description: str = "", asset_ids: list[str] | None = None
) -> str:
    """Create a new album, optionally pre-populated with assets. Use this to organize
    photos into collections. Side effect: creates a new album in Immich.

    Args:
        name: Album display name (e.g. 'Roma, Italia', 'Birthday 2024').
        description: Optional album description text.
        asset_ids: Optional list of asset UUIDs to add immediately on creation.

    Returns: JSON with the new album's id, name, and asset count.
    """
    result = await _client(ctx).create_album(
        name=name, description=description, asset_ids=asset_ids
    )
    return json.dumps(
        {
            "id": result["id"],
            "albumName": result.get("albumName", ""),
            "assetCount": result.get("assetCount", 0),
        },
        default=str,
    )


@mcp.tool()
async def update_album(
    ctx: Context, album_id: str, name: str = "", description: str = ""
) -> str:
    """Update an album's name or description. Use this to rename or re-describe an
    existing album. Side effect: modifies album metadata in Immich.

    Args:
        album_id: The album's UUID.
        name: New album name. Leave empty to keep current name.
        description: New description. Leave empty to keep current description.

    Returns: JSON with the updated album object.
    """
    result = await _client(ctx).update_album(
        album_id=album_id,
        name=name or None,
        description=description if description else None,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def delete_album(ctx: Context, album_id: str) -> str:
    """Delete an album container. The photos inside are NOT deleted — they remain in
    the library. Use this to remove unwanted album groupings. Side effect: permanently
    deletes the album (cannot be undone).

    Args:
        album_id: The album's UUID to delete.

    Returns: JSON with deleted confirmation and album_id.
    """
    await _client(ctx).delete_album(album_id)
    return json.dumps({"deleted": True, "album_id": album_id})


@mcp.tool()
async def add_assets_to_album(ctx: Context, album_id: str, asset_ids: list[str]) -> str:
    """Add existing assets to an album. Use this to curate albums from search results
    or other asset lists. Assets can belong to multiple albums simultaneously.
    Side effect: modifies album membership.

    Args:
        album_id: Target album UUID.
        asset_ids: List of asset UUIDs to add to the album.

    Returns: JSON with album_id, count added, and per-asset success/error details.
    """
    result = await _client(ctx).add_assets_to_album(album_id, asset_ids)
    return json.dumps({"album_id": album_id, "added": len(asset_ids), "result": result}, default=str)


@mcp.tool()
async def remove_assets_from_album(ctx: Context, album_id: str, asset_ids: list[str]) -> str:
    """Remove assets from an album without deleting them. The photos remain in the
    library and other albums. Use this to un-curate mistakenly added assets.
    Side effect: modifies album membership.

    Args:
        album_id: Album UUID to remove assets from.
        asset_ids: List of asset UUIDs to remove from this album.

    Returns: JSON with album_id, count removed, and per-asset result details.
    """
    result = await _client(ctx).remove_assets_from_album(album_id, asset_ids)
    return json.dumps({"album_id": album_id, "removed": len(asset_ids), "result": result}, default=str)


# ── Thumbnails ──────────────────────────────────────────────


@mcp.tool()
async def get_asset_thumbnail(ctx: Context, asset_id: str, size: str = "thumbnail") -> str:
    """Get a base64-encoded thumbnail image for a single asset. Use this to visually
    inspect one photo. For multiple photos, use get_thumbnails_batch (by IDs) or
    get_album_thumbnails (by album). Read-only.

    Args:
        asset_id: The asset's UUID.
        size: 'thumbnail' (250px, fast) or 'preview' (1440px, higher quality). Default: 'thumbnail'.

    Returns: JSON with 'data' (base64 string) and 'type' (MIME type, e.g. 'image/jpeg').
    """
    result = await _client(ctx).get_asset_thumbnail(asset_id, size)
    return json.dumps(result)


@mcp.tool()
async def get_album_thumbnails(
    ctx: Context, album_id: str, size: str = "thumbnail", limit: int = 20
) -> str:
    """Get base64-encoded thumbnails for photos in an album. Use this to generate visual
    HTML galleries from an existing album. For thumbnails from search results (no album),
    use get_thumbnails_batch instead. Read-only.

    Args:
        album_id: The album's UUID.
        size: 'thumbnail' (250px) or 'preview' (1440px). Default: 'thumbnail'.
        limit: Max thumbnails to return (1-50, default 20).

    Returns: JSON with album info and thumbnails array (each with asset_id, base64 data, filename, date).
    """
    result = await _client(ctx).get_album_thumbnails(
        album_id, size, min(limit, 50)
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def get_thumbnails_batch(
    ctx: Context, asset_ids: list[str], size: str = "thumbnail", limit: int = 20
) -> str:
    """Get base64-encoded thumbnails for arbitrary asset IDs without needing an album.
    Use this to visually display search results or any ad-hoc set of photos. For album-based
    thumbnails, use get_album_thumbnails. For a single photo, use get_asset_thumbnail. Read-only.

    Args:
        asset_ids: List of asset UUIDs to fetch thumbnails for.
        size: 'thumbnail' (250px) or 'preview' (1440px). Default: 'thumbnail'.
        limit: Max thumbnails to return (1-50, default 20). Only the first N IDs are fetched.

    Returns: JSON with thumbnails array (each with asset_id, base64 data, filename, date).
    """
    result = await _client(ctx).get_thumbnails_batch(
        asset_ids, size, min(limit, 50)
    )
    return json.dumps(result, default=str)


# ── Images (visual display) ─────────────────────────────────
#
# These tools return MCP image blocks (ImageContent) for clients that render
# images inline — e.g. Open WebUI, Claude Desktop. They are an alternative view
# of the same thumbnails; the get_*_thumbnail(s) tools above remain the default
# and return base64 JSON, which the skills embed as data: URIs into HTML
# galleries (the Cowork sandbox blocks external requests). Do not change those.


def _image_format_from_mime(mime: str) -> str:
    """Map an image MIME type to an Image format label."""
    mapping = {
        "image/jpeg": "jpeg",
        "image/jpg": "jpeg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
        "image/heic": "heic",
        "image/heif": "heic",
        "image/avif": "avif",
        "image/tiff": "tiff",
    }
    return mapping.get((mime or "image/jpeg").split(";")[0].strip().lower(), "jpeg")


def _entry_to_image(entry: dict) -> Image:
    """Convert a thumbnail entry dict (base64 data + MIME type) to an Image."""
    data = entry.get("data", "")
    raw = base64.b64decode(data) if data else b""
    return Image(data=raw, format=_image_format_from_mime(entry.get("type", "image/jpeg")))


@mcp.tool()
async def get_asset_image(ctx: Context, asset_id: str, size: str = "thumbnail") -> Image:
    """Get a single asset's thumbnail as an image block for inline visual display.
    Use this in clients that render images (Open WebUI, Claude Desktop). For HTML
    gallery generation with base64 data URIs (Cowork/skills), use get_asset_thumbnail
    instead — it returns JSON. Read-only.

    Args:
        asset_id: The asset's UUID.
        size: 'thumbnail' (250px, fast) or 'preview' (1440px, higher quality). Default: 'thumbnail'.

    Returns: An image block (MCP ImageContent) for visual display.
    """
    result = await _client(ctx).get_asset_thumbnail(asset_id, size)
    return _entry_to_image(result)


@mcp.tool(structured_output=False)
async def get_album_images(
    ctx: Context, album_id: str, size: str = "thumbnail", limit: int = 20
) -> list[Image]:
    """Get an album's thumbnails as image blocks for inline visual display. Use this
    to visually browse an album in clients that render images. For HTML gallery
    generation with base64 data URIs (Cowork/skills), use get_album_thumbnails
    instead — it returns JSON with filenames and dates. Read-only.

    Args:
        album_id: The album's UUID.
        size: 'thumbnail' (250px) or 'preview' (1440px). Default: 'thumbnail'.
        limit: Max thumbnails to return (1-50, default 20).

    Returns: A list of image blocks suitable for visual display.
    """
    result = await _client(ctx).get_album_thumbnails(album_id, size, min(limit, 50))
    return [_entry_to_image(t) for t in result.get("thumbnails", [])]


@mcp.tool(structured_output=False)
async def get_images_batch(
    ctx: Context, asset_ids: list[str], size: str = "thumbnail", limit: int = 20
) -> list[Image]:
    """Get thumbnails for arbitrary asset IDs as image blocks for inline visual
    display. Use this to visually show search results in clients that render images.
    For HTML gallery generation with base64 data URIs (Cowork/skills), use
    get_thumbnails_batch instead — it returns JSON with filenames and dates. Read-only.

    Args:
        asset_ids: List of asset UUIDs to fetch thumbnails for.
        size: 'thumbnail' (250px) or 'preview' (1440px). Default: 'thumbnail'.
        limit: Max thumbnails to return (1-50, default 20). Only the first N IDs are fetched.

    Returns: A list of image blocks suitable for visual display.
    """
    result = await _client(ctx).get_thumbnails_batch(asset_ids, size, min(limit, 50))
    return [_entry_to_image(t) for t in result.get("thumbnails", [])]


# ── Video frames ────────────────────────────────────────────


async def _video_plan(ctx: Context, asset_id: str, count: int, size: str,
                      start: float, end: float, interval: float, confirm: bool):
    """Download the video, plan the frames, and either extract or return the gate JSON."""
    data = await _client(ctx).get_video_playback(asset_id)
    duration = await asyncio.to_thread(video_frames.probe_duration, data)
    try:
        planned = video_frames.plan_timestamps(duration, count, interval, start, end)
    except video_frames.TooManyFrames as exc:
        return None, {"error": str(exc), "duration": duration}
    if len(planned) > video_frames.CONFIRM_ABOVE and not confirm:
        seg_start, seg_end = video_frames.segment_bounds(duration, start, end)
        return None, {
            "confirm_required": True, "asset_id": asset_id, "duration": duration,
            "segment": [round(seg_start, 3), round(seg_end, 3)], "frames_planned": len(planned),
            "estimated_tokens": video_frames.estimate_tokens(len(planned), size),
            "hint": "Tell the user the number of frames and tokens; call again with confirm=true to proceed.",
        }
    result = await asyncio.to_thread(
        video_frames.extract_frames, data, count, size, None, start, end, interval
    )
    return result, None


_VIDEO_ARGS = """
    Args:
        asset_id: The video asset's UUID.
        count: Frames evenly spaced over the segment (default 6). Ignored when interval > 0.
        size: 'thumbnail' (250px, ~1.6k tokens per frame) or 'preview' (1440px, ~6.4k). Default 'thumbnail'.
        start: Segment start in seconds (default 0). end: Segment end in seconds (0 = to the end).
        interval: One frame every N seconds instead of count (1 = one per second, the maximum granularity).
        confirm: Required (true) when more than 12 frames would be produced; ask the user first.
"""


@mcp.tool(structured_output=False)
async def get_video_frames(
    ctx: Context, asset_id: str, count: int = 6, size: str = "thumbnail",
    start: float = 0.0, end: float = 0.0, interval: float = 0.0, confirm: bool = False,
) -> list[Image] | str:
    """Get frames of a video as image blocks, to "watch" a clip. Immich keeps one
    poster per video; this downloads the video and cuts frames locally (PyAV via
    `pip install immich-photo-manager[video]`, or ffmpeg on PATH). Every frame is one
    image for the model. Workflow: 6 frames first; to look closer, narrow with
    start/end or use interval (down to 1 s). Above 12 frames the tool returns a JSON
    plan with frames_planned and estimated_tokens instead of images: show it to the
    user and call again with confirm=true only if they agree. Hard cap 120 per call.
    For base64 JSON with timestamps use get_video_frames_json. Read-only.
    """ + _VIDEO_ARGS + """
    Returns: JPEG image blocks in time order, or JSON (confirmation plan / error).
    """
    try:
        result, gate = await _video_plan(ctx, asset_id, count, size, start, end, interval, confirm)
    except video_frames.NoVideoBackend as exc:
        return json.dumps({"error": str(exc)})
    if gate is not None:
        return json.dumps(gate)
    return [_entry_to_image(f) for f in result["frames"]]


@mcp.tool()
async def get_video_frames_json(
    ctx: Context, asset_id: str, count: int = 6, size: str = "thumbnail",
    start: float = 0.0, end: float = 0.0, interval: float = 0.0, confirm: bool = False,
) -> str:
    """Frames of a video as base64 JPEG with timestamps, for HTML galleries and
    skills. Same parameters, gate (confirm above 12) and cap (120) as get_video_frames. Read-only.
    """ + _VIDEO_ARGS + """
    Returns: JSON {asset_id, duration, backend, count, frames:[{timestamp, data, type}]},
    a confirmation plan {confirm_required, frames_planned, estimated_tokens, ...}, or {"error": ...}.
    """
    try:
        result, gate = await _video_plan(ctx, asset_id, count, size, start, end, interval, confirm)
    except video_frames.NoVideoBackend as exc:
        return json.dumps({"error": str(exc)})
    if gate is not None:
        return json.dumps(gate)
    return json.dumps(
        {"asset_id": asset_id, "duration": result["duration"], "backend": result["backend"],
         "count": len(result["frames"]), "frames": result["frames"]}
    )


# ── PDF export ──────────────────────────────────────────────

EXPORT_MAX = 500


def _duration_seconds(raw: dict) -> float:
    d = raw.get("duration")
    if isinstance(d, (int, float)):
        return float(d) / 1000.0 if d > 1000 else float(d)
    if isinstance(d, str) and ":" in d:
        h, m, s = d.split(":")
        return round(int(h) * 3600 + int(m) * 60 + float(s), 3)
    return 0.0


def _place(raw: dict) -> str:
    exif = raw.get("exifInfo") or {}
    return ", ".join(p for p in (exif.get("city"), exif.get("country")) if p)


def _summary(raw: dict) -> dict:
    return {
        "id": raw["id"], "type": raw.get("type", ""), "filename": raw.get("originalFileName", ""),
        "taken_at": raw.get("fileCreatedAt", ""), "place": _place(raw),
        "people": [p.get("name", "") for p in (raw.get("people") or []) if p.get("name")],
        "duration": _duration_seconds(raw) if raw.get("type") == "VIDEO" else None,
    }


async def _collect_assets(client, album_id: str, asset_ids: list[str], limit: int):
    """(title, raw assets, warnings). Exactly one of album_id / asset_ids."""
    if bool(album_id) == bool(asset_ids):
        raise ValueError("Pass exactly one of album_id or asset_ids.")
    limit = max(1, min(int(limit or 100), EXPORT_MAX))
    warnings: list[str] = []
    if album_id:
        album = await client.get_album(album_id)
        title = album.get("albumName") or "Immich export"
        raw = await client.get_album_assets(album_id, limit=limit + 1, with_exif=True)
    else:
        title = ""
        raw = await client.get_assets_by_ids(asset_ids[: limit + 1], with_exif=True)
    if len(raw) > limit:
        raw = raw[:limit]
        warnings.append(f"limit {limit} reached: only the first {limit} assets are included")
    if not raw:
        raise ValueError("No assets found for that album/ids.")
    return title, raw, warnings


@mcp.tool()
async def get_export_preview(ctx: Context, album_id: str = "", asset_ids: list[str] = [], limit: int = 100) -> str:
    """List what export_pdf would include (id, type, filename, date, place, people,
    video duration) so you know which assets exist before looking at images and
    writing captions. Pass exactly one of album_id / asset_ids. Read-only.

    Args:
        album_id: Album UUID, or
        asset_ids: Explicit asset UUIDs (search results, a selection).
        limit: Max assets (1-500, default 100).

    Returns: JSON {title, count, assets:[...], warnings:[...]} or {"error": ...}.
    """
    try:
        title, raw, warnings = await _collect_assets(_client(ctx), album_id, asset_ids, limit)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({"title": title, "count": len(raw), "assets": [_summary(a) for a in raw], "warnings": warnings})


# ── Shared Links ────────────────────────────────────────────


@mcp.tool()
async def list_shared_links(ctx: Context) -> str:
    """List all shared links (public gallery URLs). Use this to see what's currently
    shared publicly or to find a link ID for updates/deletion. Read-only.

    Returns: JSON with total count and links array (each with id, key, type, description, album info).
    """
    result = await _client(ctx).list_shared_links()
    links = [
        {
            "id": link["id"],
            "key": link.get("key", ""),
            "type": link.get("type", ""),
            "description": link.get("description", ""),
            "album_id": link.get("album", {}).get("id", "") if link.get("album") else "",
            "album_name": link.get("album", {}).get("albumName", "") if link.get("album") else "",
        }
        for link in result
    ]
    return json.dumps({"total": len(links), "links": links}, default=str)


@mcp.tool()
async def create_shared_link(
    ctx: Context,
    album_id: str,
    allow_download: bool = True,
    show_metadata: bool = True,
    description: str = "",
) -> str:
    """Create a public shared link for an album, making it accessible via URL without
    authentication. Use this to publish a gallery for external viewing.
    Side effect: creates a publicly accessible URL.

    Args:
        album_id: The album UUID to share publicly.
        allow_download: Allow visitors to download original files (default true).
        show_metadata: Show EXIF data to visitors (default true).
        description: Optional human-readable description for the link.

    Returns: JSON with link id, key, album_id, and the full shareable URL.
    """
    result = await _client(ctx).create_shared_link(
        album_id=album_id,
        allow_download=allow_download,
        show_metadata=show_metadata,
        description=description,
    )
    return json.dumps(
        {
            "id": result.get("id", ""),
            "key": result.get("key", ""),
            "album_id": album_id,
            "url": f"{_client(ctx).base_url}/share/{result.get('key', '')}",
        },
        default=str,
    )


@mcp.tool()
async def get_shared_link(ctx: Context, link_id: str) -> str:
    """Get full details of a shared link including permissions, expiry, and linked assets.
    Use this to inspect a specific link's configuration. Read-only.

    Args:
        link_id: The shared link's UUID (from list_shared_links).

    Returns: JSON with link details, permissions, expiry date, and associated assets/album.
    """
    try:
        result = await _client(ctx).get_shared_link(link_id)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def update_shared_link(
    ctx: Context,
    link_id: str,
    allow_download: bool | None = None,
    show_metadata: bool | None = None,
    allow_upload: bool | None = None,
    description: str | None = None,
    expiry_at: str | None = None,
) -> str:
    """Update a shared link's permissions or expiry. Use this to tighten/loosen access
    or set an expiration date. Side effect: changes public link behavior immediately.

    Args:
        link_id: The shared link's UUID.
        allow_download: Allow visitors to download original files.
        show_metadata: Show EXIF data to visitors.
        allow_upload: Allow visitors to upload photos to the shared album.
        description: Link description. Empty string clears it.
        expiry_at: ISO 8601 expiry datetime. Empty string removes expiry (link never expires).

    Returns: JSON with the updated shared link object.
    """
    fields: dict = {}
    if allow_download is not None:
        fields["allowDownload"] = allow_download
    if show_metadata is not None:
        fields["showMetadata"] = show_metadata
    if allow_upload is not None:
        fields["allowUpload"] = allow_upload
    if description is not None:
        fields["description"] = description  # empty string clears it
    if expiry_at is not None:
        fields["expiresAt"] = expiry_at if expiry_at else None  # empty string removes expiry
    if not fields:
        return json.dumps({"error": "No fields to update."})
    try:
        result = await _client(ctx).update_shared_link(link_id, **fields)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def delete_shared_link(ctx: Context, link_id: str) -> str:
    """Delete (revoke) a shared link, making the public URL immediately inaccessible.
    The album and its photos are unaffected. Side effect: permanently removes the link.

    Args:
        link_id: The shared link's UUID to delete.

    Returns: JSON with deleted confirmation and link_id.
    """
    try:
        await _client(ctx).delete_shared_link(link_id)
        return json.dumps({"deleted": True, "link_id": link_id})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def get_connection_info(ctx: Context) -> str:
    """Return the Immich base URL and a masked API key. Use this to populate gallery
    template placeholders (e.g. {{IMMICH_URL}}). The API key is intentionally masked
    for security — thumbnails use base64 data URIs, not direct API calls. Read-only.

    Returns: JSON with base_url and api_key_masked (first 8 + last 4 chars only).
    """
    client = _client(ctx)
    key = client.api_key
    masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    return json.dumps(
        {"base_url": client.base_url, "api_key_masked": masked},
        default=str,
    )


# ── People & Faces ─────────────────────────────────────────


@mcp.tool()
async def list_people(
    ctx: Context, page: int = 1, size: int = 50, with_hidden: bool = False
) -> str:
    """List all recognized people (face clusters) in the library. Use this to browse
    who appears in the photo library or find a person's ID. For searching by name,
    use search_people instead. Read-only.

    Args:
        page: Page number, starting from 1 (default 1).
        size: Results per page (default 50).
        with_hidden: Include people marked as hidden (default false).

    Returns: JSON with total count, page, and people array (each with id, name, thumbnailPath, photoCount).
    """
    result = await _client(ctx).list_people(page=page, size=size, with_hidden=with_hidden)
    people = result.get("people", [])
    total = result.get("total", len(people))
    return json.dumps({"total": total, "page": page, "people": people}, default=str)


@mcp.tool()
async def get_person(ctx: Context, person_id: str) -> str:
    """Get full details for a specific person including name, birth date, and photo count.
    Use this after finding a person via list_people or search_people. Read-only.

    Args:
        person_id: The person's UUID (from list_people or search_people).

    Returns: JSON with person details (id, name, birthDate, isHidden, photoCount, thumbnailPath).
    """
    result = await _client(ctx).get_person(person_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def update_person(
    ctx: Context,
    person_id: str,
    name: str = "",
    birth_date: str = "",
    is_hidden: bool | None = None,
    is_favorite: bool | None = None,
    feature_face_asset_id: str = "",
    color: str = "",
) -> str:
    """Update a person's profile details. Use this to name unnamed faces, set birth dates,
    hide clutter faces, or change the representative thumbnail. Only provided fields are
    modified. Side effect: changes person metadata in Immich.

    Args:
        person_id: The person's UUID.
        name: Display name (e.g. 'John Smith'). Set to name unnamed face clusters.
        birth_date: ISO date (e.g. '1990-05-15').
        is_hidden: Hide from the People view (useful for strangers/clutter).
        is_favorite: Mark as a favorite person.
        feature_face_asset_id: Asset UUID whose face crop becomes the person's thumbnail.
        color: Hex color label for UI grouping.

    Returns: JSON with the updated person object.
    """
    fields: dict = {}
    if name:
        fields["name"] = name
    if birth_date:
        fields["birthDate"] = birth_date
    if is_hidden is not None:
        fields["isHidden"] = is_hidden
    if is_favorite is not None:
        fields["isFavorite"] = is_favorite
    if feature_face_asset_id:
        fields["featureFaceAssetId"] = feature_face_asset_id
    if color:
        fields["color"] = color
    if not fields:
        return json.dumps({"error": "No fields to update. Provide at least one field."})
    result = await _client(ctx).update_person(person_id, **fields)
    return json.dumps(result, default=str)


@mcp.tool()
async def merge_people(ctx: Context, person_id: str, merge_ids: list[str]) -> str:
    """Merge multiple person clusters into one. Use this when the same real person has
    been split into multiple face clusters. DESTRUCTIVE and IRREVERSIBLE: merged persons
    are permanently deleted and all their faces transfer to the target.

    Args:
        person_id: The target person UUID to keep (receives all merged faces).
        merge_ids: List of person UUIDs to absorb into the target. These persons are permanently deleted.

    Returns: JSON with merge result details.
    """
    result = await _client(ctx).merge_people(person_id, merge_ids)
    return json.dumps(result, default=str)


@mcp.tool()
async def search_people(ctx: Context, name: str, with_hidden: bool = False) -> str:
    """Search for people by name (partial match). Use this when you know the person's
    name. For browsing all people, use list_people instead. Read-only.

    Args:
        name: Full or partial name to match (case-insensitive).
        with_hidden: Include hidden people in results (default false).

    Returns: JSON array of matching people with id, name, and photo count.
    """
    result = await _client(ctx).search_people(name, with_hidden=with_hidden)
    return json.dumps(result, default=str)


@mcp.tool()
async def get_person_thumbnail(ctx: Context, person_id: str) -> str:
    """Get a base64-encoded face crop thumbnail for a person. Use this to visually
    identify a person before merging or renaming. Read-only.

    Args:
        person_id: The person's UUID.

    Returns: JSON with 'data' (base64 string of face crop) and 'type' (MIME type).
    """
    result = await _client(ctx).get_person_thumbnail(person_id)
    return json.dumps(result)


@mcp.tool()
async def get_asset_faces(ctx: Context, asset_id: str) -> str:
    """Get all detected faces in a photo with their person assignments. Use this to see
    who is in a specific photo or to find face IDs for reassign_face. Read-only.

    Args:
        asset_id: The asset's UUID.

    Returns: JSON array of face detections (each with face_id, person_id, person_name, bounding box).
    """
    result = await _client(ctx).get_asset_faces(asset_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def reassign_face(ctx: Context, face_id: str, person_id: str) -> str:
    """Reassign a detected face to a different person. Use this to correct face recognition
    mistakes (e.g. a face wrongly attributed to Person A should be Person B). Get face_id
    from get_asset_faces first. Side effect: permanently changes face-to-person mapping.

    Args:
        face_id: The face detection UUID (from get_asset_faces results).
        person_id: The correct person UUID to assign this face to.

    Returns: JSON with the updated face assignment.
    """
    result = await _client(ctx).reassign_face(face_id, person_id)
    return json.dumps(result, default=str)


# ── Trash ──────────────────────────────────────────────────


@mcp.tool()
async def delete_assets(ctx: Context, asset_ids: list[str], force: bool = False) -> str:
    """Delete assets (soft-delete to trash or permanent). Use this to remove unwanted
    photos/videos. Default is soft-delete (recoverable via restore_assets). With force=true,
    deletion is PERMANENT and IRREVERSIBLE. Side effect: moves/deletes assets.

    Args:
        asset_ids: List of asset UUIDs to delete.
        force: false (default) = move to trash (recoverable). true = PERMANENTLY delete (no undo).

    Returns: JSON with count deleted and whether force was used.
    """
    await _client(ctx).delete_assets(asset_ids, force=force)
    return json.dumps({
        "deleted": len(asset_ids),
        "force": force,
        "warning": "Assets permanently deleted." if force else "Assets moved to trash. Use restore_assets to undo.",
    })


@mcp.tool()
async def empty_trash(ctx: Context) -> str:
    """Permanently delete ALL assets currently in trash. DESTRUCTIVE and IRREVERSIBLE.
    Use this only after confirming the user wants to purge all trashed items. For
    deleting specific assets, use delete_assets instead. Side effect: permanently
    destroys all trashed assets and frees storage.

    Returns: JSON with success confirmation.
    """
    await _client(ctx).empty_trash()
    return json.dumps({"success": True, "warning": "All trashed assets have been permanently deleted."})


@mcp.tool()
async def restore_trash(ctx: Context) -> str:
    """Restore ALL trashed assets back to the library. Use this to undo an accidental
    bulk deletion. For restoring specific assets only, use restore_assets instead.
    Side effect: moves all trashed assets back to the active library.

    Returns: JSON with success confirmation.
    """
    await _client(ctx).restore_trash()
    return json.dumps({"success": True, "message": "All trashed assets have been restored."})


@mcp.tool()
async def restore_assets(ctx: Context, asset_ids: list[str]) -> str:
    """Restore specific assets from trash back to the active library. Use this to
    selectively recover accidentally deleted photos. For restoring everything at once,
    use restore_trash instead. Side effect: moves specified assets out of trash.

    Args:
        asset_ids: List of asset UUIDs currently in trash to restore.

    Returns: JSON with count of restored assets.
    """
    await _client(ctx).restore_assets(asset_ids)
    return json.dumps({"restored": len(asset_ids)})


# ── Duplicates ─────────────────────────────────────────────


@mcp.tool()
async def get_duplicates(ctx: Context, album_id: str = "") -> str:
    """Get ML-detected duplicate asset groups (same image stored more than once). Use this
    to review potential duplicates before resolving them with resolve_duplicates. Requires
    Immich ML service. Note: "duplicates" means the same picture, not the same person —
    for people use get_album (assets[].people) or get_asset_faces. Read-only.

    Args:
        album_id: Optional. Restrict to groups that touch this album; each group then also
            reports which of its assets are inside/outside the album.

    Returns: JSON array of duplicate groups (each with duplicateId, assets array, and similarity scores).
    """
    client = _client(ctx)
    groups = await client.get_duplicates()
    if not album_id:
        return json.dumps(groups, default=str)
    album = await client.get_album(album_id)
    in_album = {a["id"] for a in await _album_assets(client, album_id, album)}
    out = []
    for g in groups:
        ids = [a["id"] for a in g.get("assets", [])]
        inside = [i for i in ids if i in in_album]
        if inside:
            out.append({**g, "inAlbum": inside, "outsideAlbum": [i for i in ids if i not in in_album]})
    return json.dumps(
        {"albumId": album_id, "albumName": album.get("albumName", ""), "groups": out,
         "note": "Groups fully inside the album have an empty outsideAlbum list."},
        default=str,
    )


@mcp.tool()
async def resolve_duplicates(ctx: Context, groups: list[dict]) -> str:
    """Resolve duplicate groups by choosing which assets to keep and which to trash.
    Use this after reviewing results from get_duplicates. Trashed assets can still be
    recovered via restore_assets. Side effect: moves rejected duplicates to trash.

    Args:
        groups: List of dicts, each with: duplicateId (from get_duplicates), assetIds (UUIDs to KEEP), trashIds (UUIDs to TRASH).

    Returns: JSON with count of resolved groups.
    """
    await _client(ctx).resolve_duplicates(groups)
    return json.dumps({
        "resolved": len(groups),
        "message": "Duplicate groups resolved. Trashed assets can be restored from trash.",
    })


# ── Tags ──────────────────────────────────────────────────


@mcp.tool()
async def list_tags(ctx: Context) -> str:
    """List all tags in the library. Use this to discover existing tags before creating
    new ones or to find a tag ID for tagging operations. Read-only.

    Returns: JSON with total count and tags array (each with id, name, color).
    """
    try:
        result = await _client(ctx).list_tags()
        return json.dumps({"total": len(result), "tags": result}, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def get_tag(ctx: Context, tag_id: str) -> str:
    """Get details for a specific tag. Use this to inspect a tag's properties. Read-only.

    Args:
        tag_id: The tag's UUID (from list_tags).

    Returns: JSON with tag id, name, color, and usage count.
    """
    try:
        result = await _client(ctx).get_tag(tag_id)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def create_tag(ctx: Context, name: str, color: str = "") -> str:
    """Create a new tag for categorizing assets. Use list_tags first to avoid duplicates.
    Side effect: creates a new tag in Immich.

    Args:
        name: Tag display name (e.g. 'Vacation', 'Family', 'Work'). Must be unique.
        color: Optional hex color for the tag (e.g. '#FF5733').

    Returns: JSON with the new tag's id, name, and color.
    """
    try:
        result = await _client(ctx).create_tag(name, color=color or None)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def update_tag(ctx: Context, tag_id: str, name: str | None = None, color: str | None = None) -> str:
    """Update a tag's color. Side effect: changes apply to all assets using this tag.
    Immich's API cannot rename a tag (TagUpdateDto only carries `color`); to rename,
    create_tag with the new name, tag_assets, then delete_tag the old one.

    Args:
        tag_id: The tag's UUID.
        name: Not supported by Immich — passing it returns an error explaining the workaround.
        color: New hex color (e.g. '#FF5733'). Omit to keep current.

    Returns: JSON with the updated tag object.
    """
    if name is not None:
        return json.dumps({
            "error": "Immich's API cannot rename a tag (only its color can change). "
                     "To rename: create_tag with the new name, tag_assets the same assets, "
                     "then delete_tag the old tag."
        })
    fields: dict = {}
    if color is not None:
        fields["color"] = color
    if not fields:
        return json.dumps({"error": "No fields to update. Provide color."})
    try:
        result = await _client(ctx).update_tag(tag_id, **fields)
        return json.dumps(result, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def delete_tag(ctx: Context, tag_id: str) -> str:
    """Delete a tag and remove it from all assets. The assets themselves are unaffected.
    Side effect: permanently deletes the tag (cannot be undone).

    Args:
        tag_id: The tag's UUID to delete.

    Returns: JSON with deleted confirmation and tag_id.
    """
    try:
        await _client(ctx).delete_tag(tag_id)
        return json.dumps({"deleted": True, "tag_id": tag_id})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def tag_assets(ctx: Context, tag_id: str, asset_ids: list[str]) -> str:
    """Apply a tag to multiple assets at once. Use this to bulk-categorize photos
    (e.g. tag all vacation photos). Side effect: adds tag association to assets.

    Args:
        tag_id: The tag UUID to apply (from list_tags or create_tag).
        asset_ids: List of asset UUIDs to tag. Must not be empty.

    Returns: JSON with tag_id, count tagged, and per-asset results.
    """
    if not asset_ids:
        return json.dumps({"error": "asset_ids cannot be empty."})
    try:
        result = await _client(ctx).tag_assets(tag_id, asset_ids)
        return json.dumps({"tag_id": tag_id, "tagged": len(asset_ids), "result": result}, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


@mcp.tool()
async def untag_assets(ctx: Context, tag_id: str, asset_ids: list[str]) -> str:
    """Remove a tag from multiple assets. The tag itself remains; only the association is
    removed. Side effect: removes tag-to-asset links.

    Args:
        tag_id: The tag UUID to remove from assets.
        asset_ids: List of asset UUIDs to untag. Must not be empty.

    Returns: JSON with tag_id, count untagged, and per-asset results.
    """
    if not asset_ids:
        return json.dumps({"error": "asset_ids cannot be empty."})
    try:
        result = await _client(ctx).untag_assets(tag_id, asset_ids)
        return json.dumps({"tag_id": tag_id, "untagged": len(asset_ids), "result": result}, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


# ── Upload ─────────────────────────────────────────────────


ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".mp4", ".mov", ".gif", ".webp"}
MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25MB


@mcp.tool()
async def upload_asset(ctx: Context, file_path: str, album_id: str = "") -> str:
    """Upload a local photo or video file to Immich. Use this to ingest new media into
    the library. Constraints: max 25MB, allowed types: jpg, jpeg, png, heic, mp4, mov,
    gif, webp. Symlinks are rejected for security. The original file is NOT modified or
    deleted. Side effect: creates a new asset in Immich.

    Args:
        file_path: Absolute path to the local file (e.g. '/tmp/photo.jpg'). Must exist.
        album_id: Optional album UUID to add the uploaded asset to immediately.

    Returns: JSON with new asset id, filename, size_mb, and album assignment status if applicable.
    """
    import os

    if not os.path.isfile(file_path):
        return json.dumps({"error": f"File not found: {file_path}"})

    # Resolve symlinks and verify real path
    real_path = os.path.realpath(file_path)
    if real_path != file_path and os.path.islink(file_path):
        return json.dumps({"error": "Symlinks are not allowed for security."})
    file_path = real_path

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return json.dumps({"error": f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"})

    size = os.path.getsize(file_path)
    if size > MAX_UPLOAD_SIZE:
        return json.dumps({"error": f"File too large: {size / 1024 / 1024:.1f}MB. Max: 25MB."})

    client = _client(ctx)
    try:
        result = await client.upload_asset(file_path)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})

    if album_id and result.get("id"):
        try:
            await client.add_assets_to_album(album_id, [result["id"]])
            result["added_to_album"] = album_id
        except Exception as e:
            result["album_error"] = str(e)

    result["uploaded_file"] = os.path.basename(file_path)
    result["size_mb"] = round(size / 1024 / 1024, 2)
    return json.dumps(result, default=str)


# ── Asset List ─────────────────────────────────────────────


@mcp.tool()
async def list_assets(
    ctx: Context,
    is_favorite: bool | None = None,
    is_archived: bool | None = None,
    is_trashed: bool | None = None,
    asset_type: str = "",
    page: int = 1,
    size: int = 50,
) -> str:
    """List assets with simple filters (no search query needed). Use this to browse
    the library by status (favorites, archived, trashed) or type. For finding specific
    content, use search_metadata (structured) or search_smart (visual AI). Read-only.

    Args:
        is_favorite: true = only favorites, false = only non-favorites, omit = all.
        is_archived: true = only archived, false = only non-archived, omit = all.
        is_trashed: true = only trashed items; false/omit = active library (Immich never mixes both).
        asset_type: 'IMAGE' or 'VIDEO'. Omit for both.
        page: Page number, starting from 1 (default 1).
        size: Results per page (1-200, default 50).

    Returns: JSON with total count, current page, and assets array with IDs, filenames, dates, and types.
    """
    try:
        result = await _client(ctx).list_assets(
            is_favorite=is_favorite,
            is_archived=is_archived,
            is_trashed=is_trashed,
            asset_type=asset_type or None,
            page=page,
            size=min(size, 200),
        )
        assets = result.get("assets", {}).get("items", [])
        total = result.get("assets", {}).get("total", 0)
        return json.dumps({"total": total, "page": page, "assets": assets}, default=str)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Immich API error: {e.response.status_code}", "detail": e.response.text[:200]})


# ── HTTP App (for Streamable HTTP transport) ────────────────

app = mcp.streamable_http_app()

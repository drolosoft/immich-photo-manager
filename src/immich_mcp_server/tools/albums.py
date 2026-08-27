"""Albums: list, read (with assets and people), create, update, delete, add and remove assets.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

from mcp.server.fastmcp import Context

from ..app import mcp, _client
from ._common import _album_assets

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
            "id": album["id"],
            "albumName": album.get("albumName", ""),
            "description": album.get("description", ""),
            "assetCount": album.get("assetCount", 0),
            "shared": album.get("shared", False),
            "hasSharedLink": album.get("hasSharedLink", False),
            "createdAt": album.get("createdAt", ""),
        }
        for album in result
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
            "asset_ids": [asset["id"] for asset in assets],
            "assets": [
                {
                    "id": asset["id"],
                    "originalFileName": asset.get("originalFileName", ""),
                    "type": asset.get("type", ""),
                    "fileCreatedAt": asset.get("fileCreatedAt", ""),
                    "people": [
                        {"id": person.get("id"), "name": person.get("name") or ""}
                        for person in (asset.get("people") or [])
                    ],
                }
                for asset in assets
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

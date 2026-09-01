"""Shared links: list, create, read, update, delete; plus the connection info used by galleries.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

import httpx
from mcp.server.mcpserver import Context

from ..app import mcp, _client
from ._common import _api_error

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
    except httpx.HTTPStatusError as exc:
        return _api_error(exc)


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
    except httpx.HTTPStatusError as exc:
        return _api_error(exc)


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
    except httpx.HTTPStatusError as exc:
        return _api_error(exc)


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

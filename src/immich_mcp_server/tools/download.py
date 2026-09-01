"""Download archive: an album or a selection as one zip on disk.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json
import os

from mcp.server.mcpserver import Context

from ..app import mcp, _client
from ._common import _album_assets


@mcp.tool()
async def get_download_info(
    ctx: Context,
    album_id: str = "",
    asset_ids: list[str] | None = None,
) -> str:
    """How big the zip of an album or selection would be, BEFORE building it.
    Use this to warn the user about the size (originals and videos add up fast)
    and then decide whether to call download_archive. Read-only.

    Args:
        album_id: Size the whole album.
        asset_ids: Or size just these assets.

    Returns: JSON with total_size_mb, asset_count and the number of archives
    Immich would split the download into.
    """
    result = await _client(ctx).get_download_info(
        album_id=album_id or None,
        asset_ids=asset_ids or None,
    )

    archives = result.get("archives") or []
    asset_count = sum(len(archive.get("assetIds") or []) for archive in archives)
    return json.dumps({
        "total_size_mb": round((result.get("totalSize") or 0) / 1024 / 1024, 2),
        "asset_count": asset_count,
        "archives": len(archives),
    })


@mcp.tool()
async def download_archive(
    ctx: Context,
    output_path: str,
    album_id: str = "",
    asset_ids: list[str] | None = None,
) -> str:
    """Download an album or a selection as one zip of the original files, written
    to a local path. Use get_download_info first when the size matters. The file
    is streamed to disk (safe for big albums) and an existing file is never
    overwritten. Side effect: writes a file on the machine running the server.

    Args:
        output_path: Where to write the zip (an existing file is refused).
        album_id: Download the whole album.
        asset_ids: Or download just these assets.

    Returns: JSON with path and bytes written, or an error.
    """
    if not album_id and not asset_ids:
        return json.dumps({"error": "Pass album_id or asset_ids — nothing to download."})

    if os.path.exists(output_path):
        return json.dumps({"error": f"{output_path} already exists — pick another path.",
                           "path": output_path})

    # An album is downloaded by its resolved asset list, the same list every
    # other album tool works from (survives the Immich 3.x album-assets change).
    ids = list(asset_ids or [])
    if album_id:
        album = await _client(ctx).get_album(album_id)
        assets = await _album_assets(_client(ctx), album_id, album)
        ids.extend(asset.get("id") for asset in assets)

    written = await _client(ctx).download_archive(ids, output_path)
    return json.dumps({"path": output_path, "bytes": written, "assets": len(ids)})

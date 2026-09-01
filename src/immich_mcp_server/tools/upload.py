"""Upload a local file into the library.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

import httpx
from mcp.server.mcpserver import Context

from ..app import mcp, _client
from ._common import _api_error

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
    except httpx.HTTPStatusError as exc:
        return _api_error(exc)

    if album_id and result.get("id"):
        try:
            await client.add_assets_to_album(album_id, [result["id"]])
            result["added_to_album"] = album_id
        except Exception as exc:
            result["album_error"] = str(exc)

    result["uploaded_file"] = os.path.basename(file_path)
    result["size_mb"] = round(size / 1024 / 1024, 2)
    return json.dumps(result, default=str)

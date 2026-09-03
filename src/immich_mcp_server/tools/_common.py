"""Helpers shared by several tool modules: album contents across Immich versions,
base64 thumbnail entries to MCP image blocks, the JSON shape of an Immich API error."""

import base64
import json

import httpx
from mcp.server.mcpserver import Image


def _api_error(exc: httpx.HTTPStatusError) -> str:
    """The JSON a tool returns when Immich answers with an HTTP error status.

    The status code tells the model what happened (404 unknown id, 403 a key
    without that permission); the first 200 characters of the body carry
    Immich's own message without flooding the context.
    """
    return json.dumps({
        "error": f"Immich API error: {exc.response.status_code}",
        "detail": exc.response.text[:200],
    })


async def _album_assets(client, album_id: str) -> list[dict]:
    """Album assets across Immich versions, always via POST /search/metadata
    (albumIds, withPeople). Immich >= 3.0 no longer inlines `assets` in the album,
    and the inline list on 2.x lacks recognized people, so the search path is the
    only one that is both version-independent and complete."""
    return await client.get_album_assets(album_id)


#
# These tools return MCP image blocks (ImageContent) for clients that render
# images inline — e.g. Open WebUI, Claude Desktop. They are an alternative view
# of the same thumbnails; the get_*_thumbnail(s) tools in `thumbnails.py` remain the default
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

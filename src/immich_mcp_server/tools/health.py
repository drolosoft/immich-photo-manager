"""Health and library statistics: ping, server version, counts.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

import httpx
from mcp.server.mcpserver import Context

from ..app import mcp, _client

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
async def get_capabilities(ctx: Context) -> str:
    """What this Immich server can do: version, feature flags and known quirks.
    Use this once at the start of a session to learn whether OCR, smart search or
    facial recognition are available before offering them, and which behaviours
    differ between Immich 2.x and 3.x. Read-only.

    Returns: JSON with server_version, immich_major, features (the server's own
    flags: ocr, smartSearch, facialRecognition, map, trash...) and quirks (plain
    sentences about version-specific behaviour the caller should know). When the
    API key may not read the feature flags, features is empty and a note says so;
    the version and the quirks still come back.
    """
    version = await _client(ctx).get_server_version()

    # A scoped key can read the version and still be refused the feature flags.
    # Half an answer beats none, so the refusal becomes a note beside the version.
    features_note = ""
    try:
        features = await _client(ctx).get_server_features()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 403:
            raise
        features = {}
        features_note = (
            "This API key cannot read the server feature flags (403), so whether "
            "OCR, smart search or facial recognition are enabled is unknown here. "
            "Everything else in this answer is accurate."
        )

    major = version.get("major", 0)
    version_string = "%s.%s.%s" % (
        version.get("major"), version.get("minor"), version.get("patch"))

    # Behaviour verified live on 2.7.5 and 3.1.0 — these are Immich facts the
    # model cannot discover from the feature flags alone.
    quirks = [
        "The edits API (rotate_assets, revert_asset_edits) applies to images only.",
        "Tags can change color but never be renamed.",
        "Videos expose a single thumbnail; use get_video_frames for more moments.",
    ]
    if major >= 3:
        quirks.append(
            "Fetching an album does not include its assets; the plugin already "
            "works around this, so album tools behave normally.")
        quirks.append(
            "list_people hides people below a face-count threshold; the total "
            "still counts them.")
    else:
        quirks.append(
            "Searching by asset ids is ignored by this server; the plugin "
            "falls back to fetching each asset individually.")

    capabilities = {
        "server_version": version_string,
        "immich_major": major,
        "features": features,
        "quirks": quirks,
    }
    if features_note:
        capabilities["features_note"] = features_note
    return json.dumps(capabilities)


@mcp.tool()
async def get_statistics(ctx: Context) -> str:
    """Get library statistics. Use this for a quick overview of library size
    without listing individual assets. Read-only.

    Returns: JSON with total photo count, video count, and storage usage in bytes.
    """
    result = await _client(ctx).get_statistics()
    return json.dumps(result)

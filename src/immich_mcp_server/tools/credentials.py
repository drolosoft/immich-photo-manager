"""Connection credentials: validate a new URL/API key, hot-swap the live client, persist it.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

import httpx
from mcp.server.mcpserver import Context

from ..app import mcp
from ..immich_client import ImmichClient

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
    except Exception as exc:
        return json.dumps({
            "success": False,
            "error": f"Invalid credentials: {exc}",
        })

    # 2. Verify the new credentials actually work. /server/ping is public and
    # would accept any key; verify_access() needs the key to be honoured.
    try:
        await new_client.verify_access()
    except httpx.HTTPStatusError as exc:
        return json.dumps({
            "success": False,
            "error": (
                f"Immich at {base_url} rejected the API key "
                f"(HTTP {exc.response.status_code}). Check the API key is correct."
            ),
        })
    except Exception as exc:
        return json.dumps({
            "success": False,
            "error": (
                f"Could not connect to Immich at {base_url}: {exc}. "
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

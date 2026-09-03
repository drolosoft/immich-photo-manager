"""Memories: list, create, update and delete "on this day" collections.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import json

from mcp.server.mcpserver import Context

from ..app import mcp, _client


def _trim_memory(memory: dict) -> dict:
    """The API answers with full asset objects; the model only needs the essentials."""
    assets = memory.get("assets") or []
    return {
        "id": memory.get("id"),
        "type": memory.get("type"),
        "memory_at": memory.get("memoryAt"),
        "year": (memory.get("data") or {}).get("year"),
        "is_saved": memory.get("isSaved"),
        "asset_count": len(assets),
        "assets": [
            {
                "asset_id": asset.get("id"),
                "filename": asset.get("originalFileName"),
                "date": asset.get("fileCreatedAt"),
            }
            for asset in assets
        ],
    }


@mcp.tool()
async def list_memories(
    ctx: Context,
    for_date: str = "",
    is_saved: bool | None = None,
    size: int = 50,
) -> str:
    """List memories — Immich's "on this day" collections of photos from past years.
    Use this to build a 'tal día como hoy' story, album or PDF: each memory carries
    the year it looks back to and the assets Immich picked for it. Read-only.

    Args:
        for_date: ISO date — return the memories Immich shows on that day
            (e.g. today for the classic on-this-day feed). Omit for all memories.
        is_saved: If true, only memories the user saved; if false, only unsaved.
        size: Maximum memories to return (default 50).

    Returns: JSON with total and a memories array; each has id, type, memory_at,
    the year it remembers, is_saved, asset_count and a trimmed assets list
    (id, filename, date).
    """
    result = await _client(ctx).list_memories(
        for_date=for_date or None,
        is_saved=is_saved,
        size=size,
    )
    memories = [_trim_memory(memory) for memory in result]
    return json.dumps({"total": len(memories), "memories": memories}, default=str)


@mcp.tool()
async def create_memory(
    ctx: Context,
    memory_at: str,
    year: int,
    asset_ids: list[str] | None = None,
) -> str:
    """Create an "on this day" memory from chosen assets. Use this after curating
    a set of photos from the same past date (e.g. via search_metadata with a date
    range) to make them show up in Immich's memories feed. Side effect: creates
    a memory on the server.

    Args:
        memory_at: ISO date the memory is shown on (usually today's month and day).
        year: The past year the memory looks back to (required by Immich).
        asset_ids: Assets to include. May be empty, but an empty memory shows nothing.

    Returns: JSON with the created memory's id, type, memory_at, the year it
    remembers, is_saved, asset_count and a trimmed assets list (id, filename, date).
    """
    result = await _client(ctx).create_memory(
        memory_at=memory_at,
        year=year,
        asset_ids=asset_ids or None,
    )
    return json.dumps(_trim_memory(result), default=str)


@mcp.tool()
async def update_memory(
    ctx: Context,
    memory_id: str,
    is_saved: bool | None = None,
    memory_at: str = "",
    seen_at: str = "",
) -> str:
    """Update a memory: save it for later, move its date, or mark it seen.
    Side effect: modifies the memory on the server.

    Args:
        memory_id: The memory to update.
        is_saved: True to save the memory, false to unsave it.
        memory_at: New ISO date to show the memory on.
        seen_at: ISO timestamp marking when the user viewed it.

    Returns: JSON with the updated memory.
    """
    result = await _client(ctx).update_memory(
        memory_id,
        is_saved=is_saved,
        memory_at=memory_at or None,
        seen_at=seen_at or None,
    )
    return json.dumps(_trim_memory(result), default=str)


@mcp.tool()
async def delete_memory(ctx: Context, memory_id: str) -> str:
    """Delete a memory. The photos stay in the library — only the memory entry
    goes away. Side effect: removes the memory from the server.

    Args:
        memory_id: The memory to delete.

    Returns: JSON confirming the deletion.
    """
    await _client(ctx).delete_memory(memory_id)
    return json.dumps({"success": True, "deleted": memory_id})

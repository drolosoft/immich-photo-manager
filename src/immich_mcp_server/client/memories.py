"""Memories: Immich's "on this day" collections.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

from typing import Any


class MemoriesApi:
    """Memories: Immich's "on this day" collections."""

    async def list_memories(
        self,
        for_date: str | None = None,
        memory_type: str | None = None,
        is_saved: bool | None = None,
        is_trashed: bool | None = None,
        size: int | None = None,
    ) -> list:
        """List memories, optionally the ones Immich shows for a given day."""
        params: dict[str, Any] = {}
        if for_date:
            params["for"] = for_date
        if memory_type:
            params["type"] = memory_type
        if is_saved is not None:
            params["isSaved"] = is_saved
        if is_trashed is not None:
            params["isTrashed"] = is_trashed
        if size:
            params["size"] = size
        return await self._request("GET", "/memories", params=params)

    async def create_memory(
        self,
        memory_at: str,
        year: int,
        asset_ids: list[str] | None = None,
        memory_type: str = "on_this_day",
        is_saved: bool | None = None,
    ) -> dict:
        """Create a memory. `data.year` is required by both Immich majors."""
        body: dict[str, Any] = {
            "type": memory_type,
            "memoryAt": memory_at,
            "data": {"year": year},
        }
        if asset_ids:
            body["assetIds"] = asset_ids
        if is_saved is not None:
            body["isSaved"] = is_saved
        return await self._request("POST", "/memories", json=body)

    async def update_memory(
        self,
        memory_id: str,
        is_saved: bool | None = None,
        memory_at: str | None = None,
        seen_at: str | None = None,
    ) -> dict:
        """Update a memory (saved flag, date, seen timestamp)."""
        body: dict[str, Any] = {}
        if is_saved is not None:
            body["isSaved"] = is_saved
        if memory_at:
            body["memoryAt"] = memory_at
        if seen_at:
            body["seenAt"] = seen_at
        return await self._request("PUT", f"/memories/{memory_id}", json=body)

    async def delete_memory(self, memory_id: str) -> None:
        """Delete a memory (the assets stay in the library)."""
        await self._request("DELETE", f"/memories/{memory_id}")

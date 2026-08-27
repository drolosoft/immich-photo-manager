"""Trash: delete, empty, restore.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

class TrashApi:
    """Trash: delete, empty, restore."""

    async def delete_assets(self, asset_ids: list[str], force: bool = False) -> None:
        """Delete or trash assets."""
        await self._request("DELETE", "/assets", json={"ids": asset_ids, "force": force})

    async def empty_trash(self) -> None:
        """Permanently empty the trash."""
        await self._request("POST", "/trash/empty")

    async def restore_trash(self) -> None:
        """Restore all trashed assets."""
        await self._request("POST", "/trash/restore")

    async def restore_assets(self, asset_ids: list[str]) -> None:
        """Restore specific assets from trash."""
        await self._request("POST", "/trash/restore/assets", json={"ids": asset_ids})

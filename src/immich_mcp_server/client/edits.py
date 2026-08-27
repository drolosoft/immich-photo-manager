"""Non-destructive asset edits (rotate, mirror, crop).

Mixin of `ImmichClient` (see `immich_client.py`).
"""

class EditsApi:
    """Non-destructive asset edits (rotate, mirror, crop)."""

    async def apply_asset_edits(self, asset_id: str, edits: list[dict]) -> dict | None:
        """Apply non-destructive edits (rotate, mirror, crop) to an asset."""
        return await self._request(
            "PUT", f"/assets/{asset_id}/edits", json={"edits": edits}
        )

    async def get_asset_edits(self, asset_id: str) -> dict:
        """Get current edits applied to an asset."""
        return await self._request("GET", f"/assets/{asset_id}/edits")

    async def delete_asset_edits(self, asset_id: str) -> None:
        """Remove all edits from an asset (revert to original)."""
        await self._request("DELETE", f"/assets/{asset_id}/edits")

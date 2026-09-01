"""Stacks: group near-identical shots under one primary asset.

Mixin of `ImmichClient` (see `immich_client.py`).
"""


class StacksApi:
    """Stacks: group near-identical shots under one primary asset."""

    async def create_stack(self, asset_ids: list[str]) -> dict:
        """Create a stack; the first id becomes the primary (cover) asset."""
        return await self._request("POST", "/stacks", json={"assetIds": asset_ids})

    async def list_stacks(self, primary_asset_id: str | None = None) -> list:
        """All stacks, optionally the one led by a given primary asset."""
        params = {}
        if primary_asset_id:
            params["primaryAssetId"] = primary_asset_id
        return await self._request("GET", "/stacks", params=params)

    async def get_stack(self, stack_id: str) -> dict:
        """One stack with its assets."""
        return await self._request("GET", f"/stacks/{stack_id}")

    async def update_stack(self, stack_id: str, primary_asset_id: str) -> dict:
        """Change which asset fronts the stack."""
        return await self._request(
            "PUT", f"/stacks/{stack_id}", json={"primaryAssetId": primary_asset_id}
        )

    async def delete_stack(self, stack_id: str) -> None:
        """Dissolve a stack; the assets stay in the library."""
        await self._request("DELETE", f"/stacks/{stack_id}")

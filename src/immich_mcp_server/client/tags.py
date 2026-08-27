"""Tags and tagging.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

class TagsApi:
    """Tags and tagging."""

    async def list_tags(self) -> list[dict]:
        """List all tags."""
        return await self._request("GET", "/tags")

    async def get_tag(self, tag_id: str) -> dict:
        """Get tag details."""
        return await self._request("GET", f"/tags/{tag_id}")

    async def create_tag(self, name: str, color: str | None = None) -> dict:
        """Create a new tag."""
        body: dict = {"name": name}
        if color:
            body["color"] = color
        return await self._request("POST", "/tags", json=body)

    async def update_tag(self, tag_id: str, **fields) -> dict:
        """Update a tag (name, color)."""
        return await self._request("PUT", f"/tags/{tag_id}", json=fields)

    async def delete_tag(self, tag_id: str) -> None:
        """Delete a tag."""
        await self._request("DELETE", f"/tags/{tag_id}")

    async def tag_assets(self, tag_id: str, asset_ids: list[str]) -> list[dict]:
        """Add a tag to multiple assets."""
        return await self._request(
            "PUT", f"/tags/{tag_id}/assets", json={"ids": asset_ids}
        )

    async def untag_assets(self, tag_id: str, asset_ids: list[str]) -> list[dict]:
        """Remove a tag from multiple assets."""
        return await self._request(
            "DELETE", f"/tags/{tag_id}/assets", json={"ids": asset_ids}
        )

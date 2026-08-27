"""Public shared links.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

class SharingApi:
    """Public shared links."""

    async def list_shared_links(self) -> list[dict]:
        """List all shared links."""
        return await self._request("GET", "/shared-links")

    async def create_shared_link(
        self,
        album_id: str,
        allow_download: bool = True,
        show_metadata: bool = True,
        allow_upload: bool = False,
        description: str = "",
    ) -> dict:
        """Create a shared link for an album (publishes to Gallery)."""
        body = {
            "type": "ALBUM",
            "albumId": album_id,
            "allowDownload": allow_download,
            "showMetadata": show_metadata,
            "allowUpload": allow_upload,
        }
        if description:
            body["description"] = description
        return await self._request("POST", "/shared-links", json=body)

    async def delete_shared_link(self, link_id: str) -> None:
        """Delete a shared link."""
        await self._request("DELETE", f"/shared-links/{link_id}")

    async def get_shared_link(self, link_id: str) -> dict:
        """Get details of a shared link."""
        return await self._request("GET", f"/shared-links/{link_id}")

    async def update_shared_link(self, link_id: str, **fields) -> dict:
        """Update a shared link."""
        return await self._request("PATCH", f"/shared-links/{link_id}", json=fields)

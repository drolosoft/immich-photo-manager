"""Single assets: read, update, list, jobs, map markers.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

from typing import Any


class AssetsApi:
    """Single assets: read, update, list, jobs, map markers."""

    async def get_asset(self, asset_id: str) -> dict:
        """Get full metadata for a single asset."""
        return await self._request("GET", f"/assets/{asset_id}")

    async def update_asset(self, asset_id: str, **fields: Any) -> dict:
        """Update asset metadata (dates, GPS, description, etc)."""
        return await self._request("PUT", f"/assets/{asset_id}", json=fields)

    async def list_assets(
        self,
        is_favorite: bool | None = None,
        is_archived: bool | None = None,
        is_trashed: bool | None = None,
        asset_type: str | None = None,
        page: int = 1,
        size: int = 100,
    ) -> dict:
        """List assets with optional filters (uses search/metadata endpoint)."""
        body: dict[str, Any] = {"page": page, "size": size}
        if is_favorite is not None:
            body["isFavorite"] = is_favorite
        if is_archived is not None:
            body["isArchived"] = is_archived
        if is_trashed:
            # MetadataSearchDto has no `isTrashed`; trashed assets are selected by
            # including deleted rows and requiring a deletion timestamp.
            body["withDeleted"] = True
            body["trashedAfter"] = "1970-01-01T00:00:00.000Z"
        if asset_type:
            body["type"] = asset_type
        # Ensure at least one filter (Immich /search/metadata requires it)
        if len(body) == 2:  # only page and size
            body["isArchived"] = False
        return await self._request("POST", "/search/metadata", json=body)

    async def run_asset_job(self, asset_ids: list[str], name: str) -> None:
        """Queue a job for specific assets (e.g. regenerate-thumbnail)."""
        await self._request(
            "POST", "/assets/jobs", json={"name": name, "assetIds": asset_ids}
        )

    async def get_map_markers(
        self,
        is_archived: bool = False,
        is_favorite: bool | None = None,
        file_created_after: str | None = None,
        file_created_before: str | None = None,
    ) -> list[dict]:
        """Get all GPS markers from the library (for geographic discovery)."""
        params: dict[str, Any] = {"isArchived": str(is_archived).lower()}
        if is_favorite is not None:
            params["isFavorite"] = str(is_favorite).lower()
        if file_created_after:
            params["fileCreatedAfter"] = file_created_after
        if file_created_before:
            params["fileCreatedBefore"] = file_created_before
        return await self._request("GET", "/map/markers", params=params)

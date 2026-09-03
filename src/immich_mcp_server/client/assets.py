"""Single assets: read, update, list, jobs, map markers.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

from typing import Any

import httpx


class AssetsApi:
    """Single assets: read, update, list, jobs, map markers."""

    async def get_asset(self, asset_id: str) -> dict:
        """Get full metadata for a single asset."""
        return await self._request("GET", f"/assets/{asset_id}")

    async def get_asset_original(self, asset_id: str) -> dict:
        """The asset's original file, as stored (any format, full resolution).

        GET /assets/{id}/original exists on Immich 2.x and 3.x. The bytes come
        back raw, not base64: originals can be tens of megabytes.
        """
        url = f"{self.base_url}/api/assets/{asset_id}/original"
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            return {"data": response.content, "type": response.headers.get("content-type", "image/jpeg")}

    async def update_asset(self, asset_id: str, **fields: Any) -> dict:
        """Update asset metadata (dates, GPS, description, etc)."""
        return await self._request("PUT", f"/assets/{asset_id}", json=fields)

    async def update_assets_metadata(
        self,
        asset_ids: list[str],
        date_time_original: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        description: str | None = None,
        is_favorite: bool | None = None,
        rating: int | None = None,
    ) -> None:
        """One PUT /assets for many ids; only the given fields travel."""
        body: dict[str, Any] = {"ids": asset_ids}
        if date_time_original:
            body["dateTimeOriginal"] = date_time_original
        if latitude is not None:
            body["latitude"] = latitude
        if longitude is not None:
            body["longitude"] = longitude
        if description is not None:
            body["description"] = description
        if is_favorite is not None:
            body["isFavorite"] = is_favorite
        if rating is not None:
            body["rating"] = rating
        await self._request("PUT", "/assets", json=body)

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

    # ── Per-asset key-value metadata (app storage, invisible in the Immich UI) ──

    async def get_asset_metadata(self, asset_id: str) -> list[dict]:
        """Every metadata key an asset carries, from any app: [{key, value, updatedAt}]."""
        return await self._request("GET", f"/assets/{asset_id}/metadata")

    async def upsert_asset_metadata(self, asset_id: str, key: str, value: dict) -> list[dict]:
        """Create or replace one key's JSON object on an asset."""
        return await self._request(
            "PUT", f"/assets/{asset_id}/metadata", json={"items": [{"key": key, "value": value}]}
        )

    async def delete_asset_metadata(self, asset_id: str, key: str) -> None:
        """Remove one key from an asset; other apps' keys are untouched."""
        await self._request("DELETE", f"/assets/{asset_id}/metadata/{key}")

    async def reverse_geocode(self, lat: float, lon: float) -> list[dict]:
        """Resolve coordinates to city/state/country using Immich's own geodata."""
        return await self._request(
            "GET", "/map/reverse-geocode", params={"lat": lat, "lon": lon}
        )

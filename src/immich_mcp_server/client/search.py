"""Metadata search and CLIP smart search.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

from typing import Any


class SearchApi:
    """Metadata search and CLIP smart search."""

    async def search_metadata(
        self,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        make: str | None = None,
        model: str | None = None,
        taken_after: str | None = None,
        taken_before: str | None = None,
        is_favorite: bool | None = None,
        is_archived: bool | None = None,
        asset_type: str | None = None,
        ocr: str | None = None,
        page: int = 1,
        size: int = 100,
    ) -> dict:
        """Search assets by EXIF metadata (location, camera, dates)."""
        body: dict[str, Any] = {"page": page, "size": size}
        if city:
            body["city"] = city
        if state:
            body["state"] = state
        if country:
            body["country"] = country
        if make:
            body["make"] = make
        if model:
            body["model"] = model
        if taken_after:
            body["takenAfter"] = taken_after
        if taken_before:
            body["takenBefore"] = taken_before
        if is_favorite is not None:
            body["isFavorite"] = is_favorite
        if is_archived is not None:
            body["isArchived"] = is_archived
        if asset_type:
            body["type"] = asset_type
        if ocr:
            body["ocr"] = ocr
        return await self._request("POST", "/search/metadata", json=body)

    async def search_smart(
        self,
        query: str,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        taken_after: str | None = None,
        taken_before: str | None = None,
        ocr: str | None = None,
        page: int = 1,
        size: int = 100,
    ) -> dict:
        """AI-powered semantic search using CLIP (e.g. 'sunset at the beach')."""
        body: dict[str, Any] = {"query": query, "page": page, "size": size}
        if city:
            body["city"] = city
        if state:
            body["state"] = state
        if country:
            body["country"] = country
        if taken_after:
            body["takenAfter"] = taken_after
        if taken_before:
            body["takenBefore"] = taken_before
        if ocr:
            body["ocr"] = ocr
        return await self._request("POST", "/search/smart", json=body)

    async def search_explore(self) -> list:
        """Library overview grouped by explore field (cities, semantic tags)."""
        return await self._request("GET", "/search/explore")

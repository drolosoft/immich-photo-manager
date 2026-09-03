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
        person_ids: list[str] | None = None,
        tag_ids: list[str] | None = None,
        album_ids: list[str] | None = None,
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
        if person_ids:
            body["personIds"] = person_ids
        if tag_ids:
            body["tagIds"] = tag_ids
        if album_ids:
            body["albumIds"] = album_ids
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
        person_ids: list[str] | None = None,
        tag_ids: list[str] | None = None,
        album_ids: list[str] | None = None,
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
        if person_ids:
            body["personIds"] = person_ids
        if tag_ids:
            body["tagIds"] = tag_ids
        if album_ids:
            body["albumIds"] = album_ids
        return await self._request("POST", "/search/smart", json=body)

    async def search_explore(self) -> list:
        """Library overview grouped by explore field (cities, semantic tags)."""
        return await self._request("GET", "/search/explore")

    async def search_cities(self) -> list:
        """One representative asset per city with geodata."""
        return await self._request("GET", "/search/cities")

    async def search_places(self, name: str) -> list:
        """Search Immich's place gazetteer by name (no assets involved)."""
        return await self._request("GET", "/search/places", params={"name": name})

    async def search_suggestions(
        self,
        suggestion_type: str,
        country: str | None = None,
        state: str | None = None,
        make: str | None = None,
        model: str | None = None,
    ) -> list:
        """Distinct values present in the library for one field (city, camera-make...)."""
        params: dict[str, Any] = {"type": suggestion_type}
        if country:
            params["country"] = country
        if state:
            params["state"] = state
        if make:
            params["make"] = make
        if model:
            params["model"] = model
        return await self._request("GET", "/search/suggestions", params=params)

    async def search_random(
        self,
        size: int = 10,
        city: str | None = None,
        country: str | None = None,
        make: str | None = None,
        model: str | None = None,
        is_favorite: bool | None = None,
        ocr: str | None = None,
    ) -> list:
        """Random assets, optionally filtered like a metadata search."""
        body: dict[str, Any] = {"size": size}
        if city:
            body["city"] = city
        if country:
            body["country"] = country
        if make:
            body["make"] = make
        if model:
            body["model"] = model
        if is_favorite is not None:
            body["isFavorite"] = is_favorite
        if ocr:
            body["ocr"] = ocr
        return await self._request("POST", "/search/random", json=body)

    async def search_statistics(
        self,
        city: str | None = None,
        country: str | None = None,
        state: str | None = None,
        make: str | None = None,
        model: str | None = None,
        is_favorite: bool | None = None,
        ocr: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> dict:
        """Count matching assets without fetching them (`{total}`)."""
        body: dict[str, Any] = {}
        if city:
            body["city"] = city
        if country:
            body["country"] = country
        if state:
            body["state"] = state
        if make:
            body["make"] = make
        if model:
            body["model"] = model
        if is_favorite is not None:
            body["isFavorite"] = is_favorite
        if ocr:
            body["ocr"] = ocr
        if created_after:
            body["createdAfter"] = created_after
        if created_before:
            body["createdBefore"] = created_before
        return await self._request("POST", "/search/statistics", json=body)

    async def search_large_assets(
        self,
        min_file_size: int | None = None,
        size: int | None = None,
        asset_type: str | None = None,
    ) -> list:
        """Biggest assets first. Immich oddity: a POST that takes QUERY params."""
        params: dict[str, Any] = {}
        if min_file_size:
            params["minFileSize"] = min_file_size
        if size:
            params["size"] = size
        if asset_type:
            params["type"] = asset_type
        return await self._request("POST", "/search/large-assets", params=params)

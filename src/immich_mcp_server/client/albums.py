"""Albums and their contents on Immich 2.x and 3.x.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

from typing import Any

import httpx


class AlbumsApi:
    """Albums and their contents on Immich 2.x and 3.x."""

    async def list_albums(self, shared: bool | None = None) -> list[dict]:
        """List all albums."""
        params = {}
        if shared is not None:
            params["shared"] = str(shared).lower()
        return await self._request("GET", "/albums", params=params)

    async def get_album(self, album_id: str) -> dict:
        """Get album details. Immich < 3.0 also inlines `assets`; 3.0+ does not."""
        return await self._request("GET", f"/albums/{album_id}")

    async def get_album_assets(self, album_id: str, limit: int | None = None, with_exif: bool = False) -> list[dict]:
        """List the assets of an album via POST /search/metadata (albumIds).

        Works on Immich 2.x and 3.x. Immich 3.0 removed the `assets` list from
        GET /albums/{id}, so this is the only version-independent way to read
        album contents. Pages through results; stops at `limit` if given.
        `with_exif` adds EXIF data (camera, GPS, etc.) to each returned asset.
        """
        page_size = 1000 if limit is None else max(1, min(limit, 1000))
        assets: list[dict] = []
        page = 1
        while True:
            body: dict[str, Any] = {"albumIds": [album_id], "page": page, "size": page_size, "withPeople": True}
            if with_exif:
                body["withExif"] = True
            result = await self._request(
                "POST",
                "/search/metadata",
                json=body,
            )
            block = result.get("assets", {}) if isinstance(result, dict) else {}
            items = block.get("items", [])
            assets.extend(items)
            if limit is not None and len(assets) >= limit:
                return assets[:limit]
            if not items or not block.get("nextPage"):
                return assets
            page += 1

    async def get_assets_by_ids(self, ids: list[str], with_exif: bool = True) -> list[dict]:
        """Assets for explicit ids via POST /search/metadata {ids}, in the order given; unknown ids are dropped.

        `size` is capped at 1000 (the /search/metadata ceiling): pass at most 1000
        ids per call.

        Some Immich versions (e.g. 2.7.5) silently ignore the `ids` filter on
        /search/metadata and return unrelated assets instead. Any id not found in
        the response is fetched individually via GET /assets/{id} as a fallback;
        ids that genuinely don't exist (404) are dropped, same as before. Any other
        error from that fallback request (5xx, auth, etc.) is raised, not swallowed.
        """
        if not ids:
            return []
        body: dict[str, Any] = {"ids": ids, "size": min(len(ids), 1000), "withPeople": True}
        if with_exif:
            body["withExif"] = True
        result = await self._request("POST", "/search/metadata", json=body)
        items = (result.get("assets", {}) if isinstance(result, dict) else {}).get("items", [])
        by_id = {a["id"]: a for a in items if a.get("id") in ids}
        for missing_id in [i for i in ids if i not in by_id]:
            try:
                by_id[missing_id] = await self.get_asset(missing_id)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                # id doesn't exist on this server: drop it, as before
        return [by_id[i] for i in ids if i in by_id]

    async def create_album(
        self, name: str, description: str = "", asset_ids: list[str] | None = None
    ) -> dict:
        """Create a new album."""
        body: dict[str, Any] = {"albumName": name, "description": description}
        if asset_ids:
            body["assetIds"] = asset_ids
        return await self._request("POST", "/albums", json=body)

    async def update_album(
        self, album_id: str, name: str | None = None, description: str | None = None
    ) -> dict:
        """Update album name or description."""
        body: dict[str, Any] = {}
        if name:
            body["albumName"] = name
        if description is not None:
            body["description"] = description
        return await self._request("PATCH", f"/albums/{album_id}", json=body)

    async def delete_album(self, album_id: str) -> None:
        """Delete an album (does NOT delete photos)."""
        await self._request("DELETE", f"/albums/{album_id}")

    async def add_assets_to_album(self, album_id: str, asset_ids: list[str]) -> list[dict]:
        """Add assets to an album."""
        return await self._request(
            "PUT", f"/albums/{album_id}/assets", json={"ids": asset_ids}
        )

    async def remove_assets_from_album(
        self, album_id: str, asset_ids: list[str]
    ) -> list[dict]:
        """Remove assets from an album."""
        return await self._request(
            "DELETE", f"/albums/{album_id}/assets", json={"ids": asset_ids}
        )

"""Thumbnails and previews as base64.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

import base64

import httpx


class ThumbnailsApi:
    """Thumbnails and previews as base64."""

    async def get_asset_thumbnail(
        self, asset_id: str, size: str = "thumbnail", edited: bool = True
    ) -> dict:
        """Get a base64-encoded thumbnail for an asset.

        Args:
            asset_id: The asset ID.
            size: 'thumbnail' (250px) or 'preview' (1440px).
            edited: If True, return the edited version (with rotation/crop applied).

        Returns:
            dict with 'data' (base64 string) and 'type' (mime type).
        """
        # Immich 3.0+ exposes previews through the thumbnail endpoint with
        # `size=preview` (the dedicated `/preview` route no longer exists).
        if size == "preview":
            url = f"{self.base_url}/api/assets/{asset_id}/thumbnail"
            params: dict[str, str] = {"size": "preview"}
        else:
            url = f"{self.base_url}/api/assets/{asset_id}/thumbnail"
            params = {}
        if edited:
            params["edited"] = "true"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers, params=params)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/webp")
            b64 = base64.b64encode(response.content).decode("ascii")
            return {"data": b64, "type": content_type}

    async def get_album_thumbnails(
        self, album_id: str, size: str = "thumbnail", limit: int = 50
    ) -> dict:
        """Get base64 thumbnails for all assets in an album (up to limit).

        Args:
            album_id: The album ID.
            size: 'thumbnail' (250px) or 'preview' (1440px).
            limit: Max number of thumbnails to fetch.

        Returns:
            dict with album info and list of thumbnail entries.
        """
        album = await self.get_album(album_id)
        assets = album.get("assets")
        if assets is None:  # Immich >= 3.0
            assets = await self.get_album_assets(album_id, limit=limit)
        assets = assets[:limit]
        thumbnails = []
        for asset in assets:
            aid = asset["id"]
            try:
                thumb = await self.get_asset_thumbnail(aid, size)
                thumbnails.append({
                    "id": aid,
                    "data": thumb["data"],
                    "type": thumb["type"],
                    "originalFileName": asset.get("originalFileName", ""),
                    "fileCreatedAt": asset.get("fileCreatedAt", ""),
                })
            except Exception:
                # Skip assets whose thumbnails can't be fetched
                continue
        return {
            "albumId": album_id,
            "albumName": album.get("albumName", ""),
            "totalAssets": album.get("assetCount", 0),
            "fetchedCount": len(thumbnails),
            "thumbnails": thumbnails,
        }

    async def get_thumbnails_batch(
        self, asset_ids: list[str], size: str = "thumbnail", limit: int = 50
    ) -> dict:
        """Get base64 thumbnails for a list of asset IDs (no album required).

        Args:
            asset_ids: List of asset IDs to fetch thumbnails for.
            size: 'thumbnail' (250px) or 'preview' (1440px).
            limit: Max number of thumbnails to fetch.

        Returns:
            dict with list of thumbnail entries.
        """
        ids_to_fetch = asset_ids[:limit]
        thumbnails = []
        for aid in ids_to_fetch:
            try:
                thumb = await self.get_asset_thumbnail(aid, size)
                # Try to get basic asset info for filename/date
                try:
                    asset_info = await self.get_asset(aid)
                    original_name = asset_info.get("originalFileName", "")
                    created_at = asset_info.get("fileCreatedAt", "")
                except Exception:
                    original_name = ""
                    created_at = ""
                thumbnails.append({
                    "id": aid,
                    "data": thumb["data"],
                    "type": thumb["type"],
                    "originalFileName": original_name,
                    "fileCreatedAt": created_at,
                })
            except Exception:
                continue
        return {
            "totalRequested": len(ids_to_fetch),
            "fetchedCount": len(thumbnails),
            "thumbnails": thumbnails,
        }

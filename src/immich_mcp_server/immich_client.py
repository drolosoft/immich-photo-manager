"""
Immich REST API client.
Wraps the Immich API endpoints needed for photo management.
"""

import base64
import json
import os
import httpx
from pathlib import Path
from typing import Any


class ImmichClient:
    """Async HTTP client for the Immich REST API."""

    # Class-level cache dir, resolved once
    _cache_dir: str | None = None

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        # Explicit credentials always win — the config.json override only
        # applies to default construction (otherwise rotating credentials
        # would silently resurrect the old ones from disk).
        if base_url is not None or api_key is not None:
            config: dict = {}
        else:
            config = self._load_config_override()
        self.base_url = (
            base_url or config.get("base_url") or os.environ.get("IMMICH_BASE_URL", "")
        ).rstrip("/")
        self.api_key = (
            api_key or config.get("api_key") or os.environ.get("IMMICH_API_KEY", "")
        )
        if not self.base_url or not self.api_key:
            raise ValueError(
                "IMMICH_BASE_URL and IMMICH_API_KEY environment variables are required. "
                "You can also set them via the update_credentials MCP tool."
            )
        self._headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }

    # ── Config override (writable cache) ────────────────────

    @classmethod
    def _find_cache_dir(cls) -> str | None:
        """Find the writable .mcpb-cache directory.

        Resolution order:
        1. IMMICH_CACHE_DIR env var (set in mcp.json) — accepted even if
           the directory doesn't exist yet (save_config will create it).
        2. Relative to this module: ../../.mcpb-cache/
        """
        if cls._cache_dir is not None:
            return cls._cache_dir

        # 1. Explicit env var (accept path even if dir doesn't exist yet)
        env_dir = os.environ.get("IMMICH_CACHE_DIR", "")
        if env_dir:
            cls._cache_dir = os.path.realpath(env_dir)
            return cls._cache_dir

        # 2. Relative to module: src/immich_mcp_server/ -> ../../.mcpb-cache/
        module_dir = Path(__file__).resolve().parent
        cache_candidate = module_dir / ".." / ".." / ".mcpb-cache"
        # Accept even if it doesn't exist yet
        cls._cache_dir = str(cache_candidate.resolve())
        return cls._cache_dir

    @classmethod
    def _config_path(cls) -> str | None:
        """Return the path to the config override file, or None."""
        cache_dir = cls._find_cache_dir()
        if not cache_dir:
            return None
        return os.path.join(cache_dir, "config.json")

    @classmethod
    def _load_config_override(cls) -> dict:
        """Load credential overrides from .mcpb-cache/config.json if it exists."""
        config_path = cls._config_path()
        if not config_path or not os.path.exists(config_path):
            return {}
        try:
            with open(config_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    @classmethod
    def save_config(cls, base_url: str, api_key: str) -> str:
        """Save credentials to the writable cache dir.

        Creates the directory if it doesn't exist.
        Returns the path written, or raises if it cannot be created.
        """
        config_path = cls._config_path()
        if not config_path:
            raise RuntimeError(
                "No cache directory path could be determined. "
                "Cannot persist credentials."
            )
        # Create the cache directory if it doesn't exist
        cache_dir = os.path.dirname(config_path)
        os.makedirs(cache_dir, exist_ok=True)
        config = {"base_url": base_url, "api_key": api_key}
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        os.chmod(config_path, 0o600)
        return config_path

    # ── HTTP ────────────────────────────────────────────────

    async def _request(
        self, method: str, path: str, json: dict | None = None, params: dict | None = None
    ) -> Any:
        """Make an authenticated request to the Immich API."""
        url = f"{self.base_url}/api{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method, url, headers=self._headers, json=json, params=params
            )
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()

    # ── Health ──────────────────────────────────────────────

    async def ping(self) -> dict:
        """Check server connectivity (unauthenticated endpoint)."""
        return await self._request("GET", "/server/ping")

    async def verify_access(self) -> None:
        """Prove the API key is accepted. /server/ping is public, so it cannot
        validate credentials; /users/me (permission user.read) can. A scoped key
        without that permission answers 403, which still proves the key is valid.
        Raises httpx.HTTPStatusError on 401 and on network errors."""
        try:
            await self._request("GET", "/users/me")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return
            raise

    async def get_server_version(self) -> dict:
        """Get Immich server version."""
        return await self._request("GET", "/server/version")

    async def get_statistics(self) -> dict:
        """Get library statistics (photos, videos, storage)."""
        return await self._request("GET", "/server/statistics")

    # ── Assets ──────────────────────────────────────────────

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

    # ── Search ──────────────────────────────────────────────

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
        return await self._request("POST", "/search/metadata", json=body)

    async def search_smart(
        self,
        query: str,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        taken_after: str | None = None,
        taken_before: str | None = None,
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
        return await self._request("POST", "/search/smart", json=body)

    # ── Albums ──────────────────────────────────────────────

    async def list_albums(self, shared: bool | None = None) -> list[dict]:
        """List all albums."""
        params = {}
        if shared is not None:
            params["shared"] = str(shared).lower()
        return await self._request("GET", "/albums", params=params)

    async def get_album(self, album_id: str) -> dict:
        """Get album details. Immich < 3.0 also inlines `assets`; 3.0+ does not."""
        return await self._request("GET", f"/albums/{album_id}")

    async def get_album_assets(self, album_id: str, limit: int | None = None) -> list[dict]:
        """List the assets of an album via POST /search/metadata (albumIds).

        Works on Immich 2.x and 3.x. Immich 3.0 removed the `assets` list from
        GET /albums/{id}, so this is the only version-independent way to read
        album contents. Pages through results; stops at `limit` if given.
        """
        page_size = 1000 if limit is None else max(1, min(limit, 1000))
        assets: list[dict] = []
        page = 1
        while True:
            result = await self._request(
                "POST",
                "/search/metadata",
                json={"albumIds": [album_id], "page": page, "size": page_size, "withPeople": True},
            )
            block = result.get("assets", {}) if isinstance(result, dict) else {}
            items = block.get("items", [])
            assets.extend(items)
            if limit is not None and len(assets) >= limit:
                return assets[:limit]
            if not items or not block.get("nextPage"):
                return assets
            page += 1

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

    # ── Thumbnails ──────────────────────────────────────────

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

    # ── Shared Links ────────────────────────────────────────

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

    # ── People & Faces ─────────────────────────────────────

    async def list_people(
        self, page: int = 1, size: int = 50, with_hidden: bool = False
    ) -> dict:
        """List all people (paginated)."""
        params = {"page": str(page), "size": str(size), "withHidden": str(with_hidden).lower()}
        return await self._request("GET", "/people", params=params)

    async def get_person(self, person_id: str) -> dict:
        """Get a person's details."""
        return await self._request("GET", f"/people/{person_id}")

    async def update_person(self, person_id: str, **fields) -> dict:
        """Update a person (name, birthDate, isHidden, etc)."""
        return await self._request("PUT", f"/people/{person_id}", json=fields)

    async def merge_people(self, person_id: str, merge_ids: list[str]) -> dict:
        """Merge multiple people into one."""
        return await self._request(
            "POST", f"/people/{person_id}/merge", json={"ids": merge_ids}
        )

    async def get_person_statistics(self, person_id: str) -> dict:
        """Get asset count for a person."""
        return await self._request("GET", f"/people/{person_id}/statistics")

    async def search_people(self, name: str, with_hidden: bool = False) -> list[dict]:
        """Search people by name."""
        params = {"name": name, "withHidden": str(with_hidden).lower()}
        return await self._request("GET", "/search/person", params=params)

    async def get_person_thumbnail(self, person_id: str) -> dict:
        """Get a base64-encoded face thumbnail for a person."""
        url = f"{self.base_url}/api/people/{person_id}/thumbnail"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/jpeg")
            b64 = base64.b64encode(response.content).decode("ascii")
            return {"data": b64, "type": content_type}

    async def get_asset_faces(self, asset_id: str) -> list[dict]:
        """Get all detected faces for an asset."""
        return await self._request("GET", "/faces", params={"id": asset_id})

    async def reassign_face(self, face_id: str, person_id: str) -> dict:
        """Reassign a face to a different person.

        Immich's PUT /faces/{id} takes the *person* id in the path and the *face*
        id in the body (FaceDto.id = "Face ID"); the reverse silently does nothing.
        """
        return await self._request("PUT", f"/faces/{person_id}", json={"id": face_id})

    # ── Asset Edits (rotate, mirror, crop) ───────────────────

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

    # ── Trash ──────────────────────────────────────────────

    async def delete_assets(self, asset_ids: list[str], force: bool = False) -> None:
        """Delete or trash assets."""
        await self._request("DELETE", "/assets", json={"ids": asset_ids, "force": force})

    async def empty_trash(self) -> None:
        """Permanently empty the trash."""
        await self._request("POST", "/trash/empty")

    async def restore_trash(self) -> None:
        """Restore all trashed assets."""
        await self._request("POST", "/trash/restore")

    async def restore_assets(self, asset_ids: list[str]) -> None:
        """Restore specific assets from trash."""
        await self._request("POST", "/trash/restore/assets", json={"ids": asset_ids})

    # ── Duplicates ─────────────────────────────────────────

    async def get_duplicates(self) -> list[dict]:
        """Get all detected duplicate groups."""
        return await self._request("GET", "/duplicates")

    async def resolve_duplicates(self, groups: list[dict]) -> None:
        """Resolve duplicate groups (keep/trash decisions).

        Immich >= 2.6 exposes POST /duplicates/resolve with
        {"groups": [{"duplicateId", "keepAssetIds", "trashAssetIds"}]}. Older
        servers (404) get the equivalent: trash the rejected assets and clear the
        duplicate flag. Accepts the legacy keys assetIds/trashIds too.
        """
        normalized = [
            {
                "duplicateId": g.get("duplicateId"),
                "keepAssetIds": list(g.get("keepAssetIds") or g.get("assetIds") or []),
                "trashAssetIds": list(g.get("trashAssetIds") or g.get("trashIds") or []),
            }
            for g in groups
        ]
        try:
            await self._request("POST", "/duplicates/resolve", json={"groups": normalized})
            return
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise
        trash_ids = [aid for g in normalized for aid in g["trashAssetIds"]]
        if trash_ids:
            await self._request("DELETE", "/assets", json={"ids": trash_ids, "force": False})
        await self._request(
            "DELETE", "/duplicates", json={"ids": [g["duplicateId"] for g in normalized]}
        )

    # ── Tags ──────────────────────────────────────────────

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

    # ── Upload ─────────────────────────────────────────────

    async def upload_asset(self, file_path: str) -> dict:
        """Upload a file to Immich."""
        from datetime import datetime, timezone

        stat = os.stat(file_path)
        filename = os.path.basename(file_path)
        birth = getattr(stat, 'st_birthtime', stat.st_mtime)
        created = datetime.fromtimestamp(birth, tz=timezone.utc).isoformat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        url = f"{self.base_url}/api/assets"
        with open(file_path, "rb") as f:
            files = {"assetData": (filename, f, "application/octet-stream")}
            data = {
                "deviceAssetId": f"{filename}-{stat.st_size}-{int(stat.st_mtime)}",
                "deviceId": "MCP Upload",
                "fileCreatedAt": created,
                "fileModifiedAt": modified,
                "isFavorite": "false",
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url, headers={"x-api-key": self.api_key},
                    files=files, data=data,
                )
                response.raise_for_status()
                return response.json()

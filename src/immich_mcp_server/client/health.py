"""Server health, version and library statistics.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

import httpx


class HealthApi:
    """Server health, version and library statistics."""

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
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                return
            raise

    async def get_server_version(self) -> dict:
        """Get Immich server version."""
        return await self._request("GET", "/server/version")

    async def get_server_features(self) -> dict:
        """Get the server feature flags (ocr, smartSearch, map...)."""
        return await self._request("GET", "/server/features")

    async def get_statistics(self) -> dict:
        """Get library statistics (photos, videos, storage).

        /server/statistics covers the whole server and Immich only serves it to
        an administrator. For any other account (a partner, the demo reviewer)
        it answers 403, so the counts come from the user's own library instead:
        /search/statistics per asset type, and the storage use from /users/me.
        The answer then carries `scope: user` so the caller knows the numbers
        are theirs, not the server's.
        """
        try:
            return await self._request("GET", "/server/statistics")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 403:
                raise

        photos = await self._request("POST", "/search/statistics", json={"type": "IMAGE"})
        videos = await self._request("POST", "/search/statistics", json={"type": "VIDEO"})
        me = await self._request("GET", "/users/me")
        return {
            "photos": photos.get("total", 0),
            "videos": videos.get("total", 0),
            "usage": me.get("quotaUsageInBytes", 0),
            "scope": "user",
        }

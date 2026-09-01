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
        """Get library statistics (photos, videos, storage)."""
        return await self._request("GET", "/server/statistics")

"""ML duplicate groups and their resolution.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

import httpx


class DuplicatesApi:
    """ML duplicate groups and their resolution."""

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

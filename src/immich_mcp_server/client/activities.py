"""Activities: comments and likes on shared albums.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

from typing import Any


class ActivitiesApi:
    """Activities: comments and likes on shared albums."""

    async def list_activities(
        self,
        album_id: str,
        asset_id: str | None = None,
        activity_type: str | None = None,
    ) -> list:
        """Comments and likes of one album, optionally of one asset in it."""
        params: dict[str, Any] = {"albumId": album_id}
        if asset_id:
            params["assetId"] = asset_id
        if activity_type:
            params["type"] = activity_type
        return await self._request("GET", "/activities", params=params)

    async def create_activity(
        self,
        album_id: str,
        activity_type: str = "comment",
        comment: str | None = None,
        asset_id: str | None = None,
    ) -> dict:
        """Post a comment or a like on an album or one of its assets."""
        body: dict[str, Any] = {"albumId": album_id, "type": activity_type}
        if comment:
            body["comment"] = comment
        if asset_id:
            body["assetId"] = asset_id
        return await self._request("POST", "/activities", json=body)

    async def delete_activity(self, activity_id: str) -> None:
        """Remove one comment or like."""
        await self._request("DELETE", f"/activities/{activity_id}")

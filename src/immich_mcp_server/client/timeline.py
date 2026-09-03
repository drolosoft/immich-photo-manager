"""Timeline buckets: cheap month-by-month library navigation.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

from typing import Any


class TimelineApi:
    """Timeline buckets: cheap month-by-month library navigation."""

    def _timeline_params(
        self,
        album_id: str | None,
        person_id: str | None,
        tag_id: str | None,
        is_favorite: bool | None,
        order: str | None,
    ) -> dict:
        """Query params shared by the buckets and single-bucket endpoints."""
        params: dict[str, Any] = {}
        if album_id:
            params["albumId"] = album_id
        if person_id:
            params["personId"] = person_id
        if tag_id:
            params["tagId"] = tag_id
        if is_favorite is not None:
            params["isFavorite"] = is_favorite
        if order:
            params["order"] = order
        return params

    async def get_timeline_buckets(
        self,
        album_id: str | None = None,
        person_id: str | None = None,
        tag_id: str | None = None,
        is_favorite: bool | None = None,
        order: str | None = None,
    ) -> list:
        """Month buckets with asset counts (`[{timeBucket, count}]`)."""
        params = self._timeline_params(album_id, person_id, tag_id, is_favorite, order)
        return await self._request("GET", "/timeline/buckets", params=params)

    async def get_timeline_bucket(
        self,
        time_bucket: str,
        album_id: str | None = None,
        person_id: str | None = None,
        tag_id: str | None = None,
        is_favorite: bool | None = None,
        order: str | None = None,
    ) -> dict:
        """One bucket's assets. Immich answers columnar (struct-of-arrays)."""
        params = self._timeline_params(album_id, person_id, tag_id, is_favorite, order)
        params["timeBucket"] = time_bucket
        return await self._request("GET", "/timeline/bucket", params=params)

    async def get_calendar_heatmap(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
        heatmap_type: str = "Taken",
    ) -> dict:
        """Per-day activity counts. Immich 3.x only: 2.x answers 404 and the
        tool derives the same shape from the buckets above."""
        params: dict[str, Any] = {"type": heatmap_type}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return await self._request("GET", "/users/me/calendar-heatmap", params=params)

"""Video playback download (the file behind get_video_frames).

Mixin of `ImmichClient` (see `immich_client.py`).
"""

import httpx


class VideoApi:
    """Video playback download (the file behind get_video_frames)."""

    async def get_video_playback(self, asset_id: str) -> bytes:
        """Download the playable video file of an asset (permission asset.view).

        GET /assets/{id}/video/playback exists on Immich 2.x and 3.x; it serves
        the transcoded rendition when there is one, else the original.
        """
        url = f"{self.base_url}/api/assets/{asset_id}/video/playback"
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            return response.content

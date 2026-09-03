"""Download archive: an album or a selection as one zip, streamed to disk.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

import os
from typing import Any

import httpx


class DownloadApi:
    """Download archive: an album or a selection as one zip, streamed to disk."""

    async def get_download_info(
        self,
        album_id: str | None = None,
        asset_ids: list[str] | None = None,
    ) -> dict:
        """Size and chunking of the archive Immich would build."""
        body: dict[str, Any] = {}
        if album_id:
            body["albumId"] = album_id
        if asset_ids:
            body["assetIds"] = asset_ids
        return await self._request("POST", "/download/info", json=body)

    async def download_archive(self, asset_ids: list[str], destination: str) -> int:
        """Stream the zip for these assets into `destination`; returns bytes written.

        The archive can be far bigger than memory (originals, videos), so the
        response is streamed chunk by chunk instead of loaded whole. The chunks
        go to `<destination>.part` and the file is renamed only once the stream
        finished: a timeout or a dropped connection then leaves no half-written
        zip behind, which the tool would otherwise refuse to overwrite on the
        next attempt."""
        url = f"{self.base_url}/api/download/archive"
        timeout = httpx.Timeout(600.0, connect=30.0)
        partial = f"{destination}.part"
        written = 0

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", url, headers=self._headers, json={"assetIds": asset_ids}
                ) as response:
                    response.raise_for_status()
                    with open(partial, "wb") as handle:
                        async for chunk in response.aiter_bytes():
                            handle.write(chunk)
                            written += len(chunk)
        except BaseException:
            # Whatever went wrong, the incomplete file is worse than no file:
            # a leftover would look like a finished download to the next call.
            if os.path.exists(partial):
                os.remove(partial)
            raise

        os.replace(partial, destination)
        return written

"""File upload.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

import os

import httpx


class UploadApi:
    """File upload."""

    async def upload_asset(self, file_path: str) -> dict:
        """Upload a file to Immich."""
        from datetime import datetime, timezone

        stat = os.stat(file_path)
        filename = os.path.basename(file_path)
        birth = getattr(stat, 'st_birthtime', stat.st_mtime)
        created = datetime.fromtimestamp(birth, tz=timezone.utc).isoformat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        url = f"{self.base_url}/api/assets"
        with open(file_path, "rb") as handle:
            files = {"assetData": (filename, handle, "application/octet-stream")}
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

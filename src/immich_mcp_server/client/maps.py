"""OpenStreetMap tiles for the PDF places map (only with map=True).

Mixin of `ImmichClient` (see `immich_client.py`).
"""

import httpx

from .. import __version__


class MapsApi:
    """OpenStreetMap tiles for the PDF places map (only with map=True)."""

    async def fetch_tile(self, zoom: int, tile_x: int, tile_y: int) -> bytes:
        """One OpenStreetMap tile (only used by export_pdf with map=True)."""
        url = f"https://tile.openstreetmap.org/{zoom}/{tile_x}/{tile_y}.png"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers={"User-Agent": f"immich-photo-manager/{__version__}"})
            response.raise_for_status()
            return response.content

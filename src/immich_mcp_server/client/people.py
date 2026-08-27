"""People, faces and face reassignment.

Mixin of `ImmichClient` (see `immich_client.py`).
"""

import base64

import httpx


class PeopleApi:
    """People, faces and face reassignment."""

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

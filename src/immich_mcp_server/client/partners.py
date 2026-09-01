"""Partners: share a whole library between two Immich users.

Also holds the plain user listing, which exists mainly to find the id a
partner call needs. Mixin of `ImmichClient` (see `immich_client.py`).
"""


class PartnersApi:
    """Partners: share a whole library between two Immich users."""

    async def list_users(self) -> list:
        """All users visible on the server (id, name, email)."""
        return await self._request("GET", "/users")

    async def list_partners(self, direction: str) -> list:
        """Partners in one direction: 'shared-with' (me) or 'shared-by' (me)."""
        return await self._request("GET", "/partners", params={"direction": direction})

    async def create_partner(self, user_id: str) -> dict:
        """Share this library with another user."""
        return await self._request("POST", "/partners", json={"sharedWithId": user_id})

    async def update_partner(self, user_id: str, in_timeline: bool) -> dict:
        """Show or hide the partner's assets in the main timeline."""
        return await self._request(
            "PUT", f"/partners/{user_id}", json={"inTimeline": in_timeline}
        )

    async def remove_partner(self, user_id: str) -> None:
        """Stop sharing this library with a user."""
        await self._request("DELETE", f"/partners/{user_id}")

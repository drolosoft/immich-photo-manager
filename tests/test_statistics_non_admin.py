"""
get_statistics for an account that is not an administrator.

Immich answers 403 to GET /server/statistics for any key that is not an
admin's: a family member with a partner account, or the reviewer account of
the public demo server. The client then counts the user's own library through
POST /search/statistics (images, then videos) and reads the storage use from
/users/me, so the tool still answers instead of failing.
"""

import json

import pytest
import respx
from httpx import Response

from immich_mcp_server.immich_client import ImmichClient

BASE = "https://immich.test"


@pytest.fixture
def client():
    return ImmichClient(base_url=BASE, api_key="reviewer-key")


@pytest.mark.asyncio
@respx.mock
async def test_admin_statistics_are_returned_as_they_come(client):
    respx.get(f"{BASE}/api/server/statistics").mock(
        return_value=Response(200, json={"photos": 10, "videos": 2, "usage": 300})
    )
    assert await client.get_statistics() == {"photos": 10, "videos": 2, "usage": 300}


@pytest.mark.asyncio
@respx.mock
async def test_a_non_admin_key_gets_its_own_counts_instead_of_a_403(client):
    respx.get(f"{BASE}/api/server/statistics").mock(return_value=Response(403, json={"message": "Forbidden"}))
    counts = respx.post(f"{BASE}/api/search/statistics").mock(
        side_effect=[Response(200, json={"total": 16}), Response(200, json={"total": 1})]
    )
    respx.get(f"{BASE}/api/users/me").mock(return_value=Response(200, json={"quotaUsageInBytes": 4096}))

    result = await client.get_statistics()

    assert result == {"photos": 16, "videos": 1, "usage": 4096, "scope": "user"}
    sent = [json.loads(call.request.content) for call in counts.calls]
    assert sent == [{"type": "IMAGE"}, {"type": "VIDEO"}]


@pytest.mark.asyncio
@respx.mock
async def test_other_errors_on_server_statistics_still_raise(client):
    respx.get(f"{BASE}/api/server/statistics").mock(return_value=Response(500, json={"message": "boom"}))
    with pytest.raises(Exception):
        await client.get_statistics()

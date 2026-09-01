"""The 2.0.4 batch, part one: stacks and partners.

Stacks group near-identical shots under one primary asset; partners share a
whole library between two users. Both areas are identical in the Immich
2.7.5 and 3.1.0 OpenAPI specs (verified 2026-09-02).
"""

import json

import pytest
import respx
from httpx import Response

from immich_mcp_server import server
from immich_mcp_server.immich_client import ImmichClient

BASE = "https://immich.test"


@pytest.fixture
def client():
    return ImmichClient(base_url=BASE, api_key="k")


# ── Client: stacks ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_create_stack_posts_the_asset_ids(client):
    route = respx.post(f"{BASE}/api/stacks").mock(
        return_value=Response(201, json={"id": "s1", "primaryAssetId": "a1", "assets": []}))
    await client.create_stack(["a1", "a2"])
    assert json.loads(route.calls[0].request.content) == {"assetIds": ["a1", "a2"]}


@pytest.mark.asyncio
@respx.mock
async def test_list_stacks_sends_primary_filter_when_given(client):
    route = respx.get(f"{BASE}/api/stacks").mock(return_value=Response(200, json=[]))
    await client.list_stacks(primary_asset_id="a1")
    assert route.calls[0].request.url.params["primaryAssetId"] == "a1"


@pytest.mark.asyncio
@respx.mock
async def test_update_stack_puts_the_new_primary(client):
    route = respx.put(f"{BASE}/api/stacks/s1").mock(
        return_value=Response(200, json={"id": "s1", "primaryAssetId": "a2", "assets": []}))
    await client.update_stack("s1", primary_asset_id="a2")
    assert json.loads(route.calls[0].request.content) == {"primaryAssetId": "a2"}


@pytest.mark.asyncio
@respx.mock
async def test_delete_stack_calls_the_delete_endpoint(client):
    route = respx.delete(f"{BASE}/api/stacks/s1").mock(return_value=Response(204))
    await client.delete_stack("s1")
    assert route.called


# ── Client: partners and users ───────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_list_partners_sends_the_direction(client):
    route = respx.get(f"{BASE}/api/partners").mock(return_value=Response(200, json=[]))
    await client.list_partners("shared-with")
    assert route.calls[0].request.url.params["direction"] == "shared-with"


@pytest.mark.asyncio
@respx.mock
async def test_create_partner_posts_the_shared_with_id(client):
    route = respx.post(f"{BASE}/api/partners").mock(
        return_value=Response(201, json={"id": "u2"}))
    await client.create_partner("u2")
    assert json.loads(route.calls[0].request.content) == {"sharedWithId": "u2"}


@pytest.mark.asyncio
@respx.mock
async def test_update_partner_puts_the_timeline_flag(client):
    route = respx.put(f"{BASE}/api/partners/u2").mock(
        return_value=Response(200, json={"id": "u2", "inTimeline": True}))
    await client.update_partner("u2", in_timeline=True)
    assert json.loads(route.calls[0].request.content) == {"inTimeline": True}


@pytest.mark.asyncio
@respx.mock
async def test_remove_partner_calls_the_delete_endpoint(client):
    route = respx.delete(f"{BASE}/api/partners/u2").mock(return_value=Response(200, json={}))
    await client.remove_partner("u2")
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_list_users_fetches_the_users_endpoint(client):
    respx.get(f"{BASE}/api/users").mock(
        return_value=Response(200, json=[{"id": "u1", "name": "Lab", "email": "lab@example.com"}]))
    got = await client.list_users()
    assert got[0]["id"] == "u1"


# ── Tools ────────────────────────────────────────────────────────────────────

def _stack(stack_id="s1", primary="a1"):
    return {"id": stack_id, "primaryAssetId": primary,
            "assets": [{"id": "a1", "originalFileName": "1.jpg"},
                       {"id": "a2", "originalFileName": "2.jpg"}]}


class StubStacksClient:
    def __init__(self):
        self.kwargs = None

    async def create_stack(self, asset_ids):
        self.kwargs = {"asset_ids": asset_ids}
        return _stack()

    async def list_stacks(self, primary_asset_id=None):
        return [_stack(), _stack("s2", "a3")]

    async def get_stack(self, stack_id):
        self.kwargs = {"stack_id": stack_id}
        return _stack()

    async def update_stack(self, stack_id, primary_asset_id):
        self.kwargs = {"stack_id": stack_id, "primary_asset_id": primary_asset_id}
        return _stack(primary=primary_asset_id)

    async def delete_stack(self, stack_id):
        self.kwargs = {"stack_id": stack_id}


@pytest.mark.asyncio
async def test_create_stack_tool_reports_id_and_asset_count(fake_ctx):
    stub = StubStacksClient()
    raw = await server.create_stack(fake_ctx(stub), asset_ids=["a1", "a2"])
    result = json.loads(raw)
    assert stub.kwargs == {"asset_ids": ["a1", "a2"]}
    assert result["id"] == "s1"
    assert result["asset_count"] == 2


@pytest.mark.asyncio
async def test_list_stacks_tool_trims_assets_to_essentials(fake_ctx):
    raw = await server.list_stacks(fake_ctx(StubStacksClient()))
    result = json.loads(raw)
    assert result["total"] == 2
    first = result["stacks"][0]
    assert first["primary_asset_id"] == "a1"
    assert first["assets"] == [{"asset_id": "a1", "filename": "1.jpg"},
                               {"asset_id": "a2", "filename": "2.jpg"}]


@pytest.mark.asyncio
async def test_update_stack_tool_moves_the_primary(fake_ctx):
    stub = StubStacksClient()
    raw = await server.update_stack(fake_ctx(stub), stack_id="s1", primary_asset_id="a2")
    assert stub.kwargs == {"stack_id": "s1", "primary_asset_id": "a2"}
    assert json.loads(raw)["primary_asset_id"] == "a2"


@pytest.mark.asyncio
async def test_delete_stack_tool_says_assets_survive(fake_ctx):
    stub = StubStacksClient()
    raw = await server.delete_stack(fake_ctx(stub), stack_id="s1")
    result = json.loads(raw)
    assert stub.kwargs == {"stack_id": "s1"}
    assert result["success"] is True


class StubPartnersClient:
    def __init__(self):
        self.directions = []
        self.kwargs = None

    async def list_partners(self, direction):
        self.directions.append(direction)
        if direction == "shared-with":
            return [{"id": "u2", "name": "Son", "email": "son@example.com", "inTimeline": True}]
        return []

    async def create_partner(self, user_id):
        self.kwargs = {"user_id": user_id}
        return {"id": user_id, "inTimeline": False}

    async def update_partner(self, user_id, in_timeline):
        self.kwargs = {"user_id": user_id, "in_timeline": in_timeline}
        return {"id": user_id, "inTimeline": in_timeline}

    async def remove_partner(self, user_id):
        self.kwargs = {"user_id": user_id}

    async def list_users(self):
        return [{"id": "u1", "name": "Lab", "email": "lab@example.com",
                 "profileImagePath": "/x.jpg"}]


@pytest.mark.asyncio
async def test_list_partners_tool_reports_both_directions(fake_ctx):
    stub = StubPartnersClient()
    raw = await server.list_partners(fake_ctx(stub))
    result = json.loads(raw)
    assert sorted(stub.directions) == ["shared-by", "shared-with"]
    assert result["shared_with_me"][0]["email"] == "son@example.com"
    assert result["shared_by_me"] == []


@pytest.mark.asyncio
async def test_create_partner_tool_passes_the_user_id(fake_ctx):
    stub = StubPartnersClient()
    raw = await server.create_partner(fake_ctx(stub), user_id="u2")
    assert stub.kwargs == {"user_id": "u2"}
    assert json.loads(raw)["id"] == "u2"


@pytest.mark.asyncio
async def test_update_partner_tool_passes_the_timeline_flag(fake_ctx):
    stub = StubPartnersClient()
    await server.update_partner(fake_ctx(stub), user_id="u2", in_timeline=True)
    assert stub.kwargs == {"user_id": "u2", "in_timeline": True}


@pytest.mark.asyncio
async def test_remove_partner_tool_reports_success(fake_ctx):
    stub = StubPartnersClient()
    raw = await server.remove_partner(fake_ctx(stub), user_id="u2")
    assert stub.kwargs == {"user_id": "u2"}
    assert json.loads(raw)["success"] is True


@pytest.mark.asyncio
async def test_list_users_tool_trims_to_id_name_email(fake_ctx):
    raw = await server.list_users(fake_ctx(StubPartnersClient()))
    users = json.loads(raw)["users"]
    assert users == [{"id": "u1", "name": "Lab", "email": "lab@example.com"}]

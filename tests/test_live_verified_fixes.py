"""Fixes found by exercising every tool against live Immich 2.7.5 and 3.1.0 (2026-08-25).

- list_assets(is_trashed=True): Immich's MetadataSearchDto has no `isTrashed`; the
  filter was silently ignored and returned the *active* library. Trashed items are
  selected with `withDeleted` + `trashedAfter`.
- resolve_duplicates: POST /duplicates/resolve expects
  {"groups": [{"duplicateId", "keepAssetIds", "trashAssetIds"}]} (Immich >= 2.6);
  the client sent a bare list with the wrong key names. Older servers get a fallback.
- update_tag: TagUpdateDto only has `color` — renaming is not possible via the API,
  so asking for a name change must fail loudly instead of pretending.
- reassign_face: PUT /faces/{id} takes the person id in the path and the face id
  in the body; the client had them swapped, so reassignment never happened.
- update_credentials: validated with /server/ping, which is unauthenticated, so any
  bogus API key was accepted and persisted. Validate with an authenticated call.
"""

import json

import pytest
import respx
from httpx import Response

from immich_mcp_server import server
from immich_mcp_server.immich_client import ImmichClient

BASE = "https://immich.test"
EMPTY = {"albums": {}, "assets": {"items": [], "nextPage": None, "total": 0}}


@pytest.fixture
def client():
    return ImmichClient(base_url=BASE, api_key="k")


# ── list_assets(is_trashed) ───────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_list_assets_trashed_uses_withDeleted_and_trashedAfter(client):
    route = respx.post(f"{BASE}/api/search/metadata").mock(return_value=Response(200, json=EMPTY))
    await client.list_assets(is_trashed=True)
    body = json.loads(route.calls.last.request.content)
    assert body.get("withDeleted") is True
    assert "trashedAfter" in body
    assert "isTrashed" not in body


@pytest.mark.asyncio
@respx.mock
async def test_list_assets_not_trashed_sends_no_trash_filter(client):
    route = respx.post(f"{BASE}/api/search/metadata").mock(return_value=Response(200, json=EMPTY))
    await client.list_assets(is_trashed=False)
    body = json.loads(route.calls.last.request.content)
    assert "isTrashed" not in body and "withDeleted" not in body and "trashedAfter" not in body


# ── resolve_duplicates ────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_resolve_duplicates_sends_immich_dto_and_accepts_legacy_keys(client):
    route = respx.post(f"{BASE}/api/duplicates/resolve").mock(return_value=Response(204))
    await client.resolve_duplicates([
        {"duplicateId": "d1", "assetIds": ["keep1"], "trashIds": ["trash1", "trash2"]},
        {"duplicateId": "d2", "keepAssetIds": ["keep2"], "trashAssetIds": ["trash3"]},
    ])
    body = json.loads(route.calls.last.request.content)
    assert body == {"groups": [
        {"duplicateId": "d1", "keepAssetIds": ["keep1"], "trashAssetIds": ["trash1", "trash2"]},
        {"duplicateId": "d2", "keepAssetIds": ["keep2"], "trashAssetIds": ["trash3"]},
    ]}


@pytest.mark.asyncio
@respx.mock
async def test_resolve_duplicates_falls_back_on_old_servers(client):
    respx.post(f"{BASE}/api/duplicates/resolve").mock(return_value=Response(404))
    trash = respx.delete(f"{BASE}/api/assets").mock(return_value=Response(204))
    unflag = respx.delete(f"{BASE}/api/duplicates").mock(return_value=Response(204))
    await client.resolve_duplicates([{"duplicateId": "d1", "assetIds": ["keep1"], "trashIds": ["trash1"]}])
    assert json.loads(trash.calls.last.request.content) == {"ids": ["trash1"], "force": False}
    assert json.loads(unflag.calls.last.request.content) == {"ids": ["d1"]}


# ── update_tag ────────────────────────────────────────────────


class TagStub:
    def __init__(self):
        self.calls = []

    async def update_tag(self, tag_id, **fields):
        self.calls.append(fields)
        return {"id": tag_id, "name": "old", **fields}


@pytest.mark.asyncio
async def test_update_tag_rejects_rename(fake_ctx):
    stub = TagStub()
    out = json.loads(await server.update_tag(fake_ctx(stub), tag_id="t1", name="new-name"))
    assert "error" in out and "rename" in out["error"].lower()
    assert stub.calls == []


@pytest.mark.asyncio
async def test_update_tag_color_still_works(fake_ctx):
    stub = TagStub()
    out = json.loads(await server.update_tag(fake_ctx(stub), tag_id="t1", color="#00ff00"))
    assert out["color"] == "#00ff00" and stub.calls == [{"color": "#00ff00"}]


# ── update_credentials ────────────────────────────────────────


def _ctx():
    return type("Ctx", (), {"request_context": type("R", (), {"lifespan_context": {"immich": None}})()})()


@pytest.mark.asyncio
@respx.mock
async def test_update_credentials_rejects_bad_api_key(isolated_cache):
    respx.get(f"{BASE}/api/server/ping").mock(return_value=Response(200, json={"res": "pong"}))
    respx.get(f"{BASE}/api/users/me").mock(return_value=Response(401, json={"message": "Invalid API key"}))
    out = json.loads(await server.update_credentials(_ctx(), base_url=BASE, api_key="bogus"))
    assert out["success"] is False
    assert not list(isolated_cache.glob("**/*.json")), "bogus key must not be persisted"


@pytest.mark.asyncio
@respx.mock
async def test_update_credentials_accepts_key_lacking_user_read(isolated_cache):
    """A scoped API key without user.read gets 403 on /users/me — that's still a valid key."""
    respx.get(f"{BASE}/api/users/me").mock(return_value=Response(403, json={"message": "Missing permission"}))
    respx.get(f"{BASE}/api/server/statistics").mock(return_value=Response(200, json={"photos": 1, "videos": 0}))
    out = json.loads(await server.update_credentials(_ctx(), base_url=BASE, api_key="scoped"))
    assert out["success"] is True


# ── reassign_face ─────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_reassign_face_puts_person_in_path_and_face_in_body(client):
    route = respx.put(f"{BASE}/api/faces/person-1").mock(return_value=Response(200, json={"id": "person-1"}))
    await client.reassign_face(face_id="face-9", person_id="person-1")
    assert route.called
    assert json.loads(route.calls.last.request.content) == {"id": "face-9"}

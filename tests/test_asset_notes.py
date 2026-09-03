"""Asset notes: the plugin's own memory on each asset, stored in Immich's
per-asset metadata (key -> JSON object; same endpoints on 2.7.5 and 3.1.0,
verified 2026-09-03).

One key, `immich-photo-manager`, holds {"reviews": [...], "actions": [...]},
each capped at the last 10 entries. Tags stay the visible state in Immich;
these notes carry the why. Immich cannot search this metadata, so the batch
reader is what makes "skip what I already reviewed" affordable.
"""

import json

import pytest
import respx
from httpx import Response

from immich_mcp_server import server
from immich_mcp_server.immich_client import ImmichClient
from immich_mcp_server.tools import notes

BASE = "https://immich.test"
KEY = "immich-photo-manager"


@pytest.fixture
def client():
    return ImmichClient(base_url=BASE, api_key="k")


# ── Client ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_get_asset_metadata_lists_every_key(client):
    respx.get(f"{BASE}/api/assets/a1/metadata").mock(
        return_value=Response(200, json=[{"key": KEY, "value": {"reviews": []},
                                          "updatedAt": "2026-09-03T10:00:00Z"}]))
    got = await client.get_asset_metadata("a1")
    assert got[0]["key"] == KEY


@pytest.mark.asyncio
@respx.mock
async def test_upsert_asset_metadata_puts_one_item(client):
    route = respx.put(f"{BASE}/api/assets/a1/metadata").mock(
        return_value=Response(200, json=[]))
    await client.upsert_asset_metadata("a1", KEY, {"reviews": [{"verdict": "keep"}]})
    body = json.loads(route.calls[0].request.content)
    assert body == {"items": [{"key": KEY, "value": {"reviews": [{"verdict": "keep"}]}}]}


@pytest.mark.asyncio
@respx.mock
async def test_delete_asset_metadata_removes_only_that_key(client):
    route = respx.delete(f"{BASE}/api/assets/a1/metadata/{KEY}").mock(
        return_value=Response(204))
    await client.delete_asset_metadata("a1", KEY)
    assert route.called


# ── Tools ────────────────────────────────────────────────────────────────────

class StubNotesClient:
    """In-memory metadata store keyed by asset id, other apps' keys included."""

    def __init__(self, existing=None):
        self.store = existing or {}
        self.deleted = []

    async def get_asset_metadata(self, asset_id):
        return [{"key": key, "value": value, "updatedAt": "2026-09-03T10:00:00Z"}
                for key, value in self.store.get(asset_id, {}).items()]

    async def upsert_asset_metadata(self, asset_id, key, value):
        self.store.setdefault(asset_id, {})[key] = value

    async def delete_asset_metadata(self, asset_id, key):
        self.deleted.append((asset_id, key))
        self.store.get(asset_id, {}).pop(key, None)

    async def get_asset(self, asset_id):
        return {"id": asset_id, "originalFileName": f"{asset_id}.jpg"}


@pytest.mark.asyncio
async def test_review_assets_appends_a_dated_verdict_with_reason(fake_ctx, monkeypatch):
    monkeypatch.setattr(notes, "_now", lambda: "2026-09-03T10:00:00Z")
    stub = StubNotesClient()
    raw = await server.review_assets(
        fake_ctx(stub), asset_ids=["a1", "a2"], verdict="delete_candidate",
        reason="near-identical to a3")
    result = json.loads(raw)
    assert result == {"success": True, "reviewed": 2, "verdict": "delete_candidate",
                      "failed": []}
    assert stub.store["a1"][KEY]["reviews"] == [
        {"at": "2026-09-03T10:00:00Z", "verdict": "delete_candidate",
         "reason": "near-identical to a3"}]
    assert stub.store["a2"][KEY]["reviews"][0]["verdict"] == "delete_candidate"


@pytest.mark.asyncio
async def test_review_assets_rejects_an_unknown_verdict(fake_ctx):
    stub = StubNotesClient()
    raw = await server.review_assets(fake_ctx(stub), asset_ids=["a1"], verdict="meh", reason="")
    result = json.loads(raw)
    assert "error" in result
    assert "keep" in result["error"]
    assert stub.store == {}


@pytest.mark.asyncio
async def test_review_assets_keeps_other_apps_keys_and_earlier_reviews(fake_ctx, monkeypatch):
    monkeypatch.setattr(notes, "_now", lambda: "2026-09-03T11:00:00Z")
    stub = StubNotesClient({"a1": {
        "someone-elses-app": {"x": 1},
        KEY: {"reviews": [{"at": "2026-09-01T09:00:00Z", "verdict": "keep", "reason": "first pass"}],
              "actions": [{"at": "2026-09-01T09:05:00Z", "action": "rotate", "detail": "90"}]},
    }})
    await server.review_assets(fake_ctx(stub), asset_ids=["a1"], verdict="keep", reason="second pass")
    assert stub.store["a1"]["someone-elses-app"] == {"x": 1}
    reviews = stub.store["a1"][KEY]["reviews"]
    assert [review["reason"] for review in reviews] == ["first pass", "second pass"]
    assert stub.store["a1"][KEY]["actions"][0]["action"] == "rotate"


@pytest.mark.asyncio
async def test_review_history_is_capped_at_ten_newest(fake_ctx, monkeypatch):
    monkeypatch.setattr(notes, "_now", lambda: "2026-09-03T12:00:00Z")
    old = [{"at": f"2026-08-{day:02d}T00:00:00Z", "verdict": "keep", "reason": f"r{day}"}
           for day in range(1, 11)]
    stub = StubNotesClient({"a1": {KEY: {"reviews": old, "actions": []}}})
    await server.review_assets(fake_ctx(stub), asset_ids=["a1"], verdict="needs_check", reason="new")
    reviews = stub.store["a1"][KEY]["reviews"]
    assert len(reviews) == 10
    assert reviews[0]["reason"] == "r2"
    assert reviews[-1]["reason"] == "new"


@pytest.mark.asyncio
async def test_record_action_appends_to_the_actions_list(fake_ctx, monkeypatch):
    monkeypatch.setattr(notes, "_now", lambda: "2026-09-03T10:00:00Z")
    stub = StubNotesClient()
    raw = await server.record_action(
        fake_ctx(stub), asset_ids=["a1"], action="added_to_album",
        detail="Lisbon 2026, from prompt 'group my Lisbon trip'")
    assert json.loads(raw) == {"success": True, "recorded": 1,
                               "action": "added_to_album", "failed": []}
    assert stub.store["a1"][KEY]["actions"] == [
        {"at": "2026-09-03T10:00:00Z", "action": "added_to_album",
         "detail": "Lisbon 2026, from prompt 'group my Lisbon trip'"}]
    assert stub.store["a1"][KEY]["reviews"] == []


@pytest.mark.asyncio
async def test_get_asset_notes_returns_only_the_plugin_key(fake_ctx):
    stub = StubNotesClient({"a1": {
        "someone-elses-app": {"x": 1},
        KEY: {"reviews": [{"at": "t", "verdict": "keep", "reason": "ok"}], "actions": []},
    }})
    result = json.loads(await server.get_asset_notes(fake_ctx(stub), asset_id="a1"))
    assert result == {"asset_id": "a1",
                      "reviews": [{"at": "t", "verdict": "keep", "reason": "ok"}],
                      "actions": []}


@pytest.mark.asyncio
async def test_get_asset_notes_is_empty_when_never_annotated(fake_ctx):
    result = json.loads(await server.get_asset_notes(fake_ctx(StubNotesClient()), asset_id="a9"))
    assert result == {"asset_id": "a9", "reviews": [], "actions": []}


@pytest.mark.asyncio
async def test_get_assets_notes_lists_only_annotated_assets_with_last_verdict(fake_ctx):
    stub = StubNotesClient({
        "a1": {KEY: {"reviews": [{"at": "t1", "verdict": "keep", "reason": "one"},
                                 {"at": "t2", "verdict": "delete_candidate", "reason": "two"}],
                     "actions": []}},
        "a3": {KEY: {"reviews": [], "actions": [{"at": "t3", "action": "rotate", "detail": "90"}]}},
    })
    result = json.loads(await server.get_assets_notes(fake_ctx(stub), asset_ids=["a1", "a2", "a3"]))
    assert result["checked"] == 3
    assert result["annotated"] == [
        {"asset_id": "a1", "last_verdict": "delete_candidate", "last_reason": "two",
         "last_review_at": "t2", "reviews": 2, "actions": 0},
        {"asset_id": "a3", "last_verdict": None, "last_reason": None,
         "last_review_at": None, "reviews": 0, "actions": 1},
    ]


@pytest.mark.asyncio
async def test_clear_asset_notes_deletes_only_the_plugin_key(fake_ctx):
    stub = StubNotesClient({"a1": {"someone-elses-app": {"x": 1}, KEY: {"reviews": [], "actions": []}}})
    raw = await server.clear_asset_notes(fake_ctx(stub), asset_ids=["a1"])
    assert json.loads(raw) == {"success": True, "cleared": 1, "failed": []}
    assert stub.deleted == [("a1", KEY)]
    assert stub.store["a1"] == {"someone-elses-app": {"x": 1}}


@pytest.mark.asyncio
async def test_get_asset_info_includes_notes_only_when_asked(fake_ctx):
    stub = StubNotesClient({"a1": {KEY: {"reviews": [{"at": "t", "verdict": "keep", "reason": "ok"}],
                                        "actions": []}}})
    plain = json.loads(await server.get_asset_info(fake_ctx(stub), asset_id="a1"))
    assert "notes" not in plain
    with_notes = json.loads(await server.get_asset_info(fake_ctx(stub), asset_id="a1", with_notes=True))
    assert with_notes["notes"]["reviews"][0]["verdict"] == "keep"

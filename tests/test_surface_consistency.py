"""One shape for the whole 94-tool surface: parameter names, delete payloads,
list totals, empty-input guards, partial failures and Immich error reporting.

The tools grew in seven batches, and each batch answered these questions its own
way: three new tools shadowed the builtin `type`, two halves of the API disagreed
on whether `deleted` holds a boolean or an id, four list tools shipped without the
`total` every other list carries, and nine modules let an Immich 4xx escape as a
bare tool failure. This file pins the single answer to each, so a future batch
that drifts fails here rather than in a user's session.
"""

import inspect
import json

import httpx
import pytest

from immich_mcp_server import server
from immich_mcp_server.tools._common import _album_assets


def _http_error(status, detail="immich said no"):
    """An httpx.HTTPStatusError carrying `status` and a body to quote back."""
    request = httpx.Request("GET", "https://immich.test/api/thing")
    response = httpx.Response(status, request=request, text=detail)
    return httpx.HTTPStatusError(str(status), request=request, response=response)


def _tool_parameters(tool):
    """The parameter names a tool exposes on the wire, `ctx` excluded."""
    return [name for name in inspect.signature(tool).parameters if name != "ctx"]


# ── A1: no tool parameter shadows a builtin ──────────────────────────────────

@pytest.mark.parametrize("tool, expected", [
    (server.search_suggestions, "suggestion_type"),
    (server.get_calendar_heatmap, "heatmap_type"),
    (server.list_activities, "activity_type"),
])
def test_type_parameters_are_named_after_their_noun(tool, expected):
    """`type` shadows the builtin and says nothing; the client mixins and the
    older tools have always used <noun>_type. These three now match."""
    parameters = _tool_parameters(tool)
    assert expected in parameters
    assert "type" not in parameters


# ── A2: one delete payload for the whole surface ─────────────────────────────

class StubDeleteClient:
    """Accepts any delete and remembers which id it was given."""

    def __init__(self):
        self.deleted = None

    async def delete_album(self, album_id):
        self.deleted = album_id

    async def delete_tag(self, tag_id):
        self.deleted = tag_id

    async def delete_memory(self, memory_id):
        self.deleted = memory_id

    async def delete_stack(self, stack_id):
        self.deleted = stack_id

    async def delete_activity(self, activity_id):
        self.deleted = activity_id


@pytest.mark.asyncio
@pytest.mark.parametrize("tool, argument", [
    (server.delete_album, "album_id"),
    (server.delete_tag, "tag_id"),
    (server.delete_memory, "memory_id"),
    (server.delete_stack, "stack_id"),
    (server.delete_activity, "activity_id"),
])
async def test_every_delete_answers_success_true_and_deleted_id(fake_ctx, tool, argument):
    """`success` carries the boolean and `deleted` carries the subject, so a
    caller reading result['deleted'] never gets True from one tool and a UUID
    from the next."""
    stub = StubDeleteClient()
    raw = await tool(fake_ctx(stub), **{argument: "the-id"})
    result = json.loads(raw)
    assert result["success"] is True
    assert result["deleted"] == "the-id"
    assert stub.deleted == "the-id"


# ── A3: every list tool reports a total ──────────────────────────────────────

class StubListClient:
    """Two-item answers for the list tools that were missing their total."""

    async def reverse_geocode(self, lat, lon):
        return [{"city": "Lisbon"}, {"city": "Sintra"}]

    async def list_users(self):
        return [{"id": "u1", "name": "Lab", "email": "lab@example.com"},
                {"id": "u2", "name": "Partner", "email": "partner@example.com"}]

    async def search_suggestions(self, suggestion_type, **kwargs):
        return ["Lisbon", "Porto"]

    async def search_explore(self):
        return [{"fieldName": "exifInfo.city", "items": [{"value": "Lisbon", "data": {"id": "a1"}}]},
                {"fieldName": "smartInfo.tags", "items": [{"value": "beach", "data": {"id": "a2"}}]}]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool, kwargs, key", [
    (server.reverse_geocode, {"lat": 38.7, "lon": -9.1}, "places"),
    (server.list_users, {}, "users"),
    (server.search_suggestions, {"suggestion_type": "city"}, "suggestions"),
    (server.search_explore, {}, "fields"),
])
async def test_list_tools_report_a_total_next_to_their_items(fake_ctx, tool, kwargs, key):
    raw = await tool(fake_ctx(StubListClient()), **kwargs)
    result = json.loads(raw)
    assert result["total"] == len(result[key]) == 2


# ── A4: an Immich 4xx comes back as an error, never as a crash ───────────────

class StubRefusingClient:
    """Every call it is asked for answers with the same HTTP status."""

    def __init__(self, status):
        self.error = _http_error(status)

    async def search_suggestions(self, *args, **kwargs):
        raise self.error

    async def search_metadata(self, **kwargs):
        raise self.error

    async def search_smart(self, **kwargs):
        raise self.error

    async def create_stack(self, asset_ids):
        raise self.error

    async def create_partner(self, user_id):
        raise self.error

    async def update_partner(self, user_id, **kwargs):
        raise self.error

    async def create_activity(self, album_id, **kwargs):
        raise self.error

    async def list_activities(self, album_id, **kwargs):
        raise self.error

    async def get_timeline_bucket(self, time_bucket, **kwargs):
        raise self.error

    async def search_statistics(self, **kwargs):
        raise self.error


@pytest.mark.asyncio
@pytest.mark.parametrize("tool, kwargs, status", [
    (server.search_suggestions, {"suggestion_type": "colour"}, 400),
    (server.search_metadata, {"person_ids": ["not-a-uuid"]}, 400),
    (server.search_smart, {"query": "beach", "tag_ids": ["not-a-uuid"]}, 400),
    (server.create_stack, {"asset_ids": ["a1", "a2"]}, 400),
    (server.create_partner, {"user_id": "u1"}, 400),
    (server.update_partner, {"user_id": "u1", "in_timeline": True}, 400),
    (server.create_activity, {"album_id": "alb1", "comment": "hi"}, 400),
    (server.list_activities, {"album_id": "nope"}, 404),
    (server.get_timeline_bucket, {"time_bucket": "not-a-bucket"}, 400),
    (server.search_statistics, {"taken_after": "yesterday"}, 400),
])
async def test_an_immich_rejection_becomes_a_readable_error(fake_ctx, tool, kwargs, status):
    raw = await tool(fake_ctx(StubRefusingClient(status)), **kwargs)
    result = json.loads(raw)
    assert result["error"] == f"Immich API error: {status}"
    assert result["detail"] == "immich said no"


@pytest.mark.asyncio
async def test_update_partner_error_names_the_list_the_id_must_come_from(fake_ctx):
    """The docstring already warned that only a shared_with_me partner can be
    updated; the failure now says the same thing instead of a bare status."""
    raw = await server.update_partner(
        fake_ctx(StubRefusingClient(400)), user_id="u1", in_timeline=True)
    assert "shared_with_me" in json.loads(raw)["hint"]


class StubFeatureBlindClient:
    """A scoped key: the version reads fine, the feature flags answer 403."""

    async def get_server_version(self):
        return {"major": 3, "minor": 1, "patch": 0}

    async def get_server_features(self):
        raise _http_error(403, "forbidden")


@pytest.mark.asyncio
async def test_get_capabilities_survives_a_key_that_cannot_read_features(fake_ctx):
    """Half an answer beats none: the version and the quirks are still true when
    the flags are out of reach, so the 403 becomes a note rather than a failure."""
    raw = await server.get_capabilities(fake_ctx(StubFeatureBlindClient()))
    result = json.loads(raw)
    assert result["server_version"] == "3.1.0"
    assert result["features"] == {}
    assert result["quirks"]
    assert "403" in result["features_note"]


# ── A7: the destructive tools all carry a machine-readable marker ────────────

def test_merge_people_declares_its_side_effect():
    """It is dual-mode — a preview without confirm, irreversible with it — and
    the docstring now says so in the same sentence every other tool uses."""
    docstring = server.merge_people.__doc__
    assert "Side effect:" in docstring
    assert "confirm=true" in docstring


# ── B1: an empty asset_ids is a mistake, not an empty success ────────────────

class StubNeverCalledClient:
    """Fails the test if a tool reaches the server with nothing to work on."""

    def __getattr__(self, name):
        async def refuse(*args, **kwargs):
            raise AssertionError(f"{name} must not be called with an empty asset list")
        return refuse


@pytest.mark.asyncio
@pytest.mark.parametrize("tool, kwargs", [
    (server.create_stack, {}),
    (server.review_assets, {"verdict": "keep"}),
    (server.record_action, {"action": "added_to_album"}),
    (server.get_assets_notes, {}),
    (server.clear_asset_notes, {}),
    (server.update_assets_metadata, {"is_favorite": True}),
])
async def test_bulk_tools_refuse_an_empty_asset_list(fake_ctx, tool, kwargs):
    raw = await tool(fake_ctx(StubNeverCalledClient()), asset_ids=[], **kwargs)
    assert json.loads(raw) == {"error": "asset_ids cannot be empty."}


# ── B2: one bad asset does not throw away the rest of the batch ──────────────

class StubHalfBrokenClient:
    """Everything works except the asset called 'bad', which cannot be read."""

    def __init__(self):
        self.written = []

    async def get_asset_metadata(self, asset_id):
        if asset_id == "bad":
            raise _http_error(404, "no such asset")
        return [{"key": "immich-photo-manager",
                 "value": {"reviews": [{"at": "t", "verdict": "keep", "reason": "ok"}],
                           "actions": []}}]

    async def upsert_asset_metadata(self, asset_id, key, value):
        self.written.append(asset_id)

    async def delete_asset_metadata(self, asset_id, key):
        if asset_id == "bad":
            raise _http_error(404, "no such asset")
        self.written.append(asset_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("tool, kwargs, counted", [
    (server.review_assets, {"verdict": "keep"}, "reviewed"),
    (server.record_action, {"action": "rotated"}, "recorded"),
    (server.clear_asset_notes, {}, "cleared"),
])
async def test_note_tools_keep_going_past_a_failing_asset(fake_ctx, tool, kwargs, counted):
    """_append_note is read-modify-write, so aborting mid-batch used to leave
    half the assets annotated with no signal at all. Now the survivors are
    counted and the casualties are named."""
    stub = StubHalfBrokenClient()
    raw = await tool(fake_ctx(stub), asset_ids=["a1", "bad", "a2"], **kwargs)
    result = json.loads(raw)
    assert result["success"] is False
    assert result[counted] == 2
    assert result["failed"] == [{"asset_id": "bad", "error": result["failed"][0]["error"]}]
    assert stub.written == ["a1", "a2"]


@pytest.mark.asyncio
async def test_get_assets_notes_reports_the_assets_it_could_not_read(fake_ctx):
    raw = await server.get_assets_notes(
        fake_ctx(StubHalfBrokenClient()), asset_ids=["a1", "bad", "a2"])
    result = json.loads(raw)
    assert result["success"] is False
    assert result["checked"] == 2
    assert [row["asset_id"] for row in result["annotated"]] == ["a1", "a2"]
    assert [row["asset_id"] for row in result["failed"]] == ["bad"]


@pytest.mark.asyncio
async def test_note_tools_report_success_when_every_asset_worked(fake_ctx):
    raw = await server.review_assets(
        fake_ctx(StubHalfBrokenClient()), asset_ids=["a1", "a2"], verdict="keep")
    result = json.loads(raw)
    assert result["success"] is True
    assert result["failed"] == []


class StubHalfBrokenPeopleClient:
    """One of the persons to merge no longer exists."""

    async def get_person(self, person_id):
        if person_id == "gone":
            raise _http_error(404, "no such person")
        return {"id": person_id, "name": f"Person {person_id}"}


@pytest.mark.asyncio
async def test_merge_people_preview_shows_the_names_it_could_resolve(fake_ctx):
    """A preview exists so a human can read the names before an irreversible
    merge; dying on one stale id showed no names at all."""
    raw = await server.merge_people(
        fake_ctx(StubHalfBrokenPeopleClient()), person_id="p1", merge_ids=["p2", "gone"])
    result = json.loads(raw)
    assert result["confirm_required"] is True
    assert [person["id"] for person in result["merge"]] == ["p2"]
    assert [person["person_id"] for person in result["failed"]] == ["gone"]


# ── B3: `size` means the same thing everywhere ───────────────────────────────

class StubSizeClient:
    def __init__(self):
        self.kwargs = None

    async def search_large_assets(self, **kwargs):
        self.kwargs = kwargs
        return []

    async def list_memories(self, **kwargs):
        self.kwargs = kwargs
        return []


@pytest.mark.asyncio
@pytest.mark.parametrize("size, expected", [(500, 200), (0, 20), (5, 5)])
async def test_search_large_assets_caps_size_and_treats_zero_as_the_default(
        fake_ctx, size, expected):
    """The other searches cap at 200, and 0 used to mean "whatever the server
    feels like" here alone. Both now read like every other page size."""
    stub = StubSizeClient()
    await server.search_large_assets(fake_ctx(stub), size=size)
    assert stub.kwargs["size"] == expected


@pytest.mark.asyncio
async def test_list_memories_always_sends_a_page_size(fake_ctx):
    """The magic-zero sentinel is gone: the default is a number like everywhere
    else, so the answer's length no longer depends on the server's mood."""
    stub = StubSizeClient()
    await server.list_memories(fake_ctx(stub))
    assert stub.kwargs["size"] == 50


# ── B4: the docstrings promise what the code delivers ────────────────────────

class StubOrderClient:
    def __init__(self):
        self.kwargs = None

    async def get_timeline_buckets(self, **kwargs):
        self.kwargs = kwargs
        return [{"timeBucket": "2026-03-01", "count": 2}]


@pytest.mark.asyncio
async def test_get_timeline_buckets_asks_for_newest_first_by_default(fake_ctx):
    """"Newest month first" was an assumption inherited from Immich's own order;
    asking for it explicitly makes the documented contract a guarantee."""
    stub = StubOrderClient()
    await server.get_timeline_buckets(fake_ctx(stub))
    assert stub.kwargs["order"] == "desc"


@pytest.mark.asyncio
async def test_get_timeline_buckets_passes_an_explicit_order_through(fake_ctx):
    stub = StubOrderClient()
    await server.get_timeline_buckets(fake_ctx(stub), order="asc")
    assert stub.kwargs["order"] == "asc"


@pytest.mark.parametrize("tool, promised", [
    (server.get_asset_info, "notes"),
    (server.create_memory, "asset_count"),
    (server.download_archive, "assets"),
    (server.get_stack, "Use this"),
])
def test_docstrings_describe_what_the_tool_actually_returns(tool, promised):
    assert promised in tool.__doc__


# ── B6: no wasted round-trip to fetch an album nobody reads ──────────────────

def test_album_assets_no_longer_takes_the_album_it_ignored():
    """The third parameter was never read, and download_archive was fetching a
    whole album just to pass it in."""
    assert _tool_parameters(_album_assets) == ["client", "album_id"]

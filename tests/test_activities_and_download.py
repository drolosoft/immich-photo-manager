"""The 2.0.4 batch, part two: album activities and download archive.

Activities are comments and likes on shared albums; download/archive turns an
album or a selection into a zip written to disk (streamed, never loaded whole
into memory, never overwriting). Both areas are identical in the Immich 2.7.5
and 3.1.0 OpenAPI specs (verified 2026-09-02).
"""

import json

import httpx
import pytest
import respx
from httpx import Response

from immich_mcp_server import server
from immich_mcp_server.immich_client import ImmichClient

BASE = "https://immich.test"


@pytest.fixture
def client():
    return ImmichClient(base_url=BASE, api_key="k")


# ── Client ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_list_activities_sends_album_and_type(client):
    route = respx.get(f"{BASE}/api/activities").mock(return_value=Response(200, json=[]))
    await client.list_activities("alb1", activity_type="comment")
    params = route.calls[0].request.url.params
    assert params["albumId"] == "alb1"
    assert params["type"] == "comment"


@pytest.mark.asyncio
@respx.mock
async def test_create_activity_posts_a_comment(client):
    route = respx.post(f"{BASE}/api/activities").mock(
        return_value=Response(201, json={"id": "act1", "type": "comment"}))
    await client.create_activity("alb1", activity_type="comment", comment="Nice one")
    body = json.loads(route.calls[0].request.content)
    assert body == {"albumId": "alb1", "type": "comment", "comment": "Nice one"}


@pytest.mark.asyncio
@respx.mock
async def test_delete_activity_calls_the_delete_endpoint(client):
    route = respx.delete(f"{BASE}/api/activities/act1").mock(return_value=Response(204))
    await client.delete_activity("act1")
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_get_download_info_posts_the_album_id(client):
    route = respx.post(f"{BASE}/api/download/info").mock(
        return_value=Response(200, json={"totalSize": 123, "archives": [{"size": 123, "assetIds": ["a1"]}]}))
    got = await client.get_download_info(album_id="alb1")
    assert json.loads(route.calls[0].request.content) == {"albumId": "alb1"}
    assert got["totalSize"] == 123


@pytest.mark.asyncio
@respx.mock
async def test_download_archive_streams_the_zip_to_disk(client, tmp_path):
    respx.post(f"{BASE}/api/download/archive").mock(
        return_value=Response(200, content=b"PK-fake-zip-bytes"))
    destination = tmp_path / "album.zip"
    written = await client.download_archive(["a1", "a2"], str(destination))
    assert destination.read_bytes() == b"PK-fake-zip-bytes"
    assert written == len(b"PK-fake-zip-bytes")
    # The temp file the chunks went through is renamed, not left beside the zip.
    assert not (tmp_path / "album.zip.part").exists()


@pytest.mark.asyncio
@respx.mock
async def test_download_archive_leaves_nothing_behind_when_the_stream_fails(
        client, tmp_path):
    """A big album can drop mid-stream. The half-written zip used to stay on
    disk, and the tool's own never-overwrite guard then told the user to pick
    another path instead of telling them the download had failed."""
    respx.post(f"{BASE}/api/download/archive").mock(
        side_effect=httpx.ReadTimeout("the connection dropped"))
    destination = tmp_path / "album.zip"

    with pytest.raises(httpx.ReadTimeout):
        await client.download_archive(["a1", "a2"], str(destination))

    assert not destination.exists()
    assert not (tmp_path / "album.zip.part").exists()


@pytest.mark.asyncio
@respx.mock
async def test_download_archive_removes_the_partial_when_immich_refuses(client, tmp_path):
    respx.post(f"{BASE}/api/download/archive").mock(return_value=Response(400))
    destination = tmp_path / "album.zip"

    with pytest.raises(httpx.HTTPStatusError):
        await client.download_archive(["a1"], str(destination))

    assert list(tmp_path.iterdir()) == []


# ── Tools ────────────────────────────────────────────────────────────────────

class StubActivitiesClient:
    def __init__(self):
        self.kwargs = None

    async def list_activities(self, album_id, **kwargs):
        self.kwargs = {"album_id": album_id, **kwargs}
        return [{"id": "act1", "type": "comment", "comment": "Nice one",
                 "assetId": None, "createdAt": "2026-09-02T10:00:00Z",
                 "user": {"id": "u1", "name": "Lab", "email": "lab@example.com"}}]

    async def create_activity(self, album_id, **kwargs):
        self.kwargs = {"album_id": album_id, **kwargs}
        return {"id": "act9", "type": kwargs.get("activity_type")}

    async def delete_activity(self, activity_id):
        self.kwargs = {"activity_id": activity_id}


@pytest.mark.asyncio
async def test_list_activities_tool_trims_user_to_a_name(fake_ctx):
    raw = await server.list_activities(fake_ctx(StubActivitiesClient()), album_id="alb1")
    activity = json.loads(raw)["activities"][0]
    assert activity == {"id": "act1", "type": "comment", "comment": "Nice one",
                        "asset_id": None, "user": "Lab", "created_at": "2026-09-02T10:00:00Z"}


@pytest.mark.asyncio
async def test_create_activity_tool_defaults_to_a_comment(fake_ctx):
    stub = StubActivitiesClient()
    raw = await server.create_activity(fake_ctx(stub), album_id="alb1", comment="Nice one")
    assert stub.kwargs["activity_type"] == "comment"
    assert stub.kwargs["comment"] == "Nice one"
    assert json.loads(raw)["id"] == "act9"


@pytest.mark.asyncio
async def test_create_activity_tool_sends_a_like_without_text(fake_ctx):
    stub = StubActivitiesClient()
    await server.create_activity(fake_ctx(stub), album_id="alb1", like=True)
    assert stub.kwargs["activity_type"] == "like"
    assert stub.kwargs["comment"] is None


@pytest.mark.asyncio
async def test_delete_activity_tool_reports_success(fake_ctx):
    stub = StubActivitiesClient()
    raw = await server.delete_activity(fake_ctx(stub), activity_id="act1")
    assert stub.kwargs == {"activity_id": "act1"}
    assert json.loads(raw)["success"] is True


class StubDownloadClient:
    def __init__(self):
        self.kwargs = None
        self.archive_ids = None
        self.albums_fetched = []

    async def get_download_info(self, album_id=None, asset_ids=None):
        self.kwargs = {"album_id": album_id, "asset_ids": asset_ids}
        return {"totalSize": 2048, "archives": [{"size": 2048, "assetIds": ["a1", "a2"]}]}

    async def get_album(self, album_id):
        self.albums_fetched.append(album_id)
        return {"id": album_id, "albumName": "Lab Album"}

    async def get_album_assets(self, album_id, limit=None, with_exif=False):
        return [{"id": "a1"}, {"id": "a2"}]

    async def download_archive(self, asset_ids, destination):
        self.archive_ids = asset_ids
        with open(destination, "wb") as handle:
            handle.write(b"PK-fake")
        return 7


@pytest.mark.asyncio
async def test_get_download_info_tool_reports_size_and_count(fake_ctx):
    stub = StubDownloadClient()
    raw = await server.get_download_info(fake_ctx(stub), album_id="alb1")
    result = json.loads(raw)
    assert stub.kwargs == {"album_id": "alb1", "asset_ids": None}
    assert result["total_size_mb"] == round(2048 / 1024 / 1024, 2)
    assert result["asset_count"] == 2


@pytest.mark.asyncio
async def test_download_archive_tool_resolves_an_album_to_asset_ids(fake_ctx, tmp_path):
    stub = StubDownloadClient()
    destination = tmp_path / "lab.zip"
    raw = await server.download_archive(
        fake_ctx(stub), album_id="alb1", output_path=str(destination))
    result = json.loads(raw)
    assert stub.archive_ids == ["a1", "a2"]
    assert result["path"] == str(destination)
    assert destination.read_bytes() == b"PK-fake"


@pytest.mark.asyncio
async def test_download_archive_tool_never_overwrites(fake_ctx, tmp_path):
    destination = tmp_path / "lab.zip"
    destination.write_bytes(b"precious")
    raw = await server.download_archive(
        fake_ctx(StubDownloadClient()), album_id="alb1", output_path=str(destination))
    result = json.loads(raw)
    assert "error" in result
    assert destination.read_bytes() == b"precious"


@pytest.mark.asyncio
async def test_download_archive_tool_requires_album_or_ids(fake_ctx, tmp_path):
    raw = await server.download_archive(
        fake_ctx(StubDownloadClient()), output_path=str(tmp_path / "x.zip"))
    assert "error" in json.loads(raw)


@pytest.mark.asyncio
async def test_get_download_info_tool_requires_album_or_ids(fake_ctx):
    """The pair is meant to be called in sequence, so the twin that sizes the
    archive refuses the same empty request the one that builds it refuses."""
    stub = StubDownloadClient()
    raw = await server.get_download_info(fake_ctx(stub))
    assert "error" in json.loads(raw)
    assert stub.kwargs is None


@pytest.mark.asyncio
async def test_download_archive_tool_resolves_an_album_without_fetching_it(
        fake_ctx, tmp_path):
    """The album object was fetched only to be handed to a helper that ignored
    it, so an album download cost one pointless request."""
    stub = StubDownloadClient()
    await server.download_archive(
        fake_ctx(stub), album_id="alb1", output_path=str(tmp_path / "lab.zip"))
    assert stub.albums_fetched == []

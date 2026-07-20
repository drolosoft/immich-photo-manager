"""rotate_assets must never destroy non-rotation edits (crop, mirror).

Regression tests for the bug where reaching a cumulative 360° called
delete_asset_edits (removing ALL edits, crop included) and every
rotation PUT a rotation-only edit list, replacing existing edits.
"""

import json

import httpx
import pytest

from immich_mcp_server import server


CROP = {"action": "crop", "parameters": {"x": 10, "y": 10, "w": 100, "h": 100}}


def _rotate(angle):
    return {"action": "rotate", "parameters": {"angle": angle}}


def _http_error(status):
    request = httpx.Request("GET", "https://immich.test/api/assets/a1/edits")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


class StubClient:
    """Records edit calls; configurable get_asset_edits behaviour."""

    def __init__(self, edits=None, get_error=None):
        self._edits = edits or []
        self._get_error = get_error
        self.applied: list[tuple[str, list]] = []
        self.deleted: list[str] = []

    async def get_asset_edits(self, asset_id):
        if self._get_error:
            raise self._get_error
        return {"edits": self._edits}

    async def apply_asset_edits(self, asset_id, edits):
        self.applied.append((asset_id, edits))
        return {}

    async def delete_asset_edits(self, asset_id):
        self.deleted.append(asset_id)


async def rotate(client, fake_ctx, angle=90):
    ctx = fake_ctx(client)
    return json.loads(
        await server.rotate_assets(ctx, angle=angle, asset_ids=["a1"])
    )


@pytest.mark.asyncio
async def test_full_circle_keeps_crop(fake_ctx):
    """crop + rotate(270), rotated 90 more: rotation completes the circle
    and must disappear — but the crop must survive."""
    client = StubClient(edits=[CROP, _rotate(270)])

    result = await rotate(client, fake_ctx, angle=90)

    assert result["rotated"] == 1
    assert client.deleted == []  # delete would wipe the crop
    assert client.applied == [("a1", [CROP])]


@pytest.mark.asyncio
async def test_rotation_preserves_existing_crop(fake_ctx):
    client = StubClient(edits=[CROP])

    await rotate(client, fake_ctx, angle=90)

    assert client.applied == [("a1", [CROP, _rotate(90)])]


@pytest.mark.asyncio
async def test_full_circle_with_only_rotation_deletes_edits(fake_ctx):
    client = StubClient(edits=[_rotate(180)])

    result = await rotate(client, fake_ctx, angle=180)

    assert result["rotated"] == 1
    assert client.deleted == ["a1"]
    assert client.applied == []


@pytest.mark.asyncio
async def test_rotation_accumulates(fake_ctx):
    client = StubClient(edits=[_rotate(90)])

    await rotate(client, fake_ctx, angle=90)

    assert client.applied == [("a1", [_rotate(180)])]


@pytest.mark.asyncio
async def test_missing_edits_404_means_no_edits(fake_ctx):
    client = StubClient(get_error=_http_error(404))

    result = await rotate(client, fake_ctx, angle=90)

    assert result["rotated"] == 1
    assert client.applied == [("a1", [_rotate(90)])]


@pytest.mark.asyncio
async def test_unreadable_edits_fails_the_asset_instead_of_resetting(fake_ctx):
    """A transient 500 reading edits must NOT silently reset the angle
    to 0 and apply a wrong rotation — the asset fails cleanly."""
    client = StubClient(get_error=_http_error(500))

    result = await rotate(client, fake_ctx, angle=90)

    assert result["failed"] == 1
    assert result["rotated"] == 0
    assert client.applied == []
    assert client.deleted == []

"""The image-block tools return MCP Images, and the base64/JSON tools stay put.

get_asset_image / get_album_images / get_images_batch are an additive, opt-in
view for clients that render images inline (Open WebUI, Claude Desktop). The
original get_*_thumbnail(s) tools MUST keep returning base64 JSON strings — the
skills embed those as data: URIs into self-contained HTML galleries, so any
change to their return contract would break Cowork/Claude Desktop/Code.
"""

import base64
import json

import pytest
from mcp.server.mcpserver import Image

from immich_mcp_server import server


PNG = b"\x89PNG\r\n\x1a\n"  # arbitrary bytes standing in for image content
PNG_B64 = base64.b64encode(PNG).decode("ascii")


class StubClient:
    """Returns thumbnail dicts in the exact shape ImmichClient produces."""

    async def get_asset_thumbnail(self, asset_id, size="thumbnail"):
        return {"data": PNG_B64, "type": "image/png"}

    async def get_album_thumbnails(self, album_id, size="thumbnail", limit=50):
        return {
            "albumName": "Trip",
            "thumbnails": [
                {"id": "a1", "data": PNG_B64, "type": "image/png",
                 "originalFileName": "1.png", "fileCreatedAt": "2026-01-01"},
                {"id": "a2", "data": PNG_B64, "type": "image/jpeg",
                 "originalFileName": "2.jpg", "fileCreatedAt": "2026-01-02"},
            ],
        }

    async def get_thumbnails_batch(self, asset_ids, size="thumbnail", limit=50):
        return {"thumbnails": [{"id": asset_id, "data": PNG_B64, "type": "image/png"} for asset_id in asset_ids]}


# ── the new image-block tools ───────────────────────────────


@pytest.mark.asyncio
async def test_get_asset_image_returns_image_block(fake_ctx):
    result = await server.get_asset_image(fake_ctx(StubClient()), asset_id="a1")

    assert isinstance(result, Image)
    assert result.data == PNG  # base64 decoded back to the raw bytes
    assert result.to_image_content().mime_type == "image/png"


@pytest.mark.asyncio
async def test_get_album_images_returns_list_of_images(fake_ctx):
    result = await server.get_album_images(fake_ctx(StubClient()), album_id="alb1")

    assert isinstance(result, list)
    assert [type(item) for item in result] == [Image, Image]
    assert all(item.data == PNG for item in result)


@pytest.mark.asyncio
async def test_get_images_batch_returns_one_image_per_id(fake_ctx):
    result = await server.get_images_batch(fake_ctx(StubClient()), asset_ids=["a1", "a2", "a3"])

    assert len(result) == 3
    assert all(isinstance(item, Image) for item in result)


# ── the base64/JSON tools MUST NOT change (regression guard) ─


@pytest.mark.asyncio
async def test_get_asset_thumbnail_still_returns_base64_json(fake_ctx):
    result = await server.get_asset_thumbnail(fake_ctx(StubClient()), asset_id="a1")

    assert isinstance(result, str)  # a JSON string, not an Image
    assert json.loads(result) == {"data": PNG_B64, "type": "image/png"}


@pytest.mark.asyncio
async def test_batch_thumbnail_tools_still_return_json_with_metadata(fake_ctx):
    album = await server.get_album_thumbnails(fake_ctx(StubClient()), album_id="alb1")
    batch = await server.get_thumbnails_batch(fake_ctx(StubClient()), asset_ids=["a1"])

    for raw in (album, batch):
        assert isinstance(raw, str)
    # metadata the gallery templates rely on survives (asset id, base64 data)
    parsed = json.loads(album)
    assert parsed["thumbnails"][0]["id"] == "a1"
    assert parsed["thumbnails"][0]["data"] == PNG_B64


# ── MIME → format mapping ───────────────────────────────────


@pytest.mark.parametrize("mime,fmt", [
    ("image/jpeg", "jpeg"),
    ("image/jpg", "jpeg"),
    ("image/png", "png"),
    ("image/webp", "webp"),
    ("image/heic", "heic"),
    ("image/heif", "heic"),
    ("image/gif; charset=binary", "gif"),  # parameters are stripped
    ("", "jpeg"),                            # empty falls back to jpeg
    ("application/octet-stream", "jpeg"),    # unknown falls back to jpeg
])
def test_image_format_from_mime(mime, fmt):
    assert server._image_format_from_mime(mime) == fmt

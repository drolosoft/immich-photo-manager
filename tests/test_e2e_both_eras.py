"""End-to-end: the skills' critical tool flows, over the wire, on both MCP eras
and both transports, against a fake Immich API.

Matrix: {stdio, streamable-http} x {legacy handshake, 2026-07-28 stateless}.
Each cell boots the real packaged server as a subprocess, points it at
tests/fake_immich.py, and checks the exact payloads the skills consume:
base64 JSON thumbnails (with asset id / filename / date), image blocks, album
listing, metadata search. Also runs legacy and modern clients concurrently
against one HTTP server, since a stateless server must not confuse the two.
"""

import asyncio
import base64
import json
import os
import socket
import subprocess
import sys
import time

import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters, stdio_client

from tool_manifest import TOOL_NAMES

from fake_immich import API_KEY, PNG, FakeImmich

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
# "auto" probes server/discover for real before falling back, so keeping it
# here is the only SDK-driven discover exercised over stdio.
MODES = ["legacy", "2026-07-28", "auto"]
PNG_B64 = base64.b64encode(PNG).decode("ascii")


# ── server bootstrapping ────────────────────────────────────


def _env(immich_url):
    return {**os.environ, "PYTHONPATH": SRC, "IMMICH_BASE_URL": immich_url, "IMMICH_API_KEY": API_KEY}


def _stdio(immich_url):
    return stdio_client(StdioServerParameters(
        command=sys.executable, args=["-m", "immich_mcp_server", "--transport", "stdio"], env=_env(immich_url)))


class HttpServer:
    """Real `python -m immich_mcp_server --transport http` on a free port."""

    def __init__(self, immich_url):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}/mcp"
        self.env = {**_env(immich_url), "MCP_HOST": "127.0.0.1", "MCP_PORT": str(self.port)}

    def __enter__(self):
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "immich_mcp_server", "--transport", "http"],
            env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            with socket.socket() as s:
                s.settimeout(0.2)
                if s.connect_ex(("127.0.0.1", self.port)) == 0:
                    return self
            if self.proc.poll() is not None:
                raise RuntimeError(f"server died: {self.proc.stderr.read()}")
            time.sleep(0.1)
        raise RuntimeError("http server did not come up")

    def __exit__(self, *exc):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
        if self.proc.stderr:
            self.proc.stderr.close()


@pytest.fixture(scope="module")
def immich():
    with FakeImmich() as f:
        yield f


@pytest.fixture(scope="module")
def http_server(immich):
    with HttpServer(immich.base_url) as s:
        yield s


# ── the flows the skills depend on ──────────────────────────


async def _text(client, name, args=None):
    r = await client.call_tool(name, args or {})
    assert not r.is_error, r
    return json.loads(next(b.text for b in r.content if b.type == "text"))


async def exercise_skill_flows(client):
    # health
    assert (await _text(client, "ping")) == {"res": "pong"}

    # photo-search skill: metadata search -> asset ids
    found = await _text(client, "search_metadata", {"city": "Lanzarote"})
    ids = [a["id"] for a in found["assets"]]
    assert ids == ["a1", "a2"] and found["total"] == 2

    # gallery generation (album-manager / photo-search): base64 JSON with metadata
    batch = await _text(client, "get_thumbnails_batch", {"asset_ids": ids, "size": "thumbnail", "limit": 50})
    assert [t["id"] for t in batch["thumbnails"]] == ["a1", "a2"]
    for t in batch["thumbnails"]:
        assert base64.b64decode(t["data"]) == PNG          # bytes intact through the wire
        assert t["type"] == "image/png"
        assert t["originalFileName"].endswith(".png")      # template needs name + date
        assert t["fileCreatedAt"].startswith("2026-06-")

    # album-manager: album listing + album thumbnails
    albums = await _text(client, "list_albums")
    assert albums["albums"][0]["albumName"] == "Lanzarote 2026"
    alb = await _text(client, "get_album_thumbnails", {"album_id": "alb1"})
    assert alb["albumName"] == "Lanzarote 2026" and len(alb["thumbnails"]) == 2

    # image-block tools (Open WebUI / Desktop inline rendering)
    r = await client.call_tool("get_asset_image", {"asset_id": "a1"})
    img = next(b for b in r.content if b.type == "image")
    assert img.mime_type == "image/png" and img.data == PNG_B64
    r = await client.call_tool("get_images_batch", {"asset_ids": ids})
    assert sum(1 for b in r.content if b.type == "image") == 2

    # tool surface
    tools = await client.list_tools()
    assert {tool.name for tool in tools.tools} == set(TOOL_NAMES)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.asyncio
async def test_stdio_skill_flows(immich, mode):
    async with Client(_stdio(immich.base_url), mode=mode) as client:
        expected = "2025-11-25" if mode == "legacy" else "2026-07-28"
        assert client.protocol_version == expected
        await exercise_skill_flows(client)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.asyncio
async def test_http_skill_flows(http_server, mode):
    async with Client(http_server.url, mode=mode) as client:
        expected = "2025-11-25" if mode == "legacy" else "2026-07-28"
        assert client.protocol_version == expected
        await exercise_skill_flows(client)


@pytest.mark.asyncio
async def test_http_legacy_and_modern_clients_concurrently(http_server):
    """A dual-era HTTP server must serve a legacy session and stateless modern
    requests at the same time without cross-talk."""

    async def hammer(mode, n=8):
        async with Client(http_server.url, mode=mode) as c:
            results = await asyncio.gather(*[_text(c, "get_statistics") for _ in range(n)])
            assert all(r["photos"] == 2 for r in results)
            return c.protocol_version

    versions = await asyncio.gather(
        hammer("legacy"), hammer("2026-07-28"), hammer("legacy"), hammer("2026-07-28"), hammer("auto"),
    )
    assert versions == ["2025-11-25", "2026-07-28", "2025-11-25", "2026-07-28", "2026-07-28"]


@pytest.mark.asyncio
async def test_bad_api_key_surfaces_as_tool_error_not_crash(immich):
    """Auth failures must come back as tool errors on both eras, not kill the server."""
    for mode in MODES:
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "immich_mcp_server", "--transport", "stdio"],
            env={**_env(immich.base_url), "IMMICH_API_KEY": "wrong"})
        async with Client(stdio_client(params), mode=mode) as client:
            r = await client.call_tool("get_statistics", {})
            assert r.is_error or "401" in json.dumps([b.model_dump() for b in r.content])
            # server still alive afterwards
            assert {tool.name for tool in (await client.list_tools()).tools} == set(TOOL_NAMES)

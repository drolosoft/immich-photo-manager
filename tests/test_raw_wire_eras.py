"""
Era compatibility proven on the raw wire, with no SDK on the client side.

Every other era test drives the server through the same SDK the server runs
on, so a shared-code regression could change sender and expectation
symmetrically and stay green. Here the client is hand-rolled JSON-RPC over
the real stdio subprocess: these tests only pass if the bytes on the wire are
right, whatever either SDK does. They are also the arbiter for any future SDK
migration — they must pass unchanged.

Legacy era: the full `initialize` handshake at every revision real clients
speak (Claude Desktop, Cowork, Claude Code), exact version echo, and a real
tools/call. Modern era (2026-07-28): no handshake, the per-request `_meta`
envelope built by hand, a real `server/discover`, and the required-key error.
"""

import json
import os
import subprocess
import sys

import pytest

from immich_mcp_server import __version__

from tool_manifest import TOOL_NAMES

# The four revisions that negotiate via `initialize`. 2025-11-25 is what
# current Claude clients send; the older three must keep working because the
# spec's compat matrix says a server supports every revision it ever spoke.
HANDSHAKE_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")

# What an unknown offer must be countered with: the newest handshake revision.
LATEST_HANDSHAKE = "2025-11-25"

MODERN = "2026-07-28"

# Spec-reserved envelope keys carried in params._meta on every modern request.
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"


class RawStdioServer:
    """The real server as a subprocess, driven with hand-written JSON lines."""

    def __init__(self, cache_dir):
        # An unroutable Immich URL makes the startup ping fail fast; the
        # server must still serve MCP. The private cache dir keeps the
        # developer's real cached credentials out of the test.
        env = {
            **os.environ,
            "MCP_TRANSPORT": "stdio",
            "IMMICH_BASE_URL": "http://127.0.0.1:9",
            "IMMICH_API_KEY": "raw-wire-test",
            "IMMICH_CACHE_DIR": str(cache_dir),
        }
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "immich_mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
        )
        self.next_id = 0

    def close(self):
        self.proc.stdin.close()
        self.proc.stdout.close()
        self.proc.wait(timeout=10)

    def notify(self, method, params=None):
        frame = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            frame["params"] = params
        self.proc.stdin.write(json.dumps(frame) + "\n")
        self.proc.stdin.flush()

    def request(self, method, params=None):
        """Send one request and return its raw JSON-RPC response object."""
        self.next_id += 1
        frame = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            frame["params"] = params
        self.proc.stdin.write(json.dumps(frame) + "\n")
        self.proc.stdin.flush()

        # Read until the response with our id; the server may interleave
        # notifications (log messages), which a raw client must tolerate.
        while True:
            line = self.proc.stdout.readline()
            assert line, f"server closed the stream before answering {method}"
            message = json.loads(line)
            if message.get("id") == self.next_id:
                return message


@pytest.fixture
def raw_server(tmp_path):
    server = RawStdioServer(tmp_path)
    yield server
    server.close()


def envelope(extra=None):
    """A modern request's params._meta, built by hand."""
    meta = {VERSION_KEY: MODERN, CAPABILITIES_KEY: {}}
    if extra:
        meta.update(extra)
    return meta


# ── Legacy era: the initialize handshake, all four revisions ──────


@pytest.mark.parametrize("version", HANDSHAKE_VERSIONS)
def test_legacy_handshake_echoes_the_offered_version(raw_server, version):
    response = raw_server.request(
        "initialize",
        {
            "protocolVersion": version,
            "capabilities": {},
            "clientInfo": {"name": "raw-wire-test", "version": "0"},
        },
    )

    result = response["result"]
    assert result["protocolVersion"] == version
    assert result["serverInfo"]["name"] == "immich-photo-manager"
    assert result["serverInfo"]["version"] == __version__

    raw_server.notify("notifications/initialized")

    listing = raw_server.request("tools/list")
    names = {tool["name"] for tool in listing["result"]["tools"]}
    assert names == set(TOOL_NAMES)

    call = raw_server.request(
        "tools/call", {"name": "get_connection_info", "arguments": {}}
    )
    assert "result" in call, call.get("error")


def test_legacy_handshake_counters_an_unknown_version(raw_server):
    response = raw_server.request(
        "initialize",
        {
            "protocolVersion": "2099-01-01",
            "capabilities": {},
            "clientInfo": {"name": "raw-wire-test", "version": "0"},
        },
    )

    assert response["result"]["protocolVersion"] == LATEST_HANDSHAKE


# ── Modern era: no handshake, the _meta envelope on every request ──────


def test_modern_discover_names_exactly_the_modern_version(raw_server):
    response = raw_server.request("server/discover", {"_meta": envelope()})

    result = response["result"]
    assert result["supportedVersions"] == [MODERN]
    assert result["resultType"] == "complete"


def test_modern_tools_list_serves_the_full_surface(raw_server):
    response = raw_server.request("tools/list", {"_meta": envelope()})

    names = {tool["name"] for tool in response["result"]["tools"]}
    assert names == set(TOOL_NAMES)


def test_modern_tools_call_works_without_any_handshake(raw_server):
    response = raw_server.request(
        "tools/call",
        {"name": "get_connection_info", "arguments": {}, "_meta": envelope()},
    )

    assert "result" in response, response.get("error")


def test_modern_envelope_missing_capabilities_is_invalid_params(raw_server):
    response = raw_server.request(
        "tools/list", {"_meta": {VERSION_KEY: MODERN}}
    )

    error = response["error"]
    assert error["code"] == -32602
    assert CAPABILITIES_KEY in error["message"]


def test_full_tool_definitions_are_identical_across_eras(tmp_path):
    """The whole definition must match between eras, not just the names."""

    def definitions(listing):
        return {
            tool["name"]: (
                tool.get("description"),
                json.dumps(tool.get("inputSchema"), sort_keys=True),
                json.dumps(tool.get("outputSchema"), sort_keys=True),
            )
            for tool in listing["result"]["tools"]
        }

    legacy = RawStdioServer(tmp_path / "legacy")
    try:
        legacy.request(
            "initialize",
            {
                "protocolVersion": LATEST_HANDSHAKE,
                "capabilities": {},
                "clientInfo": {"name": "raw-wire-test", "version": "0"},
            },
        )
        legacy.notify("notifications/initialized")
        legacy_definitions = definitions(legacy.request("tools/list"))
    finally:
        legacy.close()

    modern = RawStdioServer(tmp_path / "modern")
    try:
        modern_definitions = definitions(
            modern.request("tools/list", {"_meta": envelope()})
        )
    finally:
        modern.close()

    assert legacy_definitions == modern_definitions

"""
What the Claude directory reads from the plugin: the manifest, the MCP server
entry, and the launcher they point at.

The directory's checks hold a plugin for a reviewer when the server command is
not a file inside the plugin, and they block credentials that do not come
through `userConfig`. These tests keep both in the shape the checks accept and
prove that the launcher file really serves MCP over stdio, with no PYTHONPATH
and no credentials in its environment, which is exactly how Claude Code starts
it before the user has configured anything.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tool_manifest import TOOL_NAMES

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MCP_JSON = REPO_ROOT / ".claude-plugin" / "mcp.json"
LAUNCHER = REPO_ROOT / "src" / "plugin_entry.py"

# The directory requires a path written in full from the plugin root.
PLUGIN_ROOT_VARIABLE = "${CLAUDE_PLUGIN_ROOT}"

# A `${user_config.KEY}` reference as Claude Code substitutes it.
USER_CONFIG_REFERENCE = re.compile(r"^\$\{user_config\.([A-Za-z_][A-Za-z0-9_]*)\}$")


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def manifest():
    return load(PLUGIN_JSON)


@pytest.fixture(scope="module")
def server_entry():
    servers = load(MCP_JSON)["mcpServers"]
    assert list(servers) == ["immich"]
    return servers["immich"]


# ── The server command ────────────────────────────────────────────


def test_the_server_runs_a_file_inside_the_plugin_with_plain_arguments(server_entry):
    assert server_entry["command"] == "python3"
    assert server_entry["args"] == [f"{PLUGIN_ROOT_VARIABLE}/src/plugin_entry.py"]
    assert LAUNCHER.is_file()


def test_the_server_needs_no_pythonpath_from_the_manifest(server_entry):
    # The launcher puts `src/` on sys.path itself; a PYTHONPATH in the manifest
    # was one more variable the directory's validator had to follow.
    assert "PYTHONPATH" not in server_entry["env"]


# ── Credentials through userConfig ────────────────────────────────


def test_credentials_are_asked_through_user_config(manifest, server_entry):
    options = manifest["userConfig"]
    assert server_entry["env"]["IMMICH_BASE_URL"] == "${user_config.immich_base_url}"
    assert server_entry["env"]["IMMICH_API_KEY"] == "${user_config.immich_api_key}"
    assert options["immich_api_key"]["sensitive"] is True
    assert options["immich_base_url"].get("sensitive", False) is False


def test_every_user_config_reference_is_declared(manifest, server_entry):
    declared = set(manifest["userConfig"])
    for value in server_entry["env"].values():
        match = USER_CONFIG_REFERENCE.match(value)
        if match:
            assert match.group(1) in declared, value


def test_user_config_options_have_the_fields_claude_code_requires(manifest):
    for key, option in manifest["userConfig"].items():
        assert option["type"] == "string", key
        assert option["title"], key
        assert option["description"], key


def test_user_config_options_keep_a_default_so_cowork_starts_the_server(manifest):
    # Cowork ignores a server whose referenced option has no default and never
    # prompts for one. An empty default lets it start credential-less, where
    # the setup command and update_credentials take over as before.
    for key, option in manifest["userConfig"].items():
        assert option["default"] == "", key


def test_no_placeholder_host_or_key_is_left_in_the_manifest(server_entry):
    for value in server_entry["env"].values():
        assert "your-" not in value, value


# ── The launcher on the wire ──────────────────────────────────────


def test_the_launcher_serves_mcp_over_stdio_without_credentials(tmp_path):
    """Started the way Claude Code starts it before any configuration: by file
    path, no PYTHONPATH, every credential variable absent or unsubstituted."""
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in ("PYTHONPATH", "IMMICH_BASE_URL", "IMMICH_API_KEY")
    }
    env["IMMICH_CACHE_DIR"] = str(tmp_path / "mcpb-cache")
    env["IMMICH_CONFIG_HOME"] = str(tmp_path / "config-home")
    env["IMMICH_API_KEY"] = "${user_config.immich_api_key}"

    proc = subprocess.Popen(
        [sys.executable, str(LAUNCHER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
        text=True,
    )
    try:
        handshake = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "directory-check", "version": "0"},
            },
        }
        proc.stdin.write(json.dumps(handshake) + "\n")
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n")
        proc.stdin.flush()

        answers = {}
        while len(answers) < 2:
            line = proc.stdout.readline()
            assert line, "the launcher closed the stream before answering"
            message = json.loads(line)
            if "id" in message:
                answers[message["id"]] = message
    finally:
        proc.stdin.close()
        proc.stdout.close()
        proc.wait(timeout=10)

    assert answers[1]["result"]["protocolVersion"] == "2025-11-25"
    served = {tool["name"] for tool in answers[2]["result"]["tools"]}
    assert served == set(TOOL_NAMES)

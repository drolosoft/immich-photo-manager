"""The stdio transport owns stdout: nothing but JSON-RPC may be printed.

Regression test for the startup warning being print()ed to stdout when
Immich is unreachable — exactly the moment a strict MCP client would
choke on the corrupted stream.
"""

import pytest

from immich_mcp_server.server import app_lifespan


@pytest.mark.asyncio
async def test_startup_warning_never_touches_stdout(
    isolated_cache, monkeypatch, capsys
):
    monkeypatch.setenv("IMMICH_BASE_URL", "http://127.0.0.1:59999")
    monkeypatch.setenv("IMMICH_API_KEY", "dummy")

    async with app_lifespan(None):
        pass

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Could not connect" in captured.err


@pytest.mark.asyncio
async def test_server_starts_without_credentials_and_warns(
    isolated_cache, monkeypatch, capsys
):
    """A container (or first run) with no credentials must still serve: /health
    has to answer and update_credentials has to be reachable. The old behavior
    raised in the lifespan and killed the whole server at startup."""
    monkeypatch.delenv("IMMICH_BASE_URL", raising=False)
    monkeypatch.delenv("IMMICH_API_KEY", raising=False)

    async with app_lifespan(None) as context:
        assert context["immich"] is None

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "update_credentials" in captured.err


@pytest.mark.asyncio
async def test_client_helper_names_the_fix_when_credentials_are_missing(fake_ctx):
    from mcp.server.mcpserver.exceptions import ToolError

    from immich_mcp_server.app import _client

    # ToolError is the SDK's anticipated-failure channel: its message reaches
    # the model inside the tool result instead of a generic execution error.
    with pytest.raises(ToolError) as exc_info:
        _client(fake_ctx(None))
    assert "update_credentials" in str(exc_info.value)

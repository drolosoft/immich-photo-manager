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

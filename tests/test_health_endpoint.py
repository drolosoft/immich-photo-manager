"""The /health endpoint of the HTTP app (Docker HEALTHCHECK and orchestrators).

It must answer without credentials, without an MCP handshake and without
touching Immich: a container is "healthy" when the server process serves HTTP,
not when the photo library is reachable.
"""

import httpx
import pytest

from immich_mcp_server import __version__, server


@pytest.mark.asyncio
async def test_health_endpoint_reports_ok_and_version():
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


@pytest.mark.asyncio
async def test_health_endpoint_needs_no_api_key_header(monkeypatch):
    monkeypatch.delenv("IMMICH_API_KEY", raising=False)
    monkeypatch.delenv("IMMICH_BASE_URL", raising=False)
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.get("/health")
    assert response.status_code == 200

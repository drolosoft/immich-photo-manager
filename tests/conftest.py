"""Shared fixtures for the immich-photo-manager test suite.

The suite runs fully offline: HTTP is mocked with respx and the Immich
client is exercised against stub objects. No Immich instance is needed.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from immich_mcp_server.immich_client import ImmichClient  # noqa: E402


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Point the credential cache at a fresh temp dir and reset the
    class-level cache-dir memo so tests never see each other's config."""
    cache_dir = tmp_path / "mcpb-cache"
    monkeypatch.setenv("IMMICH_CACHE_DIR", str(cache_dir))
    ImmichClient._cache_dir = None
    yield cache_dir
    ImmichClient._cache_dir = None


@pytest.fixture
def env_credentials(monkeypatch):
    """Baseline env credentials so ImmichClient() can construct."""
    monkeypatch.setenv("IMMICH_BASE_URL", "https://env.example.com")
    monkeypatch.setenv("IMMICH_API_KEY", "env-key")


class FakeRequestContext:
    def __init__(self, client):
        self.lifespan_context = {"immich": client}


class FakeContext:
    """Minimal stand-in for mcp Context: just the lifespan container."""

    def __init__(self, client):
        self.request_context = FakeRequestContext(client)


@pytest.fixture
def fake_ctx():
    return FakeContext

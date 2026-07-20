"""Credential handling: explicit args must beat the config.json override.

Regression tests for the rotation bug where update_credentials validated
and hot-swapped the OLD credentials whenever a config.json already
existed (config had precedence over the env vars the tool set).
"""

import json
import os

import httpx
import pytest
import respx

from immich_mcp_server.immich_client import ImmichClient
from immich_mcp_server import server


NEW_URL = "https://new.example.com"
NEW_KEY = "new-key"
OLD_URL = "https://old.example.com"
OLD_KEY = "old-key"


def test_explicit_credentials_beat_config_override(isolated_cache):
    ImmichClient.save_config(OLD_URL, OLD_KEY)

    client = ImmichClient(base_url=NEW_URL, api_key=NEW_KEY)

    assert client.base_url == NEW_URL
    assert client.api_key == NEW_KEY


def test_default_construction_still_reads_config(isolated_cache, env_credentials):
    ImmichClient.save_config(OLD_URL, OLD_KEY)

    client = ImmichClient()

    assert client.base_url == OLD_URL
    assert client.api_key == OLD_KEY


def _mock_immich(url):
    respx.get(f"{url}/api/server/ping").mock(
        return_value=httpx.Response(200, json={"res": "pong"})
    )
    respx.get(f"{url}/api/server/statistics").mock(
        return_value=httpx.Response(200, json={"photos": 7, "videos": 2})
    )


@pytest.mark.asyncio
@respx.mock
async def test_update_credentials_swaps_in_the_new_credentials(
    isolated_cache, env_credentials, fake_ctx
):
    """With an existing config.json (a previous rotation), rotating again
    must validate and hot-swap the NEW credentials, not the old ones."""
    ImmichClient.save_config(OLD_URL, OLD_KEY)
    _mock_immich(OLD_URL)  # old server also answers — the bug passes silently
    _mock_immich(NEW_URL)

    old_client = ImmichClient()
    ctx = fake_ctx(old_client)

    result = json.loads(await server.update_credentials(ctx, NEW_URL, NEW_KEY))

    assert result["success"] is True
    live = ctx.request_context.lifespan_context["immich"]
    assert live.base_url == NEW_URL
    assert live.api_key == NEW_KEY
    # And the persisted config now carries the new credentials
    with open(isolated_cache / "config.json") as f:
        persisted = json.load(f)
    assert persisted == {"base_url": NEW_URL, "api_key": NEW_KEY}


@pytest.mark.asyncio
@respx.mock
async def test_update_credentials_does_not_mutate_environment(
    isolated_cache, env_credentials, fake_ctx
):
    _mock_immich(NEW_URL)
    old_client = ImmichClient(base_url=OLD_URL, api_key=OLD_KEY)
    ctx = fake_ctx(old_client)

    await server.update_credentials(ctx, NEW_URL, NEW_KEY)

    assert os.environ["IMMICH_BASE_URL"] == "https://env.example.com"
    assert os.environ["IMMICH_API_KEY"] == "env-key"


@pytest.mark.asyncio
@respx.mock
async def test_update_credentials_rejects_unreachable_server(
    isolated_cache, env_credentials, fake_ctx
):
    respx.get(f"{NEW_URL}/api/server/ping").mock(side_effect=httpx.ConnectError)
    old_client = ImmichClient(base_url=OLD_URL, api_key=OLD_KEY)
    ctx = fake_ctx(old_client)

    result = json.loads(await server.update_credentials(ctx, NEW_URL, NEW_KEY))

    assert result["success"] is False
    assert ctx.request_context.lifespan_context["immich"] is old_client

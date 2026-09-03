"""Credential handling: explicit args must beat the config.json override, and
saved credentials must survive a plugin update.

Regression tests for the rotation bug where update_credentials validated
and hot-swapped the OLD credentials whenever a config.json already
existed (config had precedence over the env vars the tool set).

And for the update bug: the plugin's mcp.json points IMMICH_CACHE_DIR at a
directory whose path carries the plugin version, so credentials written only
there vanished the moment a new version was installed — while the README
promised they carry over. They are now written to a stable per-user path as
well, and read from there whenever the cache dir is still empty.
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


def _stable_config(tmp_path):
    """The update-proof copy the isolated_cache fixture redirects to."""
    return tmp_path / "config-home" / "config.json"


def test_save_config_also_writes_the_update_proof_copy(isolated_cache, tmp_path):
    ImmichClient.save_config(OLD_URL, OLD_KEY)

    saved = {"base_url": OLD_URL, "api_key": OLD_KEY}
    assert json.loads((isolated_cache / "config.json").read_text()) == saved
    assert json.loads(_stable_config(tmp_path).read_text()) == saved


def test_credentials_survive_a_cache_dir_that_moved(isolated_cache, tmp_path,
                                                    monkeypatch):
    """What a plugin update looks like from here: the same stable file, a cache
    directory that has never been written to. The user must not have to re-enter
    an API key that is still valid."""
    ImmichClient.save_config(OLD_URL, OLD_KEY)

    monkeypatch.setenv("IMMICH_CACHE_DIR", str(tmp_path / "mcpb-cache-v2"))
    monkeypatch.delenv("IMMICH_BASE_URL", raising=False)
    monkeypatch.delenv("IMMICH_API_KEY", raising=False)
    ImmichClient._cache_dir = None

    client = ImmichClient()

    assert client.base_url == OLD_URL
    assert client.api_key == OLD_KEY


def test_the_environment_beats_a_stale_update_proof_copy(isolated_cache, env_credentials,
                                                         tmp_path, monkeypatch):
    """The stable file outlives plugin versions, so it must never hijack the
    credentials someone is passing in right now — the Docker image and the
    script route both hand their server URL over through the environment."""
    ImmichClient.save_config(OLD_URL, OLD_KEY)

    monkeypatch.setenv("IMMICH_CACHE_DIR", str(tmp_path / "mcpb-cache-v2"))
    ImmichClient._cache_dir = None

    client = ImmichClient()

    assert client.base_url == "https://env.example.com"
    assert client.api_key == "env-key"


def test_the_cache_dir_wins_when_both_files_exist(isolated_cache, env_credentials,
                                                  tmp_path):
    """The cache dir is where the running install was told to look, so a config
    written there beats the older copy left by a previous version."""
    ImmichClient._write_config_file(
        str(_stable_config(tmp_path)), {"base_url": OLD_URL, "api_key": OLD_KEY})
    ImmichClient._write_config_file(
        str(isolated_cache / "config.json"), {"base_url": NEW_URL, "api_key": NEW_KEY})

    client = ImmichClient()

    assert client.base_url == NEW_URL
    assert client.api_key == NEW_KEY


def _mock_immich(url):
    respx.get(f"{url}/api/server/ping").mock(
        return_value=httpx.Response(200, json={"res": "pong"})
    )
    respx.get(f"{url}/api/users/me").mock(
        return_value=httpx.Response(200, json={"id": "u1", "email": "x@y"})
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
    with open(isolated_cache / "config.json") as handle:
        persisted = json.load(handle)
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
    respx.get(f"{NEW_URL}/api/users/me").mock(side_effect=httpx.ConnectError)
    old_client = ImmichClient(base_url=OLD_URL, api_key=OLD_KEY)
    ctx = fake_ctx(old_client)

    result = json.loads(await server.update_credentials(ctx, NEW_URL, NEW_KEY))

    assert result["success"] is False
    assert ctx.request_context.lifespan_context["immich"] is old_client


def test_the_plugin_placeholders_do_not_beat_the_update_proof_copy(isolated_cache, tmp_path,
                                                                   monkeypatch):
    """The plugin's mcp.json hands the server placeholder values through the
    environment ("https://your-immich-server.com" / "your-api-key-here"). Those
    are not credentials: a fresh plugin version must fall through to the stable
    copy instead of connecting to the placeholder host."""
    ImmichClient.save_config(OLD_URL, OLD_KEY)

    monkeypatch.setenv("IMMICH_CACHE_DIR", str(tmp_path / "mcpb-cache-v2"))
    monkeypatch.setenv("IMMICH_BASE_URL", "https://your-immich-server.com")
    monkeypatch.setenv("IMMICH_API_KEY", "your-api-key-here")
    ImmichClient._cache_dir = None

    client = ImmichClient()

    assert client.base_url == OLD_URL
    assert client.api_key == OLD_KEY

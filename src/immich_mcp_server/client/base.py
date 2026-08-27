"""Base of the Immich client: credentials, writable config override, HTTP request helper."""

import json
import os
import httpx
from pathlib import Path
from typing import Any


class ImmichClientBase:
    """Credentials, config override and the authenticated `_request` helper.

    The API areas live in sibling modules as mixins; `immich_client.ImmichClient`
    composes them on top of this class.
    """

    # Class-level cache dir, resolved once
    _cache_dir: str | None = None

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        """Resolve the server URL and API key: explicit arguments, else config.json, else the environment."""
        # Explicit credentials always win — the config.json override only
        # applies to default construction (otherwise rotating credentials
        # would silently resurrect the old ones from disk).
        if base_url is not None or api_key is not None:
            config: dict = {}
        else:
            config = self._load_config_override()
        self.base_url = (
            base_url or config.get("base_url") or os.environ.get("IMMICH_BASE_URL", "")
        ).rstrip("/")
        self.api_key = (
            api_key or config.get("api_key") or os.environ.get("IMMICH_API_KEY", "")
        )
        if not self.base_url or not self.api_key:
            raise ValueError(
                "IMMICH_BASE_URL and IMMICH_API_KEY environment variables are required. "
                "You can also set them via the update_credentials MCP tool."
            )
        self._headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }

    # ── Config override (writable cache) ─────────────────

    @classmethod
    def _find_cache_dir(cls) -> str | None:
        """Find the writable .mcpb-cache directory.

        Resolution order:
        1. IMMICH_CACHE_DIR env var (set in mcp.json) — accepted even if
           the directory doesn't exist yet (save_config will create it).
        2. Relative to this module: ../../.mcpb-cache/
        """
        if cls._cache_dir is not None:
            return cls._cache_dir

        # 1. Explicit env var (accept path even if dir doesn't exist yet)
        env_dir = os.environ.get("IMMICH_CACHE_DIR", "")
        if env_dir:
            cls._cache_dir = os.path.realpath(env_dir)
            return cls._cache_dir

        # 2. Relative to module: src/immich_mcp_server/ -> ../../.mcpb-cache/
        module_dir = Path(__file__).resolve().parent
        cache_candidate = module_dir / ".." / ".." / ".mcpb-cache"
        # Accept even if it doesn't exist yet
        cls._cache_dir = str(cache_candidate.resolve())
        return cls._cache_dir

    @classmethod
    def _config_path(cls) -> str | None:
        """Return the path to the config override file, or None."""
        cache_dir = cls._find_cache_dir()
        if not cache_dir:
            return None
        return os.path.join(cache_dir, "config.json")

    @classmethod
    def _load_config_override(cls) -> dict:
        """Load credential overrides from .mcpb-cache/config.json if it exists."""
        config_path = cls._config_path()
        if not config_path or not os.path.exists(config_path):
            return {}
        try:
            with open(config_path) as handle:
                return json.load(handle)
        except (json.JSONDecodeError, OSError):
            return {}

    @classmethod
    def save_config(cls, base_url: str, api_key: str) -> str:
        """Save credentials to the writable cache dir.

        Creates the directory if it doesn't exist.
        Returns the path written, or raises if it cannot be created.
        """
        config_path = cls._config_path()
        if not config_path:
            raise RuntimeError(
                "No cache directory path could be determined. "
                "Cannot persist credentials."
            )
        # Create the cache directory if it doesn't exist
        cache_dir = os.path.dirname(config_path)
        os.makedirs(cache_dir, exist_ok=True)
        config = {"base_url": base_url, "api_key": api_key}
        with open(config_path, "w") as handle:
            json.dump(config, handle, indent=2)
        os.chmod(config_path, 0o600)
        return config_path

    # ── HTTP ─────────────────────────────────────────────

    async def _request(
        self, method: str, path: str, json: dict | None = None, params: dict | None = None
    ) -> Any:
        """Make an authenticated request to the Immich API."""
        url = f"{self.base_url}/api{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method, url, headers=self._headers, json=json, params=params
            )
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()

"""Base of the Immich client: credentials, writable config override, the
authenticated HTTP request helper, and the date format both Immich majors take."""

import json
import os
import httpx
from pathlib import Path
from typing import Any

# Where credentials live so that they survive a plugin update. The cache dir the
# plugin's mcp.json points at carries the plugin version in its path, so a config
# written only there disappears the moment a new version is installed; this path
# belongs to the user, not to a version. IMMICH_CONFIG_HOME overrides the
# directory so the test suite never touches the real home.
STABLE_CONFIG_DIR = "~/.immich-photo-manager"

# The values the plugin's mcp.json ships in the environment before setup. They
# are not credentials, so they must not win over the update-proof copy: a fresh
# plugin version would otherwise "connect" to the placeholder host.
PLACEHOLDER_VALUES = ("https://your-immich-server.com", "your-api-key-here")

# The length of a bare ISO date, `2019-07-14`, and the time that widens it to
# the full timestamp Immich 3.x validates against.
BARE_DATE_LENGTH = 10
START_OF_DAY = "T00:00:00.000Z"


def _real_env_value(name: str) -> str:
    """The environment value for `name`, or "" when it is unset or still one of
    the plugin's placeholders."""
    value = os.environ.get(name, "")
    if value in PLACEHOLDER_VALUES:
        return ""
    return value


def to_immich_datetime(value: str | None) -> str | None:
    """A date bound in the one format both Immich majors accept.

    Immich 2.7.5 takes a bare `2019-07-14` on every search and map filter, and
    that is what the tool docstrings tell a model to send. Immich 3.1.0
    validates the same fields as full ISO 8601 and answers 400 for the bare
    date, so the identical call worked on one major and failed on the other.
    A plain date is therefore widened here to midnight UTC of that day, which
    is exactly how 2.7.5 read it, so nothing changes for 2.x callers and 3.x
    stops refusing them. A value that already carries a time is left alone.
    """
    if not value:
        return value
    if len(value) == BARE_DATE_LENGTH and value.count("-") == 2:
        return value + START_OF_DAY
    return value


class ImmichClientBase:
    """Credentials, config override and the authenticated `_request` helper.

    The API areas live in sibling modules as mixins; `immich_client.ImmichClient`
    composes them on top of this class.
    """

    # Class-level cache dir, resolved once
    _cache_dir: str | None = None

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        """Resolve the server URL and API key: explicit arguments, else the cache
        dir's config.json, else the environment, else the update-proof copy."""
        # Explicit credentials always win — the config.json overrides only
        # apply to default construction (otherwise rotating credentials
        # would silently resurrect the old ones from disk).
        if base_url is not None or api_key is not None:
            config: dict = {}
            fallback: dict = {}
        else:
            config = self._load_config_override()
            fallback = self._load_stable_config()

        # Order matters: the cache dir is what this install was told to use, so
        # it keeps beating the environment. The stable copy comes LAST, after the
        # environment, because it outlives plugin versions: a file left by an
        # older setup must never hijack the credentials a user is passing in now.
        self.base_url = (
            base_url
            or config.get("base_url")
            or _real_env_value("IMMICH_BASE_URL")
            or fallback.get("base_url", "")
        ).rstrip("/")
        self.api_key = (
            api_key
            or config.get("api_key")
            or _real_env_value("IMMICH_API_KEY")
            or fallback.get("api_key", "")
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
    def _stable_config_path(cls) -> str:
        """The per-user config path that outlives plugin updates.

        Read fresh every time rather than memoized like the cache dir, so that
        a test pointing IMMICH_CONFIG_HOME elsewhere takes effect immediately.
        """
        config_home = os.environ.get("IMMICH_CONFIG_HOME", "")
        directory = config_home or os.path.expanduser(STABLE_CONFIG_DIR)
        return os.path.join(directory, "config.json")

    @classmethod
    def _read_config_file(cls, config_path: str | None) -> dict:
        """The credentials stored at `config_path`, or an empty dict when the
        file is missing, unreadable or not valid JSON."""
        if not config_path or not os.path.exists(config_path):
            return {}
        try:
            with open(config_path) as handle:
                return json.load(handle)
        except (json.JSONDecodeError, OSError):
            return {}

    @classmethod
    def _load_config_override(cls) -> dict:
        """Load credential overrides from .mcpb-cache/config.json if it exists."""
        return cls._read_config_file(cls._config_path())

    @classmethod
    def _load_stable_config(cls) -> dict:
        """Load the update-proof copy of the credentials.

        This is the copy that survived the last plugin update, and it is read
        only when nothing closer to the caller answered: the cache dir a fresh
        plugin version points at is empty, and no credentials are in the
        environment either.
        """
        return cls._read_config_file(cls._stable_config_path())

    @classmethod
    def _write_config_file(cls, config_path: str, config: dict) -> None:
        """Write the credentials to `config_path`, creating its directory, and
        leave the file readable by its owner only."""
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as handle:
            json.dump(config, handle, indent=2)
        os.chmod(config_path, 0o600)

    @classmethod
    def save_config(cls, base_url: str, api_key: str) -> str:
        """Save credentials to the writable cache dir AND to the stable per-user
        path, so the next plugin version finds them where its own cache dir is
        still empty.

        Creates both directories if they don't exist. Returns the cache path,
        the location this install reads first, or raises if it cannot be
        determined. A stable path that cannot be written is not fatal: the
        session keeps working, only the update-proof copy is missing.
        """
        config_path = cls._config_path()
        if not config_path:
            raise RuntimeError(
                "No cache directory path could be determined. "
                "Cannot persist credentials."
            )
        config = {"base_url": base_url, "api_key": api_key}
        cls._write_config_file(config_path, config)

        try:
            cls._write_config_file(cls._stable_config_path(), config)
        except OSError:
            pass

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

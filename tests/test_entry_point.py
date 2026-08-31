"""The command-line entry point: --version answers without starting a server.

Knowing which version a uvx environment runs turned out to be impossible from
outside (the envs are content-hashed); the flag settles it in one call.
"""

import subprocess
import sys

from immich_mcp_server import __version__


def test_version_flag_prints_the_version_and_exits():
    result = subprocess.run(
        [sys.executable, "-m", "immich_mcp_server", "--version"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"immich-photo-manager {__version__}"

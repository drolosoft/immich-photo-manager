"""setup-mcp.sh must treat the API key/URL as opaque data, never as code.

Regression test for shell→Python injection: user-supplied values were
interpolated directly into `python3 -c` source and into a JSON heredoc,
so a single quote in the API key executed arbitrary Python and corrupted
every generated config.
"""

import json
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_setup_script_survives_hostile_api_key(tmp_path):
    # A key that breaks out of a single-quoted Python string literal and
    # tries to run code; also contains a double quote to corrupt raw JSON.
    pwned = tmp_path / "pwned"
    evil_key = f"k'+__import__('os').system('touch {pwned}')+'\"tail"

    # Sandbox copy of the repo layout the script expects
    sandbox = tmp_path / "repo"
    (sandbox / "scripts").mkdir(parents=True)
    (sandbox / "src").mkdir()
    shutil.copy(REPO / "scripts" / "setup-mcp.sh", sandbox / "scripts" / "setup-mcp.sh")

    # Stub pip3 so the test never installs anything
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "pip3"
    stub.write_text("#!/bin/sh\nexit 0\n")
    stub.chmod(0o755)

    home = tmp_path / "home"
    home.mkdir()

    proc = subprocess.run(
        ["bash", str(sandbox / "scripts" / "setup-mcp.sh")],
        input=f"https://immich.test\n{evil_key}\nn\n",
        capture_output=True,
        text=True,
        timeout=120,
        env={
            "HOME": str(home),
            "PATH": f"{bindir}:/usr/bin:/bin:/usr/sbin:/sbin",
        },
    )

    assert proc.returncode == 0, proc.stderr
    # The hostile key must never execute
    assert not pwned.exists(), "API key was executed as code"
    # The generated config must be valid JSON carrying the key verbatim
    with open(sandbox / ".mcp.json") as handle:
        config = json.load(handle)
    assert config["mcpServers"]["immich"]["env"]["IMMICH_API_KEY"] == evil_key

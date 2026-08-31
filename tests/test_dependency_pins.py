"""src/requirements.txt (the setup script and plugin route) must carry the same
version bounds as pyproject.toml (the pip/uvx route).

Issue #16: requirements.txt said `mcp>=1.0.0` with no upper bound while
pyproject already pinned `mcp<2.0`, so fresh script installs picked up the
mcp 2.x SDK (FastMCP renamed to MCPServer) and crashed on import. One source
of truth per dependency keeps the two install routes from drifting apart again.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _requirement_name(line):
    """The distribution name at the front of a requirement line."""
    for position, character in enumerate(line):
        if character in "><=!~[; ":
            return line[:position]
    return line


def test_requirements_match_pyproject_bounds():
    # Textual parse instead of tomllib, which is stdlib only from Python 3.11
    # and this suite still runs on 3.10.
    pyproject = (ROOT / "pyproject.toml").read_text()
    block = re.search(r"^dependencies = \[(.*?)^\]", pyproject, re.S | re.M).group(1)
    declared = {_requirement_name(dep): dep.replace(" ", "")
                for dep in re.findall(r'"([^"]+)"', block)}

    lines = [line.strip() for line in (ROOT / "src" / "requirements.txt").read_text().splitlines()
             if line.strip() and not line.strip().startswith("#")]
    listed = {_requirement_name(line): line.replace(" ", "") for line in lines}

    assert listed == declared

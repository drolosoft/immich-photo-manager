"""server.json, the registry listing, must agree with the rest of the repo.

The official MCP registry (registry.modelcontextprotocol.io) reads server.json
and then checks two proofs of ownership: an `mcp-name:` token in the PyPI
README and an `io.modelcontextprotocol.server.name` label on the image. Both
must carry the exact server name, and every version in the file must be the
one pyproject.toml declares, or the publish is refused after the release is
already out. This file pins all of that, and on the way it pins the three
version files that were only kept in step by hand (pyproject.toml,
.claude-plugin/plugin.json, the package __init__).
"""

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER_JSON = json.loads((ROOT / "server.json").read_text())


def _pyproject_version():
    """The version pyproject.toml declares, read textually (no tomllib on 3.10)."""
    pyproject = (ROOT / "pyproject.toml").read_text()
    return re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)


def test_server_json_version_matches_pyproject():
    assert SERVER_JSON["version"] == _pyproject_version()


def test_every_package_in_server_json_carries_the_release_version():
    version = _pyproject_version()
    for package in SERVER_JSON["packages"]:
        assert package["version"] == version, package["registryType"]
        if package["registryType"] == "oci":
            assert package["identifier"].endswith(":" + version), package["identifier"]


def test_plugin_manifest_and_package_init_carry_the_release_version():
    version = _pyproject_version()
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["version"] == version

    init = (ROOT / "src" / "immich_mcp_server" / "__init__.py").read_text()
    assert re.search(r'^__version__ = "([^"]+)"', init, re.M).group(1) == version


def test_readme_carries_the_registry_ownership_token():
    # PyPI renders README.md as the package description and keeps HTML
    # comments, which is where the registry looks for the token. It must be
    # followed by a boundary (here the comment close), never glued to a period.
    readme = (ROOT / "README.md").read_text()
    token = "<!-- mcp-name: " + SERVER_JSON["name"] + " -->"
    assert token in readme


def test_dockerfile_label_matches_the_server_name():
    dockerfile = (ROOT / "Dockerfile").read_text()
    label = re.search(r'^LABEL io\.modelcontextprotocol\.server\.name="([^"]+)"', dockerfile, re.M)
    assert label is not None
    assert label.group(1) == SERVER_JSON["name"]


def test_server_name_uses_the_github_org_namespace():
    # GitHub login grants io.github.<org>/* only to org owners; the name is
    # what the publisher authenticates against, so it must not drift.
    assert SERVER_JSON["name"] == "io.github.drolosoft/immich-photo-manager"
    assert SERVER_JSON["repository"]["url"] == "https://github.com/drolosoft/immich-photo-manager"

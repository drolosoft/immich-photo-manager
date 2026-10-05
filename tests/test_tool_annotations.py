"""
Every tool tells the client what kind of call it is.

The Claude directory policy asks each MCP tool for a title and for the
`readOnlyHint` and `destructiveHint` annotations, and clients use them to decide
which calls need the user's confirmation. The two sets below are written out by
name on purpose: a tool that starts changing or removing data must be moved
here by hand, in the same commit, or these tests fail.
"""

import pytest

from immich_mcp_server import server
from tool_manifest import TOOL_NAMES

# Tools that only add: a new album, tag, link, note, upload or file on disk.
# Nothing that existed before the call is changed or removed by them.
ADDITIVE_TOOLS = {
    "add_assets_to_album",
    "create_activity",
    "create_album",
    "create_memory",
    "create_partner",
    "create_shared_link",
    "create_stack",
    "create_tag",
    "download_archive",
    "export_pdf",
    "record_action",
    "restore_assets",
    "restore_trash",
    "review_assets",
    "rotate_assets",
    "tag_assets",
    "upload_asset",
}

# Tools that overwrite a value or remove something. The MCP specification
# counts both as destructive: only purely additive changes are not.
DESTRUCTIVE_TOOLS = {
    "clear_asset_notes",
    "delete_activity",
    "delete_album",
    "delete_assets",
    "delete_memory",
    "delete_shared_link",
    "delete_stack",
    "delete_tag",
    "empty_trash",
    "merge_people",
    "reassign_face",
    "remove_assets_from_album",
    "remove_partner",
    "resolve_duplicates",
    "revert_asset_edits",
    "untag_assets",
    "update_album",
    "update_asset_metadata",
    "update_assets_metadata",
    "update_credentials",
    "update_memory",
    "update_partner",
    "update_person",
    "update_shared_link",
    "update_stack",
    "update_tag",
}


@pytest.fixture(scope="module")
async def tools_by_name():
    tools = await server.mcp.list_tools()
    return {tool.name: tool for tool in tools}


@pytest.mark.asyncio
async def test_every_tool_has_a_title(tools_by_name):
    for name in TOOL_NAMES:
        assert tools_by_name[name].title, name


@pytest.mark.asyncio
async def test_every_tool_declares_both_hints(tools_by_name):
    for name in TOOL_NAMES:
        annotations = tools_by_name[name].annotations
        assert annotations is not None, name
        assert annotations.read_only_hint is not None, name
        assert annotations.destructive_hint is not None, name


@pytest.mark.asyncio
async def test_destructive_tools_are_exactly_the_listed_ones(tools_by_name):
    declared = {name for name, tool in tools_by_name.items() if tool.annotations.destructive_hint}
    assert declared == DESTRUCTIVE_TOOLS


@pytest.mark.asyncio
async def test_read_only_tools_are_everything_that_neither_adds_nor_destroys(tools_by_name):
    declared = {name for name, tool in tools_by_name.items() if tool.annotations.read_only_hint}
    assert declared == set(TOOL_NAMES) - ADDITIVE_TOOLS - DESTRUCTIVE_TOOLS


def test_no_tool_is_listed_as_both_additive_and_destructive():
    assert not ADDITIVE_TOOLS & DESTRUCTIVE_TOOLS
    assert ADDITIVE_TOOLS | DESTRUCTIVE_TOOLS <= set(TOOL_NAMES)

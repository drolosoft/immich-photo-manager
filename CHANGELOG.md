# Changelog

All notable changes to immich-photo-manager are documented here.

---

## [Unreleased]

### Fixed
- **`update_credentials`** now validates and hot-swaps exactly the credentials it was given. Previously, once a `config.json` existed (any prior rotation), the on-disk credentials silently took precedence and the tool "successfully" re-applied the old key.
- **`rotate_assets`** preserves non-rotation edits (crop, mirror). Previously a cumulative 360° deleted *all* edits and every rotation replaced the full edit list. A failure reading current edits now fails that asset instead of silently resetting the angle (404 still means "no edits yet").
- **Startup diagnostics go to stderr** — the stdio transport's stdout stays pure JSON-RPC even when Immich is unreachable.
- **`scripts/setup-mcp.sh`** passes the server URL and API key to Python via environment variables instead of interpolating them into code and JSON (a quote in the key could execute arbitrary code); the key is read without terminal echo and the final connection test can no longer abort the setup.

### Added
- **Offline test suite** (`pytest`, 13 tests) covering credential rotation, edit-preserving rotation, transport hygiene, and setup-script safety — runs without an Immich instance.
- **CI** — lint + tests on every push/PR (Python 3.10 & 3.13), and a tag-triggered release workflow that gates on tests, guards the sdist contents, publishes to PyPI (trusted publishing), and attaches artifacts to the GitHub release.

## [v1.3.1] — 2026-07-12

### Security
- **PyPI sdist** now ships only the package sources (`src/immich_mcp_server`, README, LICENSE, SECURITY.md) instead of the full working tree.
- **HTTP transport** binds to `127.0.0.1` by default (`MCP_HOST` to override) — first tagged release carrying this hardening.
- **Dependencies** are version-capped (`httpx<1.0`, `mcp<2.0`, `uvicorn<1.0`).

### Added
- **uvx entry point** — `uvx immich-photo-manager` runs the server directly ([#3](https://github.com/drolosoft/immich-photo-manager/pull/3), thanks @kirel).
- **`__version__`** in `immich_mcp_server` and this CHANGELOG.

### Changed
- **Version and counts synced** across plugin.json, marketplace.json, SECURITY.md, and docs — 50 MCP tools, 12 skills, one version everywhere.

### Removed
- **Internal maintenance files** (`_commit-and-rebuild.sh`, `WORKFLOW.md`, `.claude/context/`) no longer tracked in the repo.

## [v1.3.0] — 2026-05-18

### Added
- **Tags (7 tools)** — `list_tags`, `get_tag`, `create_tag`, `update_tag`, `delete_tag`, `tag_assets`, `untag_assets`.
- **Upload** — `upload_asset` (25 MB limit, extension filter, optional album).
- **Asset listing** — `list_assets` with favorite/archived/trashed/type filters.
- **Shared links CRUD** — `get_shared_link`, `update_shared_link`, `delete_shared_link`.
- **Bulk rotation** — `rotate_assets` / `revert_asset_edits` (non-destructive, accumulates, revertible).

Total: **50 MCP tools**.

### Fixed
- `list_assets` uses `POST /search/metadata` (GET `/assets` returns 404 on Immich v2.7).
- QA audit fixes — Linux compatibility, symlink checks, empty-input validation, dedup collision handling.

## [v1.2.0] — 2026-04-26

### Added
- **People & Faces (8 tools)** — list, get, update, merge, search, thumbnails, asset faces, face reassignment.
- **Trash & deletion (4 tools)** — trash, empty, restore.
- **Duplicates (2 tools)** — `get_duplicates`, `resolve_duplicates` via Immich's built-in detection.

Total: 36 MCP tools.

## [v1.1.0] — 2026-04-16

### Added
- **`update_asset_metadata`** — native metadata repair: timestamps, GPS inference from neighbors, timezone correction, descriptions, ratings.

Total: 22 MCP tools.

## [v1.0.0] — 2026-04-14

First stable release: 21 MCP tools, 11 skills, 5 slash commands, interactive HTML galleries with base64-embedded thumbnails, Claude Code plugin + any-MCP-client support.

---

[v1.3.1]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.3.1
[v1.3.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.3.0
[v1.2.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.2.0
[v1.1.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.1.0
[v1.0.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.0.0

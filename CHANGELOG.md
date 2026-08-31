# Changelog

All notable changes to immich-photo-manager are documented here.

---

## [Unreleased]

## [v1.12.1] — 2026-08-31

### Fixed
- **Fresh installs via `scripts/setup-mcp.sh` crashed on import** (#16): `src/requirements.txt` allowed the new mcp 2.x SDK, where `FastMCP` was renamed and the 1.x import fails. The file now carries the same `mcp>=1.9.0,<2.0` bound `pyproject.toml` always had (the pip/uvx route was never affected), and a test keeps both dependency lists identical from now on.

## [v1.12.0] — 2026-08-31

### Added
- **Photobook: one full page per chosen video frame**: with `layout="photobook"`, a video with several extracted frames unfolds into one full page per frame — each with its timestamp in the metadata line — instead of a single page with a thumbnail strip. Photos and single-frame videos keep the one-page look. Asked for in #15 ("full frames like photos"). The `detail` layout keeps the compact frame strip with timestamps.
- **`frame_captions` in `export_pdf`**: `{asset_id: [text, ...]}`, one caption per chosen frame in `frame_times` order; the photobook prints each caption on its frame's page. Without it, the asset caption opens the sequence on the first frame page.
- **Optional front matter**: `cover`, `index` and `places` booleans in `export_pdf` (all default true) turn each opening page off — a print-ready photobook can now be bare pages only.
- **`options` in `get_export_preview`**: the preview now lists every `export_pdf` choice with its default, so the model can ask the user how they want their PDF (layout, cover pages, video moments, captions) before building it — or skip straight to defaults when the user already said.

## [v1.11.0] — 2026-08-31

### Added
- **Contact sheets**: `get_video_frames(..., sheet=true)` packs the frames into grid images (30 per sheet, the timestamp burned under each), so skimming a long video costs one or two images instead of dozens, and needs no confirmation.
- **`language` in `export_pdf`**: `"es"` prints the fixed page labels (Índice, Lugares, Cámara, página n/n) in Spanish; captions stay as written. English remains the default.
- **`--version`**: `immich-photo-manager --version` prints the installed version, which a uvx environment could not answer before.

### Fixed
- Photobook pages centre a landscape image vertically instead of leaving the bottom half of the page empty.

## [v1.10.0] — 2026-08-31

### Added
- **`frame_times` in `export_pdf`**: `{asset_id: [seconds]}` cuts a video's PDF frames at exact moments instead of an even spread, so the page carries the representative frame the model chose after watching, not the blind middle of the clip. Wins over `frames_per_video`/`frame_interval` for the listed videos. Asked for in #15 ("extract a representative frame").

## [v1.9.0] — 2026-08-31

### Added
- **`image_size="original"` in `export_pdf`**: photos go in at the stored file's quality, re-encoded to at most 3000px on the long side (A4 print territory) with EXIF rotation applied. A format the server cannot decode (some HEIC, RAW) falls back to the preview with a note in `warnings`. Asked for in #15 ("the actual photos, not blown up thumbnails").
- **Live Photos count once**: the motion clip a still points at through `livePhotoVideoId` is folded into its photo in `get_export_preview` and `export_pdf`, with a note. Asked for in #15.

## [v1.8.0] — 2026-08-31

### Added
- **`layout="photobook"` in `export_pdf`**: one asset per page, the image as large as the page allows, fitted without cropping (letterbox, never a crop that cuts off edges), one metadata line and the caption under it. With `frames_per_video=1` a video reads like a photo. Asked for in #15 for a car-spotting photobook.
- **`frame_size` in `export_pdf`**: size of the video frames inside the PDF. `"auto"` (default) uses preview quality (1440px) up to 4 frames per video and thumbnail (250px) above; `"preview"` and `"thumbnail"` force it. Before, frames in the PDF were always 250px.

### Fixed
- **Vertical phone videos came out sideways** in the PyAV frames (`get_video_frames` and the PDF): phones store the video rotated with a display-rotation flag, which PyAV decodes but does not apply. Frames now honour the flag, matching ffmpeg's behavior; verified against ffmpeg's auto-rotation on both Immich versions. Reported in #15.

## [v1.7.1] — 2026-08-28

### Changed
- **PyAV and fpdf2 are dependencies of the package.** `pip install immich-photo-manager` (or `uvx immich-photo-manager`) now brings video frames and PDF export with it; nothing extra to install, one line in the client config. The `[video]`, `[pdf]` and `[all]` extras still exist, empty, so commands copied from the 1.6.0 and 1.7.0 docs keep working. Plugin route: `pip3 install -r src/requirements.txt` after pulling.

## [v1.7.0] — 2026-08-28

### Added
- **`export_pdf(album_id / asset_ids, captions, layout, frames_per_video, frame_interval, image_size, map, ...)`** builds a PDF (cover, index with links, places table with an optional OpenStreetMap map, one detail page per asset or a six-per-page grid, video frames laid out four per row with timestamps, footer on every page) from an album or a list of assets, on the machine running the server. Immich metadata (date, place, camera, people, tags) is always included; `captions` add the model's own description of each asset. The file is never sent anywhere unless `return_base64=true`. Needs `pip install immich-photo-manager[pdf]`.
- **`get_export_preview(album_id / asset_ids, limit)`**, the read-only look-before-you-leap step: lists what `export_pdf` would include (id, type, filename, date, place, people, video duration) without looking at a single image.
- **`album-report` skill** — a report workflow that previews an album or selection, looks at the photos and video frames, writes one caption per asset, and calls `export_pdf` to produce the PDF.
- **`start` / `end` / `interval` / `confirm` on `get_video_frames` / `get_video_frames_json`** — a video can now be watched by segment (`start`/`end` in seconds) or at a fixed cadence (`interval`, down to one frame per second) instead of only evenly spaced over the whole clip.
- **Extras `[pdf]` and `[all]`** in `pyproject.toml` (`fpdf2` for PDF export; `[all]` installs both `[video]` and `[pdf]`).
- **Immich 2.7.5 compatibility**: `POST /search/metadata` silently ignores the `ids` filter on that version and returns unrelated assets instead. Assets requested by id now fall back to `GET /assets/{id}` per id for anything not found in the `/search/metadata` response, so `export_pdf`/`get_export_preview` with `asset_ids` work the same on 2.7.5 and 3.x.

### Changed
- **Video frame cap raised from 12 to 120 per call.** Above 12 frames, `get_video_frames`/`get_video_frames_json` no longer extract automatically: they return `{confirm_required: true, frames_planned, estimated_tokens, ...}` and wait for a call with `confirm=true`, so a large request is never made without the user seeing its cost first.
- **Numeric video durations are read as milliseconds** (Immich's `duration` field), rather than assumed to already be seconds.

## [v1.6.0] — 2026-08-26

### Added
- **`get_video_frames(asset_id, count=6, size)`** returns evenly spaced frames of a video as image blocks, so a model can look at a clip frame by frame (issue #15). Immich only keeps one poster thumbnail per video; the plugin downloads the file through `GET /assets/{id}/video/playback` and decodes the frames locally with PyAV (optional extra `pip install immich-photo-manager[video]`) or `ffmpeg` on PATH, and says which to install when neither is present. `count` is capped at 12; every frame is one image for the model.
- **`get_video_frames_json`**, the base64 + timestamps twin for HTML galleries and skills.
- Live harness checks for both tools against `clip.mp4` on Immich 2.7.5 and 3.1.0. 55 tools.

## [v1.5.3] — 2026-08-25

### Added
- **`get_album` returns an `assets` array** (id, filename, type, date, recognized people) so "who appears in this album / which photos show the same person" is answered in one call, on Immich 2.x and 3.x alike (album contents are now always read through `POST /search/metadata` with `withPeople`, since the 2.x inline list carries no people and 3.x has no inline list).
- **`get_duplicates(album_id=…)`** scopes ML duplicate groups to an album and reports which assets of each group are inside/outside it. The tool now states explicitly that "duplicates" means the same picture, not the same person.

## [v1.5.2] — 2026-08-25

Every tool was exercised over the MCP protocol against live Immich 2.7.5 and 3.1.0 instances. Five defects surfaced; all are fixed and covered by tests.

### Fixed
- **`list_assets(is_trashed=true)`** returned the *active* library — Immich's search has no `isTrashed` filter, so it was silently ignored. Trashed assets are now selected with `withDeleted` + `trashedAfter`.
- **`resolve_duplicates`** sent the wrong body (bare list, `assetIds`/`trashIds`) so nothing was trashed. Now sends `{"groups": [{duplicateId, keepAssetIds, trashAssetIds}]}` as `POST /duplicates/resolve` expects (Immich ≥ 2.6), still accepts the legacy keys, and falls back to trash + un-flag on older servers.
- **`reassign_face`** had the person and face ids swapped (`PUT /faces/{personId}` with `{"id": faceId}`), so the reassignment never happened.
- **`update_credentials`** validated the new key against `/server/ping`, which needs no auth, so a wrong key was accepted and persisted. It now validates with `/users/me` (a 403 from a scoped key still counts as valid).
- **`update_tag`** claimed to rename tags; Immich's API only updates the color. Passing `name` now returns a clear error with the create/retag/delete workaround.

## [v1.5.1] — 2026-08-25

### Fixed
- **Album contents on Immich 3.x** — Immich 3.0 removed the `assets` list from `GET /albums/{id}`, so `get_album`, `get_album_thumbnails`, `get_album_images` and `rotate_assets(album_id=…)` returned an empty album on 3.x servers. They now fall back to `POST /search/metadata` (`albumIds`, paginated), which works on 2.x and 3.x. New client method `get_album_assets`. 6 regression tests.

## [v1.5.0] — 2026-08-25

### Added
- **Image-block thumbnail tools** — `get_asset_image`, `get_album_images`, `get_images_batch` return MCP `ImageContent` for clients that render images inline (Open WebUI, Claude Desktop). Additive: the existing `get_*_thumbnail(s)` tools keep returning base64 JSON (the default the skills embed into HTML galleries). Tool count 50 → 53 ([#13](https://github.com/drolosoft/immich-photo-manager/pull/13), idea from @developersorli).
- **Docker deployment** — `Dockerfile`, `docker-compose.yml`, `.dockerignore` for a local build (no registry), plus TrueNAS SCALE / Open WebUI docs in `GETTING-STARTED.md` ([#12](https://github.com/drolosoft/immich-photo-manager/pull/12), thanks @developersorli).
- **`--transport` CLI flag** (`stdio`/`http`) with precedence CLI > `MCP_TRANSPORT` env > default.
- **`start-mcp.sh.example`** launch template; `start-mcp.sh` is git-ignored (holds real credentials).

### Changed
- **`MCP_ALLOWED_HOSTS`** accepts a bare host/IP — a `:*` wildcard is appended for portless entries, since the `Host` header always carries a port.

### Fixed
- **Preview thumbnails** use `thumbnail?size=preview` (Immich 3.x removed the dedicated `/preview` route). Return shape unchanged.
- **Startup logs** — silence the harmless pydantic-settings `IncompleteFieldDefinitionWarning`.

## [v1.4.0] — 2026-07-27

### Fixed
- **`update_credentials`** now validates and hot-swaps exactly the credentials it was given. Previously, once a `config.json` existed (any prior rotation), the on-disk credentials silently took precedence and the tool "successfully" re-applied the old key.
- **`rotate_assets`** preserves non-rotation edits (crop, mirror). Previously a cumulative 360° deleted *all* edits and every rotation replaced the full edit list. A failure reading current edits now fails that asset instead of silently resetting the angle (404 still means "no edits yet").
- **Startup diagnostics go to stderr** — the stdio transport's stdout stays pure JSON-RPC even when Immich is unreachable.
- **`scripts/setup-mcp.sh`** passes the server URL and API key to Python via environment variables instead of interpolating them into code and JSON (a quote in the key could execute arbitrary code); the key is read without terminal echo and the final connection test can no longer abort the setup.
- **Install instructions** — `claude plugin marketplace add ./` (the bare `.` was rejected as an invalid marketplace source) and the `setup-mcp.sh` step is now documented ([#5](https://github.com/drolosoft/immich-photo-manager/pull/5), thanks @tclancy).

### Added
- **`MCP_ALLOWED_HOSTS`** — comma-separated extra `Host` values accepted in HTTP mode, so the server works behind a reverse proxy that forwards a public domain (previously `421 Misdirected Request`). Additive and opt-in: DNS-rebinding protection stays on, localhost stays allowed, and unset means unchanged behavior ([#4](https://github.com/drolosoft/immich-photo-manager/pull/4), thanks @bradhgq).
- **Offline test suite** (`pytest`, 13 tests) covering credential rotation, edit-preserving rotation, transport hygiene, and setup-script safety — runs without an Immich instance.
- **CI** — lint + tests on every push/PR (Python 3.10 & 3.13), and a tag-triggered release workflow that gates on tests, guards the sdist contents, publishes to PyPI (trusted publishing), and attaches artifacts to the GitHub release.

### Changed
- **`mcp` minimum raised to `1.9`** — the `MCP_ALLOWED_HOSTS` feature passes `transport_security` to `FastMCP`, an argument only present since mcp 1.9; the old `>=1.0.0` floor could resolve a version that crashes at startup ([#6](https://github.com/drolosoft/immich-photo-manager/pull/6)).

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

[v1.12.1]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.12.1
[v1.12.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.12.0
[v1.11.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.11.0
[v1.10.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.10.0
[v1.9.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.9.0
[v1.8.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.8.0
[v1.7.1]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.7.1
[v1.7.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.7.0
[v1.6.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.6.0
[v1.5.3]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.5.3
[v1.5.2]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.5.2
[v1.5.1]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.5.1
[v1.5.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.5.0
[v1.4.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.4.0
[v1.3.1]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.3.1
[v1.3.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.3.0
[v1.2.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.2.0
[v1.1.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.1.0
[v1.0.0]: https://github.com/drolosoft/immich-photo-manager/releases/tag/v1.0.0

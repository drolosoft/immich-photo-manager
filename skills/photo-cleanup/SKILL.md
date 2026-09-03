---
name: photo-cleanup
description: >
  Detect and remove screenshots, duplicates, and low-quality photos from an Immich library.
  Use when the user says "clean up my photos", "remove screenshots",
  "find duplicates", "deduplicate", "photo cleanup", "library cleanup",
  "how many screenshots do I have", "free up space", "remove junk photos",
  or any variation of cleaning, deduplicating, or optimizing a photo library.
version: 1.2.0
---

# Photo Cleanup

## ⚠️ Connection Required — ALWAYS CHECK FIRST

**Before doing ANYTHING else in this skill, call `ping` on the Immich MCP server.**

- If `ping` succeeds → proceed with the skill normally.
- If `ping` fails or the MCP tools are not available → **STOP. Do not continue.** Tell the user:

> ❌ **Immich is not connected.** This plugin needs a running Immich MCP server to work.
>
> Run **/setup-immich-photo-manager** to configure your Immich connection. You'll need:
> 1. Your Immich server URL (e.g., `http://192.168.1.100:2283`)
> 2. An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
> 3. The MCP server configured (see **/setup-immich-photo-manager**)
>
> Nothing in this plugin will work until the connection is configured.

**Do NOT skip this check. Do NOT try to run any other tool first. Always ping, always block if it fails.**

Intelligent photo library cleanup for Immich. Identifies and helps remove screenshots, duplicates, and low-quality images while protecting valuable photos.

## Safety First

**NEVER delete photos automatically.** Always:
1. Identify candidates for removal
2. Present findings with counts and examples to the user
3. Get explicit approval before any deletion
4. Use `delete_assets(asset_ids, force=False)` to send photos to trash (recoverable). Use `restore_assets` or `restore_trash` to undo. Only use `force=True` for permanent deletion when the user explicitly requests it.

## Cleanup Categories

### 1. Screenshot Detection

Screenshots are the #1 source of library bloat. Surface candidates with `search_smart(query="screenshot")` (CLIP) plus filename patterns (`Screenshot*`, `Screen Shot*`, `Captura*`) in `search_metadata`/`list_assets` results — dimensions are NOT searchable. Then score each candidate by combining multiple signals (dimensions and EXIF come from `get_asset_info`, per asset):

| Signal | Weight | How to detect |
|--------|--------|--------------|
| Screen resolution | High | `get_asset_info` dimensions match known screen sizes exactly |
| No GPS data | Medium | EXIF GPS fields empty |
| No lens info | Medium | No focal length, aperture, or lens model |
| Filename pattern | Low | Contains "Screenshot", "Screen Shot", "Captura" |
| No camera make/model | Medium | Missing or generic device info |

**Screen resolutions to flag** (exact pixel matches):

iPhone screens: 750x1334, 1125x2436, 1170x2532, 1242x2688, 1284x2778, 1290x2796
Mac screens: 1920x1080, 2560x1440, 2560x1600, 2880x1800, 3024x1964, 3456x2234
Common Android: 1080x1920, 1080x2340, 1080x2400, 1440x2560, 1440x3200

A photo matching 2+ signals is a strong screenshot candidate. Report confidence level:
- **High confidence**: Screen resolution + no GPS + no lens → almost certainly screenshot
- **Medium confidence**: Screen resolution only, or no GPS + no lens but non-standard resolution
- **Low confidence**: Only one signal matches → needs human review

### 2. Duplicate Detection

Sources of duplicates:
- Same photo in Google Fotos AND Apple Fotos (most common)
- Multiple exports of the same original (different formats: HEIC, JPEG, PNG)
- Burst photos that look identical
- Edited versions alongside originals

Detection strategy:
1. **Immich ML duplicates**: Use `get_duplicates` tool as a fast first pass — returns groups of visually similar assets detected by Immich's ML engine. Resolve with `resolve_duplicates`.
2. **Exact duplicates**: Same file hash (SHA-256) → safe to remove the copy
3. **Format duplicates**: Same timestamp + same dimensions, different format → keep highest quality (HEIC > JPEG > PNG)
4. **Near-duplicates**: Same timestamp + similar dimensions + high CLIP similarity → present to user
5. **Burst groups**: Sequential timestamps (< 2 seconds apart) + same location → let user pick best

### 3. Low-Quality Photo Detection

| Issue | Detection | Action |
|-------|-----------|--------|
| Very dark | Average brightness < 20 (if available) | Flag for review |
| Very blurry | Motion blur EXIF hints, very low sharpness | Flag for review |
| Tiny resolution | Under 640x480 | Flag for review |
| Corrupt/partial | File size anomalies, unreadable EXIF | Flag for review |

**Important**: Some intentionally dark or blurry photos are artistic. Always flag, never auto-remove.

## Cleanup Workflow

### Quick Scan (recommended first step)

1. Get library statistics: total photos, videos, storage
2. Estimate screenshots: run `search_smart(query="screenshot")` and scan filenames (`Screenshot*`, `Captura*`) in `search_metadata`/`list_assets` results
3. Estimate duplicates: search for same-timestamp clusters
4. Report summary:

```
📊 Library: {total} assets ({size})
📱 Probable screenshots: ~{count} ({percentage}%)
🔄 Probable duplicates: ~{count} ({percentage}%)
📉 Low quality candidates: ~{count} ({percentage}%)
💾 Estimated space recoverable: {size}
```

### Targeted Cleanup

After the quick scan, clean up category by category:

1. **Screenshots first** (highest confidence, biggest impact)
   - `search_smart(query="screenshot")` (CLIP) to surface visual screenshots
   - Scan filenames from `search_metadata`/`list_assets` for `Screenshot*`, `Screen Shot*`, `Captura*` patterns
   - Confirm borderline candidates with `get_asset_info`: no GPS + no lens info + dimensions matching known screen sizes
   - Present list grouped by confidence level
   - User approves → `delete_assets(asset_ids, force=False)` (moves to trash, recoverable)

2. **Duplicates second** (requires more care)
   - Find exact hash duplicates first (safest)
   - Then find format duplicates (same photo, different format)
   - Keep the highest quality version
   - User approves → `delete_assets(asset_ids, force=False)` to trash copies. For ML duplicates, use `get_duplicates` + `resolve_duplicates` first.

3. **Low quality last** (most subjective)
   - Present candidates with thumbnails if possible
   - User decides per-photo or in batches

### Remember what was decided (notes)

The plugin keeps its own memory on each asset (`review_assets`, `get_assets_notes`), invisible in Immich and separate from tags. Use it so a second pass — days later, another session — does not redo the work:

- **Before analysing a batch**, call `get_assets_notes(asset_ids)` and skip the assets that already have a `last_verdict`, unless the user asks to re-review them. Say how many were skipped.
- **After each decision**, call `review_assets(asset_ids, verdict, reason)` with `keep`, `delete_candidate`, `duplicate_of` or `needs_check` and a short concrete reason ("near-identical to IMG_6367, that one has the bystander"). Tag the delete candidates as well (a tag is what the user sees and selects in Immich; the note is the why).
- When something is trashed, `record_action(asset_ids, "trashed", reason)` so the audit trail survives a restore.

### Progress Reporting

For large cleanups, report progress every 500 assets processed:
```
🧹 Scanning... {processed} / {total} ({percentage}%)
Found so far: {screenshots} screenshots, {duplicates} duplicates
```

## Cleanup by Source

Since Immich imports from specific folders, cleanup can target specific sources:

- **Google Photos imports** — Oldest photos, most likely to have duplicates with Apple Photos
- **Apple Photos imports** — Higher quality (HEIC), but overlaps with Google
- **Manual imports** — Manually organized, least likely to need cleanup
- **Screen capture folders** — ALL screenshots by definition

## What NOT to Clean

- Photos with faces detected (Immich's face recognition) — may be valuable memories
- Photos in existing albums — someone already curated these
- Favorited photos — explicitly marked as wanted
- Videos — different cleanup criteria, handle separately
- Photos with GPS in known "home" locations — daily life photos may seem like junk but are memories

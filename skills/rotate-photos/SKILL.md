---
name: rotate-photos
description: >
  Bulk rotate photos in an Immich library, by album or asset IDs. Non-destructive,
  original files are never modified. Supports undo/revert.
  Use when the user says "rotate photos", "rotate album", "fix rotation",
  "photos are sideways", "rotate 90", "rotate clockwise", "rotate counterclockwise",
  "upside down photos", "wrong orientation", "bulk rotate", "rotate multiple",
  or any variation of wanting to rotate one or more photos.
version: 1.2.0
---

# Rotate Photos

## Connection Required: ALWAYS CHECK FIRST

**Before doing ANYTHING else in this skill, call `ping` on the Immich MCP server.**

- If `ping` succeeds → proceed with the skill normally.
- If `ping` fails or the MCP tools are not available → **STOP. Do not continue.** Tell the user:

> **Immich is not connected.** This plugin needs a running Immich MCP server to work.
>
> Run **/setup-immich-photo-manager** to configure your Immich connection.

**Do NOT skip this check. Do NOT try to run any other tool first. Always ping, always block if it fails.**

## How It Works

Rotation uses Immich's **non-destructive edits API**. The original file is never modified. Immich stores the rotation as a display transform that is applied when serving thumbnails and previews.

### Key Architecture Details

| Concept | Detail |
|---------|--------|
| API endpoint | `PUT /assets/{id}/edits` |
| Storage | Server-side, persists in Immich database forever |
| Original file | Never touched |
| Thumbnails | Served rotated via `?edited=true` query parameter |
| Accumulation | Each PUT **replaces** all edits, so the tool must read the current angle and add |
| Full circle | 360° → edits are deleted entirely (`isEdited` returns to `false`) |

### MCP Tools

| Tool | Purpose |
|------|---------|
| `rotate_assets` | Rotate by album_id or asset_ids. Accumulates with existing rotation. |
| `revert_asset_edits` | Remove all edits (rotation, crop, mirror), back to original. |

## Recommended User Workflow

1. **In Immich web UI**: Browse library, spot wrongly-rotated photos
2. **Multi-select** the rotated photos and add them to an album (e.g., "Fix Rotation")
3. **Use this skill**: `rotate_assets(album_id="...", angle=90)`
4. **Verify** in the Immich web UI: photos should appear rotated
5. **If wrong direction**: call again (rotation accumulates) or `revert_asset_edits(album_id="...")`
6. **Clean up**: Delete the temporary album when done (photos are not affected)

## Rotation Angles

| Angle | Direction | Use when |
|-------|-----------|----------|
| 90 | Clockwise | Photo tilted left |
| 180 | Upside down | Photo inverted |
| 270 | Counter-clockwise | Photo tilted right |

Calling `rotate_assets` multiple times **accumulates**:

| Current | + angle | Result |
|---------|---------|--------|
| 0° | +90° | 90° |
| 90° | +90° | 180° |
| 180° | +90° | 270° |
| 270° | +90° | 0° (edits removed, back to original) |

## Examples

### Rotate an entire album 90° clockwise

```
rotate_assets(album_id="uuid-of-album", angle=90)
```

### Rotate specific photos 270° (counter-clockwise)

```
rotate_assets(asset_ids=["uuid-1", "uuid-2", "uuid-3"], angle=270)
```

### Undo all rotation on an album

```
revert_asset_edits(album_id="uuid-of-album")
```

### Check current rotation state of an asset

Use `get_asset_info(asset_id)` and check:
- `isEdited`: `true` if any edits exist
- `width` / `height`: swapped if rotated 90° or 270°

For the exact angle, the tool reads `GET /assets/{id}/edits` internally.

## Showing Results to the User

When generating HTML galleries or visual reports, thumbnails must be fetched with `?edited=true` to reflect rotation. The MCP thumbnail tools (`get_asset_thumbnail`, `get_album_thumbnails`, `get_thumbnails_batch`) do this by default.

## Limitations

- **No auto-detection**: There is no reliable way to automatically find wrongly-rotated photos. The user must identify them visually and add them to an album.
- **CLIP search doesn't help**: Searching for "sideways photo" returns semantically similar images, not actually misrotated ones.
- **EXIF orientation**: Immich already handles EXIF orientation tags when generating thumbnails. Photos that appear wrong in the UI have a genuine orientation problem that needs manual correction.
- **Angle must be a multiple of 90**: Arbitrary angles are not supported.
- **Images only**: Immich's edits API applies to images, not videos, so a video inside a mixed album is not rotated. `get_capabilities` reports this behaviour for whichever server version is connected, and anything the server rejects comes back in the `failed` count with its reason.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Calling rotate_assets twice expecting it to stack without the accumulation fix | The tool handles this: it reads the current angle and adds. No action needed. |
| Trying to detect rotated photos with CLIP search | Don't. Have the user identify them visually and create an album. |
| Applying CSS rotation to thumbnails instead of using `?edited=true` | Always use the real edited thumbnail from the API. Never fake it with CSS. |
| Forgetting that edits are per-asset, not per-album | A photo rotated in Album A will also appear rotated in Album B. |

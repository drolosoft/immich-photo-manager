# MCP Tools Reference

The Immich Photo Manager MCP server exposes 87 tools that Claude can use to interact with your Immich instance. These tools are the building blocks that all skills use internally.

---

## Tool Categories

### Health & Info (4)

| Tool | Description | Returns |
|------|-------------|---------|
| `ping` | Check if the Immich server is reachable | Connection status |
| `get_server_version` | Get Immich server version | Version string |
| `get_capabilities` | What this server can do: version, feature flags (OCR, smart search...), known 2.x/3.x quirks | Capability report |
| `get_statistics` | Get library-wide statistics | Photo count, video count, storage used |

### Assets (8)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_asset_info` | Get full metadata for a specific asset | EXIF data, GPS, dates, dimensions, file info |
| `reverse_geocode` | Resolve GPS coordinates to city/state/country (Immich's offline geodata) | Place candidates |
| `update_asset_metadata` | Update asset metadata (dates, GPS, description, favorites, rating) | Updated asset object |
| `rotate_assets` | Rotate assets by album or IDs (90°, 180°, 270°) — non-destructive | Count of rotated/failed assets |
| `revert_asset_edits` | Remove all edits (rotation, crop, mirror) from assets — revert to original | Count of reverted/failed assets |
| `get_map_markers` | Get GPS markers for all geotagged assets | Array of {lat, lng, id} for mapping |
| `upload_asset` | Upload a local file to Immich (25MB limit, extension filter, optional album) | Uploaded asset object with ID |
| `list_assets` | List assets with filters (favorites, archived, trashed, type) | Paginated asset list |

### Search (9)

| Tool | Description | Returns |
|------|-------------|---------|
| `search_metadata` | Search by EXIF metadata: location, camera, dates, type, OCR text | Paginated asset list |
| `search_smart` | AI-powered visual search via CLIP embeddings | Ranked asset list by visual similarity |
| `search_explore` | Library overview: one representative asset per city and concept | Explore fields with value + asset id |
| `search_cities` | Every city in the library, one representative asset each (no threshold) | {city, country, asset_id, date} rows |
| `search_places` | Look a place name up in Immich's built-in gazetteer | Place names with coordinates |
| `search_suggestions` | Distinct values present in the library for one field (city, camera-make...) | String list |
| `search_random` | Random assets, optionally filtered (city, camera, favorite, OCR) | Asset list (max 100) |
| `search_statistics` | Count matching assets WITHOUT fetching them | {total} |
| `search_large_assets` | Biggest files first — what is eating storage | {asset_id, filename, size_mb, date} rows |

**`search_metadata` parameters:**

| Parameter | Type | Example |
|-----------|------|---------|
| `city` | string | "Barcelona" |
| `state` | string | "Catalonia" |
| `country` | string | "Spain" |
| `make` | string | "Apple" |
| `model` | string | "iPhone 14 Pro" |
| `taken_after` | ISO date | "2023-06-01" |
| `taken_before` | ISO date | "2023-06-30" |
| `asset_type` | string | "IMAGE" or "VIDEO" |
| `is_favorite` | boolean | true |
| `ocr` | string | "boarding pass" (text recognized inside the image; needs OCR enabled on the server) |
| `page` | number | 1 |
| `size` | number | 50 (max 200) |

**`search_smart` parameters:**

| Parameter | Type | Example |
|-----------|------|---------|
| `query` | string | "sunset at the beach" |
| `city` | string | "Barcelona" (optional filter) |
| `state` | string | "Catalonia" (optional filter) |
| `country` | string | "Spain" (optional filter) |
| `taken_after` | ISO date | "2023-06-01" |
| `taken_before` | ISO date | "2023-06-30" |
| `ocr` | string | "Renfe" (text recognized inside the image, combined with the visual query) |
| `page` | number | 1 |
| `size` | number | 50 (max 200) |

### Stacks (5)

Group near-identical shots (bursts, retries of the same scene) under one cover asset — a gentler cleanup than deleting.

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `create_stack` | Group assets into a stack; the first id becomes the cover | Yes |
| `list_stacks` | List every stack with its assets | No |
| `get_stack` | One stack with its assets | No |
| `update_stack` | Change which asset fronts the stack | Yes |
| `delete_stack` | Dissolve a stack (the assets stay in the library) | Yes |

### Partners (5)

Immich's family sharing: each side keeps its own library but can see the other's.

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_users` | Users visible on the server (to find the partner's id) | No |
| `list_partners` | Who shares with this account and who it shares with | No |
| `create_partner` | Share this library with another user | Yes |
| `update_partner` | Mix a partner's photos into the timeline, or keep them separate | Yes |
| `remove_partner` | Stop sharing (their photos are not touched) | Yes |

### Activities (3)

Comments and likes on shared albums.

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_activities` | Comments and likes on an album (or one asset in it) | No |
| `create_activity` | Post a comment or a like | Yes |
| `delete_activity` | Remove one comment or like | Yes |

### Download (2)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_download_info` | Size of the zip an album/selection would make, before building it | {total_size_mb, asset_count} |
| `download_archive` | Album or selection as one zip, streamed to a local path, never overwrites | JSON {path, bytes, assets} |

### Memories (4)

Immich's "on this day" collections — photos from the same date in past years.

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_memories` | List memories, optionally the ones shown on a given day | No |
| `create_memory` | Create an "on this day" memory from chosen assets (needs the past year) | Yes |
| `update_memory` | Save/unsave a memory, move its date, mark it seen | Yes |
| `delete_memory` | Delete a memory (the photos stay in the library) | Yes |

### Timeline (2)

The cheap way to browse by date: one call maps the whole library month by month.

| Tool | Description | Returns |
|------|-------------|---------|
| `get_timeline_buckets` | One bucket per month with its asset count (filterable by album, person, tag) | {timeBucket, count} rows |
| `get_timeline_bucket` | The assets of one month bucket | {asset_id, date, is_image, city...} rows |

### Albums (7)

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_albums` | List all albums with asset counts | No |
| `get_album` | Get album details including all asset IDs | No |
| `create_album` | Create a new album with name, description, and optional initial assets | Yes |
| `update_album` | Update album name or description | Yes |
| `delete_album` | Delete an album (photos are NOT deleted) | Yes |
| `add_assets_to_album` | Add assets to an album by ID | Yes |
| `remove_assets_from_album` | Remove assets from an album (photos stay in library) | Yes |

### Sharing (5)

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_shared_links` | List all shared links | No |
| `create_shared_link` | Create a public link for an album | Yes |
| `get_shared_link` | Get details of a specific shared link | No |
| `update_shared_link` | Update shared link settings (expiry, password, permissions) | Yes |
| `delete_shared_link` | Delete a shared link (revokes access) | Yes |

### Thumbnails (3)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_asset_thumbnail` | Get base64-encoded thumbnail for a single asset | Base64 image data + MIME type |
| `get_album_thumbnails` | Get base64 thumbnails for assets in an album (batch) | Array of {asset_id, data, mime_type, filename, date} |
| `get_thumbnails_batch` | Get base64 thumbnails for a list of asset IDs (no album needed) | Array of {asset_id, data, mime_type, filename, date} |

### Images (3)

Image-block variants of the thumbnail tools — return MCP `ImageContent` for clients that render images inline (Open WebUI, Claude Desktop). The `get_*_thumbnail(s)` tools above stay the default and return base64 JSON for HTML gallery embedding.

| Tool | Description | Returns |
|------|-------------|---------|
| `get_asset_image` | Get a single asset's thumbnail as an image block | Image (ImageContent) |
| `get_album_images` | Get an album's thumbnails as image blocks | List of images |
| `get_images_batch` | Get thumbnails for arbitrary asset IDs as image blocks | List of images |

### Video (2)

Immich keeps one poster thumbnail per video and no per-frame previews. These tools download the video (`GET /assets/{id}/video/playback`) and cut frames locally, so a model can "watch" a clip, a segment of it (`start`/`end`), or a fixed cadence (`interval`, down to one frame per second). The decoder is PyAV, installed with the package since 1.7.1 (`ffmpeg` on PATH works as a fallback); without either they return a clear error naming both. Above 12 frames the tool asks for confirmation instead of extracting: it returns `{confirm_required: true, frames_planned, estimated_tokens, ...}` so the caller can tell the user the cost before spending it; call again with `confirm=true` to proceed. Hard cap: 120 frames per call.

| Tool | Description | Returns |
|------|-------------|---------|
| `get_video_frames` | Frames of a video as image blocks, evenly spaced or at a fixed interval, over the whole clip or a `start`/`end` segment (default 6, cap 120, confirmation above 12) | List of images, or a confirmation/error JSON |
| `get_video_frames_json` | Same frames as base64 JPEG with timestamps, for galleries | JSON |

### Export (2)

Turn an album or a selection into a PDF, built on the machine running the server.

| Tool | Description | Returns |
|------|-------------|---------|
| `get_export_preview` | List what `export_pdf` would include (id, type, filename, date, place, people, video duration) — read-only | JSON |
| `export_pdf` | Build the PDF (cover, index, places, one section per asset) from an album or asset IDs | JSON {path, pages, bytes, ...} |

### Configuration (2)

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `get_connection_info` | Return the Immich base URL and masked API key | No |
| `update_credentials` | Update Immich URL and API key at runtime (persisted to disk, no restart needed) | Yes |

### People & Faces (8)

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_people` | List all recognized people (paginated, supports hidden) | No |
| `get_person` | Get full details for a specific person | No |
| `update_person` | Update person name, birth date, hidden/favorite status, color | Yes |
| `merge_people` | Merge multiple people into one (DESTRUCTIVE — cannot be undone) | Yes |
| `search_people` | Search people by name | No |
| `get_person_thumbnail` | Get base64-encoded face thumbnail for a person | No |
| `get_asset_faces` | Get all detected faces in an asset with person assignments | No |
| `reassign_face` | Reassign a face to a different person (correct misidentification) | Yes |

### Trash & Deletion (4)

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `delete_assets` | Move assets to trash (default) or permanently delete (force=True) | Yes |
| `empty_trash` | Permanently delete ALL trashed assets (IRREVERSIBLE) | Yes |
| `restore_trash` | Restore all trashed assets back to library | Yes |
| `restore_assets` | Restore specific assets from trash by ID | Yes |

### Duplicates (2)

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `get_duplicates` (optional `album_id`) | Get all ML-detected duplicate groups with similarity scores | No |
| `resolve_duplicates` | Resolve duplicate groups — specify which to keep, which to trash | Yes |

### Tags (7)

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_tags` | List all tags with IDs, names, colors | No |
| `get_tag` | Get tag details | No |
| `create_tag` | Create a new tag with name and optional color | Yes |
| `update_tag` | Update tag color (Immich's API cannot rename tags) | Yes |
| `delete_tag` | Delete a tag (removed from all assets) | Yes |
| `tag_assets` | Add a tag to multiple assets | Yes |
| `untag_assets` | Remove a tag from multiple assets | Yes |

---

## Tool Details

### `get_asset_thumbnail`

```json
{
  "asset_id": "uuid-of-asset",
  "size": "thumbnail"
}
```

`size` accepts `"thumbnail"` (~250px, default) or `"preview"` (~1440px). Returns `{data, mime_type}` with base64-encoded image data. Used by the gallery HTML generator to embed thumbnails directly in self-contained HTML files.

### `get_album_thumbnails`

```json
{
  "album_id": "uuid-of-album",
  "limit": 20,
  "size": "thumbnail"
}
```

Batch version of `get_asset_thumbnail` — fetches thumbnails for assets in an album in a single call. Returns album info and a list of thumbnail entries with asset IDs, base64 data, filenames, and dates. Default limit is 20, max 50. This is the primary tool for gallery HTML generation when working with albums.

### `get_thumbnails_batch`

```json
{
  "asset_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "limit": 20,
  "size": "thumbnail"
}
```

Like `get_album_thumbnails` but works with arbitrary asset IDs — no album needed. Use this when displaying search results or orphan photos that aren't in any album. Default limit is 20, max 50.

### `get_asset_image` / `get_album_images` / `get_images_batch`

Image-block variants of `get_asset_thumbnail`, `get_album_thumbnails`, and `get_thumbnails_batch`. Same parameters, but they return MCP `ImageContent` blocks instead of base64 JSON, so clients that render images inline (Open WebUI, Claude Desktop) show the photos directly. They carry no filenames/dates — for HTML gallery generation (which needs the metadata and embeds base64 as `data:` URIs), keep using the JSON `get_*_thumbnail(s)` tools. These are additive; the JSON tools remain the default.

### `get_video_frames` / `get_video_frames_json`

**Parameters:**
- `asset_id` (string, required): The video asset's UUID
- `count` (int, optional): Frames to extract, evenly spaced over the segment. Default 6. Ignored when `interval > 0`.
- `size` (string, optional): `"thumbnail"` (250px, ~1.6k tokens/frame, default) or `"preview"` (1440px, ~6.4k tokens/frame)
- `start` / `end` (float, optional): Segment bounds in seconds (default 0 / 0, where `end=0` means to the end of the clip)
- `interval` (float, optional): One frame every N seconds instead of `count` (e.g. `interval=1` for one frame per second — the maximum granularity)
- `confirm` (bool, optional): Required (`true`) when the plan produces more than 12 frames
- `sheet` (bool, optional): pack the frames into contact sheets (30 per image, the timestamp burned under each); a long video becomes one or two images and needs no confirmation

Frames are taken at the centre of equal time bins within the segment, so a 3 s clip with `count=3` yields 0.5 s, 1.5 s, 2.5 s (never the black first frame). `get_video_frames` returns JPEG image blocks in time order; `get_video_frames_json` returns `{asset_id, duration, backend, count, frames: [{timestamp, data, type}]}` for HTML galleries.

**Confirmation gate:** a plan over 12 frames is not extracted automatically. Instead the tool returns `{confirm_required: true, asset_id, duration, segment: [start, end], frames_planned, estimated_tokens, hint}` — tell the user the number of frames and the estimated tokens, and call again with `confirm=true` only if they agree. The hard cap is 120 frames per call regardless of `confirm`.

**Cost:** every frame is one image for the model. Six thumbnail frames are cheap; a `interval=1` pass over a long clip is not. Start with the default and narrow with `start`/`end` or `interval` only for the clips that need it.

**Decoder:** PyAV is tried first (in-process, a dependency of the package since 1.7.1), then the `ffmpeg` binary. If PyAV was removed and there is no ffmpeg, the error message says so. The whole video file is downloaded to a temp file and deleted after extraction.

**Example:**
```
"Show me 6 frames of that hypercar clip"
"What happens in this video? Cut 8 frames"
"Cut one frame per second between 8s and 12s of that clip"
```

### `export_pdf` / `get_export_preview`

Turn an album or a selection into a PDF (cover, index, places, one section per asset), built on the machine running the server. `get_export_preview` is the read-only look-before-you-leap step; `export_pdf` does the work.

**Common parameters (both tools):**
- `album_id` (string) or `asset_ids` (list of strings): exactly one of the two must be passed
- `limit` (int, optional): max assets, 1-500, default 100

**`get_export_preview` returns:** JSON `{title, count, assets: [{id, type, filename, taken_at, place, people, duration}], warnings: []}` — nothing here costs tokens on images, it is metadata only.

**`export_pdf` parameters:**
- `output_path` (string, optional): where to write the file, on the machine running the server. Default `~/Desktop/<title>.pdf`. A directory is accepted (the file is placed inside it as `<title>.pdf`); a path with no `.pdf` extension gets one appended. An existing file is never overwritten — `report.pdf` becomes `report-2.pdf`, `report-3.pdf`, ...
- `title` (string, optional): cover title. Default: the album's name, or `"Immich export <date>"`.
- `captions` (dict, optional): `{asset_id: text}` — Claude's own description of each photo/video after looking at it. Immich's own metadata (date, place, camera, people, tags) is always included regardless of captions.
- `layout` (string, optional): `"detail"` (one asset per page with its data, default), `"grid"` (six per page) or `"photobook"` (one full-page image per asset, fitted without cropping, caption under it; pair with `frames_per_video=1` so a video reads like a photo)
- `frames_per_video` (int, optional): frames per video, evenly spaced, 0-120, default 4 (`0` = poster only)
- `frame_interval` (float, optional): one frame every N seconds instead of `frames_per_video` (same 120 cap)
- `image_size` (string, optional): `"preview"` (default, 1440px), `"thumbnail"` (250px) or `"original"` for photos: the stored file at print quality, re-encoded to at most 3000px on the long side (a format the server cannot decode, like some HEIC, falls back to preview with a note)
- `language` (string, optional): `"en"` (default) or `"es"` for the fixed labels on the pages (Index, Places, Camera, page numbers); captions stay as written
- `frame_times` (object, optional): `{asset_id: [seconds, ...]}` exact moments for specific videos, chosen after looking at their frames; wins over `frames_per_video`/`frame_interval` for the listed videos ("use the frame at second 8 for this clip")
- `frame_size` (string, optional): size of the video frames inside the PDF: `"auto"` (default: preview quality up to 4 frames per video, thumbnail above), `"preview"` or `"thumbnail"`
- `map` (bool, optional): add an OpenStreetMap map to the Places page (fetches tiles from `tile.openstreetmap.org`)
- `return_base64` (bool, optional): also return the PDF bytes in the JSON response (skipped above 2 MB; every MB is roughly 350k tokens in the conversation)

**`export_pdf` returns:** JSON `{path, pages, bytes, assets_included, assets_skipped: [{id, reason}], warnings: []}`, or `{"pdf_base64": "..."}` in addition when `return_base64=true`.

**Live Photos count once:** the motion clip a still points at through `livePhotoVideoId` is folded into its photo in both tools, with a note in `warnings`.

**PDF structure:** cover page (title, subtitle, first image) → index (one line per asset, each linking to its page) → Places (a table of country/city/count, plus a stitched OpenStreetMap image when `map=true` and GPS data exists) → one detail page per asset in `"detail"` layout (metadata block plus the photo or, for a video, its frames laid out four per row with a timestamp under each), a six-per-page grid in `"grid"` layout, or one full-page image with the caption under it in `"photobook"` → a footer with the plugin version, server URL, and page number on every page.

**Cost:** frames that go into the PDF cost no tokens — they never enter the conversation. Only the frames you look at while writing captions do. A PDF with `frames_per_video=120` on ten videos costs nothing extra over the default; looking at 120 frames to caption them does.

**What leaves the network:** Immich → your machine (metadata and images, same as any other tool). The PDF itself stays on disk and is not sent anywhere unless `return_base64=true`, in which case it goes back over MCP like any other tool result. `map=true` is the only call that reaches outside your Immich: it fetches tiles from `tile.openstreetmap.org`.

**Requirements:** none beyond the package since 1.7.1 (`fpdf2` and PyAV are dependencies). On the Claude Code plugin route, `pip3 install -r src/requirements.txt` after updating.

**Example:**
```
"Make a PDF of the hypercars album with what you see in each video"
"Export the photos of Curie to a PDF, grid layout"
"Preview what would be exported before we look at anything"
```

### `update_asset_metadata`

```json
{
  "asset_id": "uuid-of-asset",
  "date_time_original": "2019-07-14T15:23:41.000Z",
  "latitude": 41.3874,
  "longitude": 2.1686
}
```

Updates metadata fields on a single asset. Only provided fields are modified — omitted fields are left unchanged. Supports:

| Parameter | Type | Description |
|-----------|------|-------------|
| `asset_id` | string | **Required.** The asset to update |
| `date_time_original` | ISO 8601 string | Original capture date and time |
| `latitude` | number (-90 to 90) | GPS latitude |
| `longitude` | number (-180 to 180) | GPS longitude |
| `description` | string | Asset description text |
| `is_favorite` | boolean | Mark as favorite |
| `rating` | integer (1-5) | Star rating |

Used by the metadata-fixer skill to repair timestamps, infer GPS from neighboring photos, and correct timezone offsets — all with user approval before any change is applied.

> **Known limitation:** Immich writes a `.xmp` sidecar file when updating EXIF data. If your photos are in an external library whose path contains special characters (e.g., emojis), exiftool may fail to create the sidecar and the update will silently revert. Photos uploaded directly through Immich are not affected.

### `rotate_assets`

```json
{
  "asset_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "angle": 90
}
```

Applies a non-destructive rotation to one or more assets. The original file is never modified — Immich stores the transform as a display edit. Supports bulk operations: pass multiple asset IDs to rotate an entire selection in one call.

| Parameter | Type | Description |
|-----------|------|-------------|
| `asset_ids` | list[string] | Asset IDs to rotate (provide this OR `album_id`) |
| `album_id` | string | Rotate all assets in this album (provide this OR `asset_ids`) |
| `angle` | integer | Clockwise rotation: 90, 180, or 270. Default: 90 |

Returns `{rotated: count, failed: count, angle: degrees, album?: name}`. Failed assets (if any) include the asset ID and error message.

### `revert_asset_edits`

```json
{
  "album_id": "uuid-of-album"
}
```

Removes all non-destructive edits (rotation, crop, mirror) from assets, reverting them to their original appearance. Accepts either `asset_ids` or `album_id`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `asset_ids` | list[string] | Asset IDs to revert (provide this OR `album_id`) |
| `album_id` | string | Revert all assets in this album (provide this OR `asset_ids`) |

Returns `{reverted: count, failed: count, album?: name}`.

### `create_album`

```json
{
  "name": "🇮🇹 Roma, Italia",
  "description": "Summer 2023 — 45 photos across historic center, Trastevere, and Vatican",
  "asset_ids": ["uuid-1", "uuid-2"]
}
```

Returns: Album object with `id` for use with other tools. `asset_ids` is optional — pass it to add photos at creation time.

### `add_assets_to_album`

```json
{
  "album_id": "uuid-of-album",
  "asset_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

Accepts up to ~2000 asset IDs per call. For larger batches, make multiple calls.

### `create_shared_link`

```json
{
  "album_id": "uuid-of-album",
  "show_metadata": true,
  "allow_download": false
}
```

Returns: Shared link URL that can be accessed without authentication.

### `update_credentials`

```json
{
  "base_url": "https://photos.example.com",
  "api_key": "new-api-key-here"
}
```

Updates the Immich connection credentials at runtime. The new credentials are persisted to disk and take effect immediately — no restart required. Use this when the API key has been rotated or when switching Immich instances.

### `list_people`

```json
{
  "page": 1,
  "size": 50,
  "with_hidden": false
}
```

Returns `{total, page, people: [...]}` with person objects containing `id`, `name`, `birthDate`, `isHidden`, `thumbnailPath`, and face count. Paginated — iterate pages for large libraries.

### `update_person`

```json
{
  "person_id": "uuid-of-person",
  "name": "María",
  "birth_date": "1990-05-15"
}
```

Only provided fields are updated — omitted fields are left unchanged. Supports: `name`, `birth_date`, `is_hidden`, `is_favorite`, `feature_face_asset_id`, `color`.

### `merge_people`

```json
{
  "person_id": "uuid-to-keep",
  "merge_ids": ["uuid-to-merge-1", "uuid-to-merge-2"]
}
```

**DESTRUCTIVE:** Merges all face assignments from `merge_ids` into `person_id`. The merged people cease to exist. This cannot be undone. Use `search_people` or `list_people` to identify merge candidates first.

### `reassign_face`

```json
{
  "face_id": "uuid-of-face",
  "person_id": "uuid-of-correct-person"
}
```

Corrects face recognition mistakes. Get face IDs from `get_asset_faces`, then reassign to the correct person. Useful for faces Immich misidentified.

### `delete_assets`

```json
{
  "asset_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "force": false
}
```

With `force=false` (default): moves assets to trash — recoverable with `restore_assets`. With `force=true`: **permanently deletes** assets — cannot be recovered. Returns `{deleted: count, force: bool, warning: "..."}`.

### `get_duplicates`

Returns all duplicate groups detected by Immich's ML engine. Each group contains visually similar assets with similarity scores. No parameters — Immich manages detection automatically. Use this to find duplicates, then `resolve_duplicates` to act on them.

### `resolve_duplicates`

```json
{
  "groups": [
    {
      "duplicateId": "group-uuid",
      "keepAssetIds": ["uuid-to-keep"],
      "trashAssetIds": ["uuid-to-trash-1", "uuid-to-trash-2"]
    }
  ]
}
```

Resolves duplicate groups by specifying which assets to keep and which to trash (the legacy keys `assetIds`/`trashIds` are still accepted). Uses `POST /duplicates/resolve` (Immich ≥ 2.6); on older servers the rejected assets are trashed and the duplicate flag cleared. Trashed assets can be restored via `restore_assets` or `restore_trash`.

### `search_metadata` — Pagination

Results are paginated. First call returns `total` count:

```json
{
  "assets": [...],
  "page": 1,
  "total": 234
}
```

For large result sets, iterate pages: `page=1`, `page=2`, etc., with `size=200` for maximum efficiency.

### `search_smart` — CLIP Search

Uses Immich's machine learning container to find visually similar photos. Requires the ML container to be running. Can be combined with location and date filters for more precise results.

Good queries: "sunset", "birthday cake", "mountains with snow", "group photo at dinner"
Less effective: Very specific queries, proper nouns, text-heavy images

---

## Architecture

```
Claude ←→ MCP (stdio) ←→ Python Server ←→ Immich REST API
                                              your-instance
```

- **Protocol**: stdio (standard MCP transport for Claude Code / Cowork)
- **Auth**: Immich API key passed via environment variable (never exposed to Claude)
- **Thumbnail delivery**: Base64 data URIs embedded directly in self-contained HTML galleries — required because the Cowork viewer runs in an `about:` sandbox that blocks all external network requests

For a detailed explanation of the thumbnail delivery architecture and why base64 embedding is the only viable approach in Cowork, see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Rate Limits

The MCP server does not impose its own rate limits, but Immich may:

- Search operations: Generally unlimited for self-hosted instances
- Bulk operations (add 2000 assets to album): May take 2-5 seconds
- CLIP search: Depends on ML container resources — may be slower on first query

For bulk operations, skills automatically batch requests (typically 100-2000 items per call) and report progress.

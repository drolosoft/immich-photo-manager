# MCP Tools Reference

The Immich Photo Manager MCP server exposes 94 tools that Claude can use to interact with your Immich instance. These tools are the building blocks that all skills use internally.

---

## Tool Categories

### Health & Info (4)

| Tool | Description | Returns |
|------|-------------|---------|
| `ping` | Check if the Immich server is reachable | Connection status |
| `get_server_version` | Get Immich server version | Version string |
| `get_capabilities` | What this server can do: version, feature flags (OCR, smart search...), known 2.x/3.x quirks | Capability report |
| `get_statistics` | Get library-wide statistics | Photo count, video count, storage used |

### Assets (9)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_asset_info` | Get full metadata for a specific asset (`with_notes=true` adds the plugin's notes) | EXIF data, GPS, dates, dimensions, file info |
| `reverse_geocode` | Resolve GPS coordinates to city/state/country (Immich's offline geodata) | Place candidates |
| `update_asset_metadata` | Update asset metadata (dates, GPS, description, favorites, rating) | Updated asset object |
| `update_assets_metadata` | The same fields on MANY assets in one call (a scanned roll gets its date, a trip its GPS) | {success, updated} |
| `rotate_assets` | Rotate assets by album or IDs (90°, 180°, 270°), non-destructive | Count of rotated/failed assets |
| `revert_asset_edits` | Remove all edits (rotation, crop, mirror) from assets, revert to original | Count of reverted/failed assets |
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
| `search_large_assets` | Biggest files first, what is using the most storage | {asset_id, filename, size_mb, date} rows |

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
| `person_ids` | string[] | ids from `list_people`, only assets showing all of them |
| `tag_ids` | string[] | ids from `list_tags` |
| `album_ids` | string[] | only assets inside these albums |
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
| `person_ids` / `tag_ids` / `album_ids` | string[] | same filters as `search_metadata` |
| `page` | number | 1 |
| `size` | number | 50 (max 200) |

### Stacks (5)

Group near-identical shots (bursts, retries of the same scene) under one cover asset, a gentler cleanup than deleting.

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
| `get_download_info` | Size of the zip an album/selection would make, before building it | {total_size_mb, asset_count, archives} |
| `download_archive` | Album or selection as one zip, streamed to a local path, never overwrites | JSON {path, bytes, assets} |

### Notes (5)

The plugin's own memory on each asset, stored in Immich's per-asset metadata under one key (`immich-photo-manager`). Invisible in the Immich UI and not searchable. Tags stay the visible state; notes carry the why, and let a later session skip what was already reviewed.

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `review_assets` | Remember a verdict (`keep`, `delete_candidate`, `duplicate_of`, `needs_check`) with its reason; last 10 kept | Yes |
| `record_action` | Remember what the plugin did to assets and why (album, date fix, rotation); last 10 kept | Yes |
| `get_asset_notes` | One asset's reviews and actions | No |
| `get_assets_notes` | Which of many assets already carry notes, with their last verdict (the "skip what I reviewed" call) | No |
| `clear_asset_notes` | Forget the plugin's notes (other apps' metadata untouched) | Yes |

`get_asset_info(asset_id, with_notes=true)` includes the same notes inline.

### Memories (4)

Immich's "on this day" collections: photos from the same date in past years.

| Tool | Description | Modifies? |
|------|-------------|-----------|
| `list_memories` | List memories, optionally the ones shown on a given day | No |
| `create_memory` | Create an "on this day" memory from chosen assets (needs the past year) | Yes |
| `update_memory` | Save/unsave a memory, move its date, mark it seen | Yes |
| `delete_memory` | Delete a memory (the photos stay in the library) | Yes |

### Timeline (3)

The cheap way to browse by date: one call maps the whole library month by month.

| Tool | Description | Returns |
|------|-------------|---------|
| `get_timeline_buckets` | One bucket per month with its asset count (filterable by album, person, tag) | {timeBucket, count} rows |
| `get_timeline_bucket` | The assets of one month bucket | {asset_id, date, is_image, city...} rows |
| `get_calendar_heatmap` | Photos per day over a range, gaps and busy periods. Native on Immich 3.x, built from the timeline on 2.x | {source, total, series[{date, count}]} |

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

Image-block variants of the thumbnail tools. They return MCP `ImageContent` for clients that render images inline (Open WebUI, Claude Desktop). The `get_*_thumbnail(s)` tools above stay the default and return base64 JSON for HTML gallery embedding.

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
| `get_export_preview` | List what `export_pdf` would include (id, type, filename, date, place, people, video duration), read-only | JSON |
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
| `merge_people` | Merge multiple people into one (DESTRUCTIVE, cannot be undone). Previews names first; `confirm=true` merges | Yes |
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
| `resolve_duplicates` | Resolve duplicate groups: specify which to keep, which to trash | Yes |

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

Batch version of `get_asset_thumbnail`: fetches thumbnails for assets in an album in a single call. Returns album info and a list of thumbnail entries with asset IDs, base64 data, filenames, and dates. Default limit is 20, max 50. This is the primary tool for gallery HTML generation when working with albums.

### `get_thumbnails_batch`

```json
{
  "asset_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "limit": 20,
  "size": "thumbnail"
}
```

Like `get_album_thumbnails` but works with arbitrary asset IDs, no album needed. Use this when displaying search results or orphan photos that aren't in any album. Default limit is 20, max 50.

### `get_asset_image` / `get_album_images` / `get_images_batch`

Image-block variants of `get_asset_thumbnail`, `get_album_thumbnails`, and `get_thumbnails_batch`. Same parameters, but they return MCP `ImageContent` blocks instead of base64 JSON, so clients that render images inline (Open WebUI, Claude Desktop) show the photos directly. They carry no filenames/dates. For HTML gallery generation (which needs the metadata and embeds base64 as `data:` URIs), keep using the JSON `get_*_thumbnail(s)` tools. These are additive; the JSON tools remain the default.

### `get_video_frames` / `get_video_frames_json`

**Parameters:**
- `asset_id` (string, required): The video asset's UUID
- `count` (int, optional): Frames to extract, evenly spaced over the segment. Default 6. Ignored when `interval > 0`.
- `size` (string, optional): `"thumbnail"` (250px, ~1.6k tokens/frame, default) or `"preview"` (1440px, ~6.4k tokens/frame)
- `start` / `end` (float, optional): Segment bounds in seconds (default 0 / 0, where `end=0` means to the end of the clip)
- `interval` (float, optional): One frame every N seconds instead of `count` (e.g. `interval=1` for one frame per second, the maximum granularity)
- `confirm` (bool, optional): Required (`true`) when the plan produces more than 12 frames
- `sheet` (bool, optional): pack the frames into contact sheets (30 per image, the timestamp burned under each); a long video becomes one or two images and needs no confirmation

Frames are taken at the centre of equal time bins within the segment, so a 3 s clip with `count=3` yields 0.5 s, 1.5 s, 2.5 s (never the black first frame). `get_video_frames` returns JPEG image blocks in time order; `get_video_frames_json` returns `{asset_id, duration, backend, count, frames: [{timestamp, data, type}]}` for HTML galleries.

**Confirmation gate:** a plan over 12 frames is not extracted automatically. Instead the tool returns `{confirm_required: true, asset_id, duration, segment: [start, end], frames_planned, estimated_tokens, hint}`. Tell the user the number of frames and the estimated tokens, and call again with `confirm=true` only if they agree. The hard cap is 120 frames per call regardless of `confirm`.

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

**`get_export_preview` returns:** JSON `{title, count, assets: [{id, type, filename, taken_at, place, people, duration}], warnings: []}`. Nothing here costs tokens on images, it is metadata only.

**`export_pdf` parameters:**
- `output_path` (string, optional): where to write the file, on the machine running the server. Default `~/Desktop/<title>.pdf`. A directory is accepted (the file is placed inside it as `<title>.pdf`); a path with no `.pdf` extension gets one appended. An existing file is never overwritten: `report.pdf` becomes `report-2.pdf`, `report-3.pdf`, ...
- `title` (string, optional): cover title. Default: the album's name, or `"Immich export <date>"`.
- `captions` (dict, optional): `{asset_id: text}`, Claude's own description of each photo/video after looking at it. Immich's own metadata (date, place, camera, people, tags) is always included regardless of captions.
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

**Cost:** frames that go into the PDF cost no tokens: they never enter the conversation. Only the frames you look at while writing captions do. A PDF with `frames_per_video=120` on ten videos costs nothing extra over the default; looking at 120 frames to caption them does.

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

Updates metadata fields on a single asset. Only provided fields are modified, and omitted fields are left unchanged. Supports:

| Parameter | Type | Description |
|-----------|------|-------------|
| `asset_id` | string | **Required.** The asset to update |
| `date_time_original` | ISO 8601 string | Original capture date and time |
| `latitude` | number (-90 to 90) | GPS latitude |
| `longitude` | number (-180 to 180) | GPS longitude |
| `description` | string | Asset description text |
| `is_favorite` | boolean | Mark as favorite |
| `rating` | integer (1-5) | Star rating |

Used by the metadata-fixer skill to repair timestamps, infer GPS from neighboring photos, and correct timezone offsets, all with user approval before any change is applied.

> **Known limitation:** Immich writes a `.xmp` sidecar file when updating EXIF data. If your photos are in an external library whose path contains special characters (e.g., emojis), exiftool may fail to create the sidecar and the update will silently revert. Photos uploaded directly through Immich are not affected.

### `rotate_assets`

```json
{
  "asset_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "angle": 90
}
```

Applies a non-destructive rotation to one or more assets. The original file is never modified: Immich stores the transform as a display edit. Supports bulk operations: pass multiple asset IDs to rotate an entire selection in one call.

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
  "description": "Summer 2023, 45 photos across historic center, Trastevere, and Vatican",
  "asset_ids": ["uuid-1", "uuid-2"]
}
```

Returns: Album object with `id` for use with other tools. `asset_ids` is optional: pass it to add photos at creation time.

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

Updates the Immich connection credentials at runtime. The new credentials are persisted to disk and take effect immediately, no restart required. Use this when the API key has been rotated or when switching Immich instances.

### `list_people`

```json
{
  "page": 1,
  "size": 50,
  "with_hidden": false
}
```

Returns `{total, page, people: [...]}` with person objects containing `id`, `name`, `birthDate`, `isHidden`, `thumbnailPath`, and face count. Paginated: iterate pages for large libraries.

### `update_person`

```json
{
  "person_id": "uuid-of-person",
  "name": "María",
  "birth_date": "1990-05-15"
}
```

Only provided fields are updated, and omitted fields are left unchanged. Supports: `name`, `birth_date`, `is_hidden`, `is_favorite`, `feature_face_asset_id`, `color`.

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

With `force=false` (default): moves assets to trash, recoverable with `restore_assets`. With `force=true`: **permanently deletes** assets, which cannot be recovered. Returns `{deleted: count, force: bool, warning: "..."}`.

### `get_duplicates`

Returns all duplicate groups detected by Immich's ML engine. Each group contains visually similar assets with similarity scores. No parameters. Immich manages detection automatically. Use this to find duplicates, then `resolve_duplicates` to act on them.

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

### `search_metadata`: Pagination

Results are paginated. First call returns `total` count:

```json
{
  "assets": [...],
  "page": 1,
  "total": 234
}
```

For large result sets, iterate pages: `page=1`, `page=2`, etc., with `size=200` for maximum efficiency.

### `search_smart`: CLIP Search

Uses Immich's machine learning container to find visually similar photos. Requires the ML container to be running. Can be combined with location and date filters for more precise results.

Good queries: "sunset", "birthday cake", "mountains with snow", "group photo at dinner"
Less effective: Very specific queries, proper nouns, text-heavy images

### `get_capabilities`

Call this once at the start of a session, before offering anything that depends on a server feature. It answers "can this Immich do OCR, smart search, faces, map?" and "which Immich major is this?", so a search that would come back empty is never offered and a missing feature is not mistaken for an empty library. No parameters.

Returns `{server_version, immich_major, features, quirks}`. `features` is Immich's own flag object (`ocr`, `smartSearch`, `facialRecognition`, `map`, `trash`, and whatever else that version reports). `quirks` is a list of plain sentences the flags do not cover: the edits API applies to images only, tags can change color but never be renamed, videos expose a single thumbnail. On Immich 3.x it adds that fetching an album does not include its assets (the plugin already works around it) and that `list_people` hides people below a face-count threshold. On 2.x it adds that searching by asset ids is ignored, so the plugin fetches each asset one by one.

A scoped API key can be allowed to read the version and still be refused the feature flags. When that happens the call does not fail: `features` comes back empty and a `features_note` explains that whether OCR, smart search or facial recognition are on is unknown, while the version and the quirks are still accurate.

### `search_explore` / `search_cities`

The two "what is in this library?" calls, for a library nobody has described yet. `search_explore` is Immich's own Explore page: one representative asset per city and per detected concept. `search_cities` is the same idea for places only, without Immich's five-asset threshold, so it is the reliable one on a small library. Neither takes parameters.

`search_explore` returns `{total, fields}`, with `total` counting the fields that came back and each field carrying its name (`exifInfo.city`, and the concept field) and `items` pairing each value with one representative `asset_id`. `search_cities` returns `{total, cities}` with `{city, country, asset_id, date}` per row. Feed the ids to `get_thumbnails_batch` to show them.

### `search_suggestions`

The exact strings the library holds for one field, so a filter is never guessed. Ask for the cities before calling `search_metadata(city=...)`, or for the camera models before `model="iPhone 14 Pro"` (Immich may hold `iPhone14,3` instead).

```json
{
  "suggestion_type": "city",
  "country": "Spain"
}
```

`suggestion_type` is required and must be one of `country`, `state`, `city`, `camera-make`, `camera-model`, `camera-lens-model`. The other parameters narrow the answer: `country` and `state` for city suggestions, `make` for model suggestions, `model` for lens suggestions. Returns `{total, suggestions}`, a plain list of strings ready to paste into `search_metadata`.

### `search_random`

A quick sample of the library, optionally filtered. Good for "surprise me", for a feel of what a filter matches before paging through it, and for spot checks on a big library.

| Parameter | Type | Description |
|-----------|------|-------------|
| `size` | integer | How many assets. Default 10, capped at 100 |
| `city` / `country` | string | Place filters, same spellings as `search_metadata` |
| `make` / `model` | string | Camera filters |
| `is_favorite` | boolean | Only favorites |
| `ocr` | string | Only assets whose recognized text matches (needs OCR on the server) |

Returns `{total, assets}`.

### `search_statistics`

Counting without fetching. "How many photos from Spain?" costs one integer here, against pages of assets through `search_metadata`, so use this whenever only the number matters, including for every row of a breakdown.

Accepts `city`, `state`, `country`, `make`, `model`, `is_favorite`, `ocr`, `created_after` and `created_before`. Returns `{total}`.

> **Upload date, not capture date.** `created_after` / `created_before` bound the date the asset reached Immich, which is what Immich's count endpoint accepts. There is no `taken_after` here, so "how many photos did I take in 2019?" cannot be answered by this tool. Use `search_metadata(taken_after=..., taken_before=...)` and read its `total`, or `get_timeline_buckets` and sum the months.

### `search_large_assets`

What is using the most storage, biggest first. This is the one call behind most of the storage-optimizer skill.

```json
{
  "min_size_mb": 50,
  "size": 50,
  "asset_type": "VIDEO"
}
```

`min_size_mb` is a floor in megabytes (0 for no minimum), `size` is how many rows to return (default 20, capped at 200), `asset_type` is `IMAGE` or `VIDEO`. Note that `size` means "how many" and `min_size_mb` means "how big"; they are different axes. Returns `{total, assets}` with `{asset_id, filename, size_mb, date}` per row, largest first.

### `reverse_geocode`

Turns coordinates into a place name using Immich's own offline geodata, so nothing leaves your network and no API key is involved. Use it to name a marker from `get_map_markers` or a GPS cluster whose photos carry no geocoded city.

```json
{
  "lat": 41.3874,
  "lon": 2.1686
}
```

Returns `{total, places}`, a list of `{city, state, country}` candidates for those coordinates.

### `get_timeline_buckets` / `get_timeline_bucket`

The cheap way to navigate by date. `get_timeline_buckets` maps the whole library in one request: one bucket per month with its asset count. `get_timeline_bucket` then fetches the assets of a single month. Together they walk a large library without a single search.

Both accept the same filters, which is what makes the pair useful:

| Parameter | Type | Description |
|-----------|------|-------------|
| `album_id` | string | Only assets in this album (an event album gives one or two buckets, a collection spans years) |
| `person_id` | string | Only assets showing this person, so the oldest and newest buckets show when they first and last appear |
| `tag_id` | string | Only assets carrying this tag |
| `is_favorite` | boolean | Only favorites |
| `order` | string | `desc` for newest month first (the default), `asc` for oldest first |

`get_timeline_bucket` additionally requires `time_bucket`, the key exactly as the buckets call returned it (`"2026-03-01"`).

```json
{
  "person_id": "uuid-of-person"
}
```

`get_timeline_buckets` returns `{total_buckets, buckets}` with `{timeBucket, count}` rows. `get_timeline_bucket` returns `{time_bucket, total, assets}`, one row per asset with `asset_id`, `date`, `is_image`, `is_favorite`, `duration`, `city` and `country`. Immich answers that endpoint columnar (one array per field); the tool turns it back into rows so it can be read.

### `get_calendar_heatmap`

Photos per day over a range: gaps, busy periods and library health, without listing a single asset.

| Parameter | Type | Description |
|-----------|------|-------------|
| `from_date` | ISO date | Lower bound, e.g. `"2026-01-01"` |
| `to_date` | ISO date | Upper bound |
| `heatmap_type` | string | `"Taken"` (capture date, default) or `"Upload"` (when it reached Immich, Immich 3.x only) |

```json
{
  "from_date": "2019-01-01",
  "to_date": "2019-12-31"
}
```

Returns `{source, total, series}`, where `series` holds `{date, count}` for the days that had activity, oldest first. A day missing from the series had nothing. `source` says where the numbers came from: `"immich"` on 3.x, which answers natively, or `"timeline"` on 2.x, where the same shape is built from the timeline buckets (capture dates only, so `heatmap_type="Upload"` returns an explanatory error there instead).

> **Pass the narrowest range that answers the question.** The 2.x fallback costs one request per month in range, so a wide range is a slow call. An omitted bound means the server default on 3.x, but the last 365 days on 2.x, so that an open-ended call does not walk every month the library has ever held.

### `list_memories` / `create_memory` / `update_memory` / `delete_memory`

Immich's "on this day" collections: photos from the same date in past years. Use them to build a "tal día como hoy" story, album or PDF, and to save the ones the user wants to keep.

`list_memories(for_date, is_saved, size)`: `for_date` is an ISO date and returns the memories Immich would show on that day (pass today for the classic feed); `is_saved` filters to saved or unsaved only; `size` caps the count, default 50. Returns `{total, memories}`, each memory carrying `id`, `type`, `memory_at`, the `year` it looks back to, `is_saved`, `asset_count` and a trimmed `assets` list of `{asset_id, filename, date}`.

```json
{
  "memory_at": "2026-09-03",
  "year": 2019,
  "asset_ids": ["uuid-1", "uuid-2"]
}
```

`create_memory` needs both `memory_at` (the date the memory is shown on, usually today's month and day) and `year` (the past year it looks back to, required by Immich). `asset_ids` may be omitted, but an empty memory shows nothing. It returns the created memory in the same shape as a list row.

`update_memory(memory_id, is_saved, memory_at, seen_at)` saves or unsaves a memory, moves its date, or marks it seen. `delete_memory(memory_id)` returns `{"success": true, "deleted": "<memory id>"}`; the photos stay in the library, only the memory entry goes.

### `create_stack` / `list_stacks` / `get_stack` / `update_stack` / `delete_stack`

Stacking is the gentler alternative to deleting. A burst, three tries at the same shot, a photo and its edit: group them and the library shows one item, with the primary asset as the cover and every frame still there. It is reversible, which makes it the right offer when the user cannot decide which copy is best.

```json
{
  "asset_ids": ["uuid-best-shot", "uuid-2", "uuid-3"]
}
```

`create_stack` takes at least two asset ids, in order, and the **first one becomes the cover**. `list_stacks` takes an optional `primary_asset_id` to find the stack fronted by a given asset. `update_stack(stack_id, primary_asset_id)` changes the cover, and the new cover must already belong to the stack. `delete_stack(stack_id)` dissolves the grouping and returns `{"success": true, "deleted": "<stack id>"}` with a note that the assets themselves stay in the library.

The read calls return `{id, primary_asset_id, asset_count, assets}`, each asset trimmed to `{asset_id, filename}`; `list_stacks` wraps them in `{total, stacks}`.

### `list_users` / `list_partners` / `create_partner` / `update_partner` / `remove_partner`

Immich's family sharing. Each side keeps its own library, and a partner sees the other's photos next to their own. Start with `list_users` to find the id, since everything else here is addressed by user id, not by name or email.

`list_users` returns `{total, users}` with `{id, name, email}`. `list_partners` asks Immich in both directions and returns `{shared_with_me, shared_by_me}`, each entry `{id, name, email, in_timeline}`.

```json
{
  "user_id": "uuid-of-user",
  "in_timeline": true
}
```

`create_partner(user_id)` shares this account's whole library with that user. `update_partner(user_id, in_timeline)` decides whether their photos are mixed into this timeline or kept separate, and it only works on someone in `shared_with_me`: the flag controls how *their* photos appear *here*, so calling it on a `shared_by_me` partner is rejected by Immich. `remove_partner(user_id)` revokes the sharing and returns `{"success": true, "removed": "<user id>"}`; their own photos are never touched.

### `list_activities` / `create_activity` / `delete_activity`

Comments and likes on a shared album, the conversation that happens around photos the user shared with someone. Only meaningful on albums that actually have a shared link or shared users.

| Parameter | Type | Description |
|-----------|------|-------------|
| `album_id` | string | **Required.** The shared album |
| `asset_id` | string | Only activity on this one asset within the album |
| `activity_type` | string | `"comment"` or `"like"`. Omit for both |

```json
{
  "album_id": "uuid-of-album",
  "activity_type": "comment"
}
```

`list_activities` returns `{total, activities}` with `{id, type, comment, asset_id, user, created_at}` per entry. `create_activity(album_id, comment, asset_id, like)` posts one: pass `comment` for text, or `like=true` for a like (then leave `comment` empty), and `asset_id` to attach it to one photo instead of the album. It returns `{id, type}`. `delete_activity(activity_id)` removes it for everyone and returns `{"success": true, "deleted": "<activity id>"}`.

### `get_download_info` / `download_archive`

Getting the originals out, as one zip on the machine running the server. Call them in that order: originals and videos add up fast, and telling the user "this is 14 GB" before starting is the whole point of the first tool.

```json
{
  "album_id": "uuid-of-album"
}
```

Both accept `album_id` **or** `asset_ids`, not both, and `download_archive` additionally requires `output_path`. `get_download_info` returns `{total_size_mb, asset_count, archives}`, where `archives` is how many separate zips Immich would split the download into. `download_archive` streams the file to disk and returns `{path, bytes, assets}`.

An existing file is never overwritten: the call refuses and asks for another path. In the Docker image, write into the mounted `/data` volume.

### `review_assets` / `record_action` / `get_asset_notes` / `get_assets_notes` / `clear_asset_notes`

The plugin's own memory on an asset, so a second cleanup session does not redo the first one's thinking. Immich lets an app store a key with a JSON value on each asset; this plugin owns exactly one key, `immich-photo-manager`, and never reads or deletes another app's. The notes are invisible in the Immich UI and not searchable, so tags remain the visible state a user acts on and notes carry the reasoning behind it.

```json
{
  "asset_ids": ["uuid-1", "uuid-2"],
  "verdict": "duplicate_of",
  "reason": "near-identical to IMG_6367, keep that one"
}
```

`review_assets` records a verdict with its reason. `verdict` is a closed vocabulary so that sessions stay comparable: `keep`, `delete_candidate`, `duplicate_of`, `needs_check`. `record_action(asset_ids, action, detail)` records what the plugin did instead of what it decided: `action` is a short label like `added_to_album`, `date_fixed` or `rotated`, and `detail` holds the context to keep (which album, the previous value, the user's request). Each list keeps only the 10 newest entries per asset; this is a memory, not an audit log.

`get_asset_notes(asset_id)` reads one asset's `reviews` and `actions`, newest last. `get_assets_notes(asset_ids)` is the bulk read: it returns `{checked, annotated}`, one compact row per asset that already carries notes with its `last_verdict`, `last_reason` and `last_review_at`, so a 500-asset pass can skip everything an earlier session already judged. `clear_asset_notes(asset_ids)` forgets them again.

The bulk calls work asset by asset and do not stop at the first bad id: each one returns a `failed` array of `{asset_id, error}` alongside its count, and `success` is true only when that array is empty. An empty `asset_ids` is rejected rather than silently reported as zero.

`get_asset_info(asset_id, with_notes=true)` returns the same notes inline, which saves a second call when the asset is being fetched anyway.

---

## Architecture

```
Claude ←→ MCP (stdio) ←→ Python Server ←→ Immich REST API
                                              your-instance
```

- **Protocol**: stdio (standard MCP transport for Claude Code / Cowork)
- **Auth**: Immich API key passed via environment variable (never exposed to Claude)
- **Thumbnail delivery**: Base64 data URIs embedded directly in self-contained HTML galleries, required because the Cowork viewer runs in an `about:` sandbox that blocks all external network requests

For a detailed explanation of the thumbnail delivery architecture and why base64 embedding is the only viable approach in Cowork, see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Rate Limits

The MCP server does not impose its own rate limits, but Immich may:

- Search operations: Generally unlimited for self-hosted instances
- Bulk operations (add 2000 assets to album): May take 2-5 seconds
- CLIP search: Depends on ML container resources and may be slower on first query

For bulk operations, skills automatically batch requests (typically 100-2000 items per call) and report progress.

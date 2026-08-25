# MCP Tools Reference

The Immich Photo Manager MCP server exposes 53 tools that Claude can use to interact with your Immich instance. These tools are the building blocks that all skills use internally.

---

## Tool Categories

### Health & Info (3)

| Tool | Description | Returns |
|------|-------------|---------|
| `ping` | Check if the Immich server is reachable | Connection status |
| `get_server_version` | Get Immich server version | Version string |
| `get_statistics` | Get library-wide statistics | Photo count, video count, storage used |

### Assets (7)

| Tool | Description | Returns |
|------|-------------|---------|
| `get_asset_info` | Get full metadata for a specific asset | EXIF data, GPS, dates, dimensions, file info |
| `update_asset_metadata` | Update asset metadata (dates, GPS, description, favorites, rating) | Updated asset object |
| `rotate_assets` | Rotate assets by album or IDs (90°, 180°, 270°) — non-destructive | Count of rotated/failed assets |
| `revert_asset_edits` | Remove all edits (rotation, crop, mirror) from assets — revert to original | Count of reverted/failed assets |
| `get_map_markers` | Get GPS markers for all geotagged assets | Array of {lat, lng, id} for mapping |
| `upload_asset` | Upload a local file to Immich (25MB limit, extension filter, optional album) | Uploaded asset object with ID |
| `list_assets` | List assets with filters (favorites, archived, trashed, type) | Paginated asset list |

### Search (2)

| Tool | Description | Returns |
|------|-------------|---------|
| `search_metadata` | Search by EXIF metadata: location, camera, dates, type | Paginated asset list |
| `search_smart` | AI-powered visual search via CLIP embeddings | Ranked asset list by visual similarity |

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
| `page` | number | 1 |
| `size` | number | 50 (max 200) |

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

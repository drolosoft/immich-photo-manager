---
name: album-manager
description: >
  Create, curate, and publish Immich albums organized by geography, theme, or custom criteria.
  Use when the user says "create an album", "organize my photos by location",
  "make a gallery album", "curate photos from Italy", "publish album",
  "geographic albums", "album from my trip to X", "share this album",
  or any variation of creating, managing, or publishing photo albums in Immich.
  Also triggers on "what albums do I have", "list albums", "album stats",
  "show me photos from", "generate gallery for", "show me the album".
version: 1.1.0
---

# Album Manager

## ⚠️ Connection Required — ALWAYS CHECK FIRST

**Before doing ANYTHING else in this skill, call `ping` on the Immich MCP server.**

- If `ping` succeeds → proceed with the skill normally.
- If `ping` fails or the MCP tools are not available → **STOP. Do not continue.** Tell the user:

> ❌ **Immich is not connected.** This plugin needs a running Immich MCP server to work.
>
> Run **/setup-immich-photo-manager** to configure your Immich connection. You'll need:
> 1. Your Immich server URL (e.g., `http://192.168.1.100:2283`)
> 2. An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
> 3. The MCP server running (`./immich-mcp-server`)
>
> Nothing in this plugin will work until the connection is configured.

**Do NOT skip this check. Do NOT try to run any other tool first. Always ping, always block if it fails.**

Intelligent album creation and curation for Immich photo libraries. Organizes photos **geographically by default** — albums represent places, not dates.

## Core Principle

**Geography first, chronology second.** A user who visited Mexico twice gets one "Mexico" album (or sub-albums by city), not "Mexico 2018" and "Mexico 2023". Dates are metadata shown inside the album, never the organizing principle.

## Available MCP Tools

Use the Immich MCP tools for all API interactions:

- `search_metadata` — Search by city, state, country, camera make/model, date range (`taken_after`/`taken_before`), favorites, or asset type
- `search_smart` — CLIP semantic search from a natural language description (e.g. "Colosseum Rome Italy")
- `get_map_markers` — Get GPS markers (up to 500) for all geotagged assets; filter by coordinates client-side
- `create_album` — Create a new album with name and description
- `add_assets_to_album` — Add photos/videos to an album by asset IDs
- `remove_assets_from_album` — Remove assets from an album
- `list_albums` — List all albums with asset counts
- `get_album` — Get album details including all assets
- `delete_album` — Delete an album (does NOT delete the photos)
- `create_shared_link` — Create a public shared link for an album (makes it visible in Gallery)
- `get_asset_info` — Get full metadata for a specific asset (GPS, EXIF, dates)
- `get_statistics` — Get library statistics (total photos, videos, storage)
- `get_asset_thumbnail` — Get base64 thumbnail for an asset (used for gallery HTML generation)
- `create_stack` / `list_stacks` — Group near-identical shots under one cover asset instead of dropping them; the album shows the stack as a single item
- `get_download_info` — Size of the zip an album would make, before building it
- `download_archive` — Write the album's originals to a zip on the machine running the server

## Album Creation Workflow

### 1. Discover photos for a location

There is no radius/coordinate search parameter — combine these four approaches:

```
# Location text search (most reliable — uses EXIF reverse-geocoded names)
search_metadata(city="Roma")
search_metadata(country="Italy")

# CLIP semantic search (when geocoded names are missing or inconsistent)
search_smart(query="Colosseum Rome Italy")

# GPS clustering via map markers (returns up to 500 markers with lat/lon)
get_map_markers()
# Then filter the returned coordinates yourself, e.g. keep markers
# within ~0.5° of Rome (41.90, 12.49) and collect their asset IDs

# Date-based (supplement — trip windows)
search_metadata(taken_after="2023-06-01", taken_before="2023-06-15")

# Combined: location text + date window
search_metadata(city="Roma", taken_after="2023-06-01", taken_before="2023-06-15")
```

### 2. Filter and curate

From the search results, filter out:
- Screenshots (typical screen resolutions, no GPS, no lens info)
- Duplicate/near-duplicate images
- Blurry or very dark photos (if quality metadata available)
- Photos that don't match the location theme

Near-duplicates do not have to be dropped. When several shots are the same moment, `create_stack(asset_ids=[...])` groups them behind the best one: the album reads clean and nothing is thrown away. The first id passed becomes the cover.

Prefer photos that:
- Have strong composition or visual interest
- Show landmarks, landscapes, or characteristic scenes of the place
- Have good resolution and quality
- Tell the story of the place

Target: **20-50 photos per album** for optimal gallery experience. Can go up to 100 for major destinations.

### 3. Create the album

Naming convention:
```
[Country emoji] Place, Country
Examples:
🇮🇹 Cinque Terre, Italia
🇪🇬 Cairo & Luxor, Egypt
🇲🇽 Chiapas, México
🏝️ Lanzarote
🌴 La Palma
🏙️ Barcelona
```

For the description, include:
- When the photos were taken (year or date range)
- Brief context (e.g., "Summer road trip through coastal villages")
- Number of photos

### 4. Share for Gallery publication

After creating the album, create a shared link to make it visible in the Gallery frontend:

```
create_shared_link(album_id="{id}", show_metadata=true, allow_download=false)
```

### 5. Verify

Confirm the album appears correctly:
- Check album name and description
- Verify photo count matches expectations
- Confirm shared link is active

## Batch Album Creation

When creating multiple albums at once (e.g., "create albums for all my trips"):

1. First, get library statistics and `get_map_markers` data to understand what locations exist
2. Cluster the returned marker coordinates client-side to identify distinct locations
3. Present a proposed album list to the user for approval BEFORE creating
4. Create albums one by one, reporting progress
5. Summarize all created albums at the end

Always err on the side of creating MORE albums — the user can merge or delete later. It's easier to remove an unwanted album than to discover a missing one.

## Handling Missing GPS Data

Many photos (especially older ones or screenshots) lack GPS coordinates. Strategy:

1. First search by geocoded location text (`search_metadata` with city/country) for photos that have it
2. Then search by date range (`taken_after`/`taken_before`) to find photos taken during the same trip
3. Use CLIP semantic search as a fallback (`search_smart`: "beach Lanzarote", "pyramid Egypt")
4. Flag photos without GPS that were found by date/CLIP — they may or may not belong

## Album Maintenance

When asked to update or refine an existing album:

1. Get current album contents
2. Search for additional photos that might belong (expanded date range, nearby GPS, related CLIP queries)
3. Present additions and potential removals to the user
4. Apply changes after approval

---

## Gallery HTML Generation

When the user asks to **"show me photos from [album]"**, **"generate a gallery for [album]"**, **"show me [album name]"**, or any variation of viewing/displaying album contents visually, generate an interactive HTML gallery page.

### Template

Use the gallery template at `assets/viewer-template.html` (from the plugin root). This is a self-contained, single-file HTML gallery with:

- **Triple theme support** — Light, System (auto-detects), and Dark modes
- **5 view modes**: detail grid, icon grid, list, masonry, compact
- **Full-screen gallery overlay** with keyboard navigation (arrows, Escape, Space for slideshow)
- **Touch/swipe gestures** for mobile
- **Lazy loading** with intersection observers
- **Manual pagination** with "Load more" button (no infinite scroll)
- **Slideshow mode** with progress bar
- **Polaroid-style album cards** linking back to Immich
- **Responsive design** for all screen sizes

### Placeholder Reference

The template uses these placeholders that MUST be replaced:

| Placeholder | Description | Example |
|---|---|---|
| `{{ALBUM_NAME}}` | Display name of the album | `Lanzarote Verde` |
| `{{ALBUM_TOTAL}}` | Total number of photos in the album | `273` |
| `{{SEARCH_QUERY}}` | The query or description used to find photos | `&ldquo;green landscapes in Lanzarote&rdquo;` |
| `{{IMMICH_URL}}` | Immich server base URL | `https://your-immich-server.com` |
| `{{PAGE_SIZE}}` | Number of photos per lazy-load page | `20` |
| `{{PHOTO_COUNT}}` | Total photos in the gallery (limit ~50 for file size) | `50` |
| `{{PHOTO_ENTRIES}}` | The photo data entries (see format below) | See below |
| `{{ALBUMS_JSON}}` | JSON array of album links | See below |

### Photo Entry Format (base64 embedded thumbnails)

The Cowork viewer runs in an `about:` protocol sandbox that blocks ALL external network requests. Thumbnails MUST be embedded as base64 `data:` URIs.

Each entry in `{{PHOTO_ENTRIES}}` includes the full thumbnail data:

```javascript
{src:'data:image/jpeg;base64,/9j/4AAQ...',id:'<asset-id>',name:'<filename>',date:'<ISO-date>'}
```

- `src`: Base64 data URI of the thumbnail (from `get_thumbnails_batch`, size=thumbnail, ~250px, ~15-25KB each)
- `id`: The Immich asset ID (for linking to Immich web UI)
- `name`: Original filename (displayed as label)
- `date`: ISO date string from the asset metadata

**Always use `size="thumbnail"` (250px)** — never `preview` (1440px). Thumbnails average ~18KB each, so 50 photos ≈ 0.9MB HTML file.

Entries are comma-separated, one per line.

### Albums JSON Format

`{{ALBUMS_JSON}}` is injected raw into JS. It can be either a JSON **array** `[{...}]` or a single **object** `{...}` — the template handles both. Use standard JSON with quoted keys:

```javascript
[{"id":"<album-id>","name":"<Album Name>","total":<count>}]
```

Each album object needs: `id` (string), `name` (string), `total` (integer).

### Generation Workflow

1. **Get album data**: Call `get_album` to get the album ID, name, and full asset list (IDs, filenames, dates)
2. **Fetch thumbnails**: Call `get_thumbnails_batch(asset_ids=[...], size="thumbnail", limit=50)` — call in batches of 50 if needed
3. **Read the template**: Read `assets/viewer-template.html` from the plugin root
4. **Replace placeholders**: Fill in all `{{...}}` placeholders
5. **Build `{{PHOTO_ENTRIES}}`**: `{src:'data:...',id:'...',name:'...',date:'...'}` for each asset with base64 thumbnail
6. **Write the HTML**: Save to the outputs directory as `<album-name-slug>.html` (~0.9MB for 50 photos)
7. **Present to user**: Share the file link via `computer://`

**`get_thumbnails_batch` is REQUIRED.** The Cowork sandbox blocks all external requests — base64 is the only way.

### ⚠️ Placeholder Rules (IMPORTANT)

- **`{{PAGE_SIZE}}`**, **`{{PHOTO_COUNT}}`**, **`{{ALBUM_TOTAL}}`**: Must be **plain integers** (e.g. `200`, not `200+` or `"200"`). These are injected directly into JavaScript.
- **`{{ALBUM_NAME}}`**, **`{{SEARCH_QUERY}}`**, **`{{IMMICH_URL}}`**: Can be any string (they are placed inside HTML or JS string literals).
- **`{{PHOTO_ENTRIES}}`**: Must be valid JS object literals, comma-separated.
- **`{{ALBUMS_JSON}}`**: Must be comma-separated JSON objects (NOT wrapped in array brackets — the template adds `[...]`). Example: `{"id":"abc","name":"My Album","total":50}`. If no related albums, use empty string.

### CRITICAL: Related Albums = REAL Albums Only

**The `{{ALBUMS_JSON}}` placeholder must ONLY contain real, user-created albums.** Never fabricate album entries. Never create temporary albums to populate this field.

When generating a gallery for an album, find OTHER real albums that are related (e.g., same country, same trip) and list them as Related Albums. If there are no related albums, use `[]`.

### Performance Notes

- **PAGE_SIZE**: Keep at 20 for initial load. Pagination is manual ("Load more" button)
- **PHOTO_COUNT**: Limit to ~50 photos per gallery for reasonable file size (~0.9MB)
- **Thumbnails**: Embedded as base64 via `get_thumbnails_batch(size="thumbnail")` — ~18KB avg each
- For albums with 100+ photos, show first 50 and tell the user the total count

### Example: Generating a gallery

```
User: "Show me photos from Lanzarote Verde"

1. list_albums() -> find "Lanzarote Verde" album (id: abc123, 273 photos)
2. get_album(album_id="abc123") -> get full asset list with IDs, names, dates
3. Read assets/viewer-template.html
4. Replace:
   - {{ALBUM_NAME}} -> "Lanzarote Verde"
   - {{ALBUM_TOTAL}} -> 273
   - {{SEARCH_QUERY}} -> "Lanzarote Verde"
   - {{IMMICH_URL}} -> "https://your-immich-server.com"
   - {{PAGE_SIZE}} -> 20
   - {{PHOTO_COUNT}} -> 50 (first 50 of 273)
   - {{PHOTO_ENTRIES}} -> {src:'data:image/jpeg;base64,...',id:"abc",name:"IMG_001",date:"2023-06-15"},{src:'data:...',id:"def",...}
   - {{ALBUMS_JSON}} -> {"id":"abc123","name":"Lanzarote Verde","total":273}
5. Save as lanzarote-verde.html (~0.9MB)
6. Present computer:// link
```

## Reference Files

- `references/geographic-search-patterns.md` — Location names and GPS reference coordinates of common destinations, plus search strategies
- `assets/index-template.html` — Dashboard template listing all saved gallery HTML files
- `assets/viewer-template.html` — Self-contained HTML gallery template with dark/light themes, multiple view modes, slideshow, Cowork Actions Panel, and keyboard navigation

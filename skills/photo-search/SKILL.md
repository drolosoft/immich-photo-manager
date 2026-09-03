---
name: photo-search
description: >
  Search and explore an Immich photo library using natural language, GPS locations,
  dates, people, cameras, and AI-powered visual search (CLIP).
  Use when the user says "find photos of", "search my photos", "show me pictures from",
  "where are my photos of", "do I have photos of", "find all screenshots",
  "photos taken with", "photos from 2019", "photos near", "photos of [person]",
  or any variation of searching, browsing, or exploring their photo library.
version: 1.2.0
---

# Photo Search

## Connection Required: ALWAYS CHECK FIRST

**Before doing ANYTHING else in this skill, call `ping` on the Immich MCP server.**

- If `ping` succeeds -> proceed with the skill normally.
- If `ping` fails or the MCP tools are not available -> **STOP. Do not continue.** Tell the user:

> Immich is not connected. This plugin needs a running Immich MCP server to work.
>
> Run **/setup-immich-photo-manager** to configure your Immich connection. You'll need:
> 1. Your Immich server URL (e.g., `http://192.168.1.100:2283`)
> 2. An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
> 3. The MCP server configured (see **/setup-immich-photo-manager**)

**Do NOT skip this check. Do NOT try to run any other tool first. Always ping, always block if it fails.**

---

## CRITICAL RULE: NEVER CREATE TEMPORARY ALBUMS

**This is the most important rule of this skill. NEVER create albums as part of a search workflow.**

The user has a curated library of real albums. Creating temporary albums pollutes their library with junk. Instead:

- If photos belong to a real album -> use that real album directly
- If photos are NOT in any album -> show them directly using `get_thumbnails_batch`
- **NEVER call `create_album` from this skill. Not for "temp" albums, not for "search results", not for any reason.**

---

## Search Workflow (Step by Step)

### Step 1: Parse user intent

Identify what the user is looking for. Determine which search dimensions apply.

If the user is browsing rather than looking for something specific ("what's in here?", "surprise me"), start with `search_explore` for one representative photo per city and per detected concept, or `search_random` for a quick sample. Both answer in one call.

### Step 2: Search for matching photos

Use `search_metadata` and/or `search_smart` to find matching assets.

**IMPORTANT: how Immich stores place names:**
- Immich stores cities as **municipalities**, not tourist names. "Tikal" does not exist as a city; it's in the municipality of **"Flores"** (state: **"Petén"**, country: **"Guatemala"**).
- "Lanzarote" does not exist as a city; look for municipalities like "Arrecife", "Yaiza", "Teguise", "Haría", etc. (state: **"Canary Islands"**, country: **"Spain"**).
- When a place-name search returns 0 results, try broader terms: search by **state** or **country** instead of city, then filter. Or use `search_smart` with the place name as a CLIP query.
- Do not guess spellings. `search_cities` lists every city that appears in the library, and `search_suggestions(suggestion_type="city", country="Spain")` returns the exact strings `search_metadata` expects. One call is cheaper than three failed searches, and the same works for `camera-make` and `camera-model`.

Search strategy priority:
1. `search_metadata(city=...)`: fastest, most precise if the city name matches
2. `search_metadata(state=...)` or `search_metadata(country=...)`: broader, catches municipalities
3. `search_smart(query="...")`: AI/CLIP semantic search, catches things without GPS

### Step 3: Find REAL matching albums

Call `list_albums()` and **fuzzy-match** album names/descriptions against the user's query.

Examples:
- User asks "photos of Tikal" -> match album "Tikal & Petén" (and possibly "Guatemala")
- User asks "fotos de la Barceloneta" -> match album "Barcelona - Barceloneta / Playa"
- User asks "Valle del Jerte" -> match album "Valle del Jerte & Hervás"
- User asks "Lanzarote" -> match albums containing "Lanzarote" in their name

Matching rules:
- Case-insensitive substring match on album name
- Also check album descriptions
- The query terms can appear anywhere in the album name (e.g., "Tikal" matches "Tikal & Petén")
- Include albums for broader regions if relevant (e.g., for "Tikal" also include "Guatemala")

### Step 4: Collect asset metadata for the gallery

**Two paths depending on whether a real album was found:**

#### Path A: real album found (preferred)
Use `get_album(album_id)` to get the full asset list. Extract `id`, `originalFileName`, and `fileCreatedAt` from each asset.
This is the best path because the user curated these albums intentionally.

#### Path B: no matching album (orphan photos)
Use the search results directly: they already contain `id`, `originalFileName`, and `fileCreatedAt` for each asset.
**Do NOT create an album. Just show the photos.**

**Fetch thumbnails as base64** using `get_thumbnails_batch(asset_ids=[...], size="thumbnail", limit=50)`. The Cowork viewer runs in an `about:` sandbox that blocks ALL external network requests, so thumbnails MUST be embedded as base64 `data:` URIs.

### Step 5: Build and present the HTML gallery

1. Read the template: `assets/viewer-template.html` from the plugin root
2. Replace all `{{PLACEHOLDERS}}` with actual data
3. Write the HTML to the outputs directory
4. Present via `computer://` link

**For Related Albums ({{ALBUMS_JSON}}):**
- Include ONLY real albums found in Step 3
- If no real albums matched, use an empty array `[]`
- NEVER fabricate album entries

---

## Search Capabilities

| Dimension | MCP Tool / Parameter | Example |
|-----------|---------------------|---------|
| **Visual/semantic** | `search_smart(query=...)` | "sunset at the beach", "birthday cake" |
| **Location (text)** | `search_metadata(city=..., state=..., country=...)` | city="Barcelona" |
| **Date range** | `search_metadata(taken_after=..., taken_before=...)` | 2023-06-01 to 2023-06-30 |
| **Camera/device** | `search_metadata(make=..., model=...)` | make="Apple", model="iPhone 14 Pro" |
| **File type** | `search_metadata(asset_type=...)` | "IMAGE" or "VIDEO" |
| **Favorites** | `search_metadata(is_favorite=true)` | true |
| **Person** | `search_metadata(person_ids=[...])` | ids from `search_people(name=...)` or `list_people`; matches assets showing all of them |
| **Text inside the image** | `search_metadata(ocr=...)` | "boarding pass" (needs OCR enabled, check with `get_capabilities`) |
| **Tags** | `search_metadata(tag_ids=[...])` | ids from `list_tags` |
| **Inside an album** | `search_metadata(album_ids=[...])` | narrows any of the above to those albums |

The same four parameters work on `search_smart`, so a visual query can be filtered by person, tag, album or recognized text.

## Query Translation

| User says | Search strategy |
|-----------|----------------|
| "photos from my Italy trip" | `search_metadata(country="Italy")` + `list_albums()` to find Italy albums |
| "sunset photos" | `search_smart(query="sunset")` |
| "photos from last Christmas" | `search_metadata(taken_after="2025-12-20", taken_before="2025-12-31")` |
| "my best photos" | `search_metadata(is_favorite=true)` |
| "photos taken with iPhone" | `search_metadata(make="Apple")` |
| "videos from Barcelona" | `search_metadata(city="Barcelona", asset_type="VIDEO")` |
| "show me Tikal" | `search_metadata(state="Petén")` + `search_smart(query="Tikal")` + match album "Tikal & Petén" |

---

## Gallery HTML Generation

### Template

Use the canonical template at `assets/viewer-template.html`. Read the template file, replace `{{PLACEHOLDERS}}` with actual data, and write the result.

### Placeholder Rules

- **`{{PAGE_SIZE}}`**, **`{{PHOTO_COUNT}}`**, **`{{ALBUM_TOTAL}}`**: Should be plain integers (e.g. `20`). The template uses `parseInt()` with fallbacks, so non-numeric values degrade gracefully (PAGE_SIZE defaults to 6, others to 0).
- **`{{ALBUM_NAME}}`**: Can contain any characters including apostrophes (e.g. "L'Hospitalet"). Safe in HTML contexts. The JS alt-text reads from `document.title` instead of re-injecting this placeholder, so apostrophes won't break JS.
- **`{{SEARCH_QUERY}}`**, **`{{IMMICH_URL}}`**: Can be any string.
- **`{{PHOTO_ENTRIES}}`**: Must be valid JS object literals, comma-separated.
- **`{{ALBUMS_JSON}}`**: JSON album objects. The template wraps them in `[...].flat()`, so you can pass any of these formats:
  - Comma-separated objects: `{"id":"abc","name":"X","total":50},{"id":"def","name":"Y","total":30}`
  - A JSON array: `[{"id":"abc","name":"X","total":50}]`
  - Empty string (no albums): the template produces `[].flat()` → `[]` and hides the section

### Thumbnail Delivery Strategies

There are three strategies for delivering thumbnails to the gallery viewer, with different trade-offs. The strategy used depends on the user's Immich setup and the viewing context.

#### Strategy 1: Base64 Embedded (Default, Always Works)

The Cowork viewer runs in an `about:` protocol sandbox that blocks ALL external network requests (`fetch`, `<img src>`, etc.). Therefore, the **default and always-safe strategy** is to embed thumbnails as base64 `data:` URIs directly in the HTML.

Each photo entry in `{{PHOTO_ENTRIES}}` includes the full thumbnail data:

```javascript
{src:'data:image/jpeg;base64,/9j/4AAQ...',id:'<asset-id>',name:'<filename>',date:'<ISO-date>'}
```

- `src`: Base64 data URI of the thumbnail (from `get_thumbnails_batch`, size=thumbnail, ~250px, ~15-25KB each)
- `id`: The Immich asset ID (for linking to Immich web UI)
- `name`: Original filename (displayed as label)
- `date`: ISO date string from the asset metadata

**Always use `size="thumbnail"` (250px)**, never `preview` (1440px). Thumbnails average ~18KB each, so 50 photos ≈ 0.9MB HTML file.

**How to get thumbnails:** Call `get_thumbnails_batch(asset_ids=[...], size="thumbnail", limit=50)`. If more than 50 photos, call in batches of 50.

**Limitations:** HTML file size grows linearly with photo count (~18KB per photo). Not ideal for albums with hundreds of photos. Maximum practical limit is ~50 thumbnails per gallery file.

#### CORS-Enabled Direct URLs (Optional, Requires User Setup)

If the user has configured CORS headers on their Immich reverse proxy, the gallery HTML can use JavaScript `fetch()` with the `x-api-key` header to load thumbnails on demand, converting responses to blob URLs. This enables full URL-based delivery for **any** photos, not just albums.

**This requires the user to configure their reverse proxy** (Nginx, Caddy, Traefik, etc.) to return CORS headers. See the **Post-Install: CORS Configuration** section in `/setup-immich-photo-manager` for instructions.

**Advantages:** Works for any photos (albums or search results), tiny HTML file, true on-demand pagination, no shared links needed.

**Limitations:** Requires CORS configuration on the server side. Not available out of the box.

#### Strategy Decision Flow

```
Always use Base64 Embedded (Strategy 1) as the default:
  ├─ ≤50 photos → Embed all thumbnails as base64
  └─ >50 photos → Embed first 50 in batches, warn user about file size and total count
```

**Note:** CORS-enabled direct URLs (Strategy 3) are an opt-in enhancement for users who open galleries in a regular browser. They do NOT work inside the Cowork sandbox. Never mention strategy numbers or internal labels in user-facing output. Just generate the gallery silently using the correct approach.

### Template lazy loading

The first page (PAGE_SIZE photos) loads immediately. The next pages use IntersectionObserver to set `src` from `dataset.src` only when scrolled into view. Pagination is manual via "Load more" button (no infinite scroll). This works with both base64 and URL-based strategies.

### Albums JSON Format

`{{ALBUMS_JSON}}` is a JSON array of REAL albums:

```
{"id":"abc123","name":"Tikal & Petén","total":169},{"id":"xyz789","name":"Guatemala","total":392}
```

Comma-separated JSON objects, NO outer array brackets (the template adds `[...]`). If no real albums match, use empty string.

### Generation Workflow (Concrete Example)

```
User: "show me photos of Tikal"

1. ping() -> OK
2. search_metadata(state="Petén", country="Guatemala") -> found 200+ assets
3. list_albums() -> scan names -> found "Tikal & Petén" (id: d6dd63d0, 169 photos), "Guatemala" (id: 8dde4bb1, 392 photos)
4. get_album(album_id="d6dd63d0") -> get asset list with IDs, names, dates
5. get_thumbnails_batch(asset_ids=[...], size="thumbnail", limit=50) -> base64 JPEG data for first 50 photos
6. Read assets/viewer-template.html
7. Replace placeholders:
   - {{ALBUM_NAME}} -> "Tikal & Petén"
   - {{ALBUM_TOTAL}} -> 169
   - {{SEARCH_QUERY}} -> "Tikal"
   - {{IMMICH_URL}} -> "https://your-immich-server.com"
   - {{PAGE_SIZE}} -> 20
   - {{PHOTO_COUNT}} -> 50 (limited to 50 for file size)
   - {{PHOTO_ENTRIES}} -> {src:'data:image/jpeg;base64,...',id:"abc",name:"IMG_001",date:"2023-06-15"}, ...
   - {{ALBUMS_JSON}} -> {"id":"d6dd63d0","name":"Tikal & Petén","total":169},{"id":"8dde4bb1","name":"Guatemala","total":392}
8. Write tikal.html to outputs (~0.9MB with 50 base64 thumbnails, total album has 169 photos)
9. Present computer:// link
```

### When photos are NOT in any album

```
User: "show me sunset photos"

1. ping() -> OK
2. search_smart(query="sunset") -> found 35 assets (each has id, originalFileName, fileCreatedAt)
3. list_albums() -> no album name matches "sunset"
4. Read template
5. Replace placeholders:
   - {{ALBUM_NAME}} -> "Sunset Photos"
   - {{ALBUM_TOTAL}} -> 35
   - {{PHOTO_COUNT}} -> 35
   - {{PHOTO_ENTRIES}} -> entries built from get_thumbnails_batch (base64 src + id + name + date)
   - {{ALBUMS_JSON}} ->     <-- empty string, no real albums match
6. Write sunset-photos.html to outputs (~0.7MB with base64 thumbnails)
7. Present computer:// link
```

---

## Result Presentation

When showing search results:

- **Count first**: "Found 147 photos matching your search"
- **Real albums**: "These photos are in your album 'Tikal & Petén' (169 photos)"
- **Date range**: "Spanning from June 2019 to June 2023"
- **Visual preview**: Always generate the HTML gallery viewer
- **Action prompt**: Suggest next steps (see more photos, explore related albums, etc.)

## Pagination

Immich API returns paginated results. For large result sets:
- Fetch first page to get total count
- Report total to user before fetching all pages
- For browsing, show first page thumbnails and offer to load more

## Advanced Search Patterns

### Finding screenshots
No GPS data + screen-resolution dimensions + no lens/focal length EXIF.

### Finding duplicates
Same date range across import sources. Compare by exact hash, timestamp + dimensions, or CLIP similarity.

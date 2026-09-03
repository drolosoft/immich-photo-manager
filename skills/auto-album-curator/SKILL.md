---
name: auto-album-curator
description: >
  Monitor your Immich library for new photos that match existing albums and suggest additions.
  Keeps albums fresh by finding new photos that belong in existing collections based on GPS location,
  visual similarity (CLIP), and date patterns.
  Use when the user says "update my albums", "refresh albums", "new photos for albums",
  "curate albums", "auto-curate", "keep albums fresh", "album suggestions",
  "what new photos belong in my albums", "smart album update",
  or any variation of wanting to keep their albums up to date with recent imports.
version: 1.1.0
---

# Auto-Album Curator

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

Analyze new photos against existing albums and suggest additions. Uses GPS proximity, CLIP visual similarity, and temporal patterns to find photos that belong in an album but haven't been added yet.

## When to Use

- After importing new photos from a trip/event
- Periodic curation (weekly/monthly)
- When the user notices new photos aren't in the right albums
- After running a cleanup that might have removed album members

## Curation Workflow

### Step 1: Inventory Current Albums

Use the MCP tool `list_albums` to get all albums, then `get_album` for each to understand their contents:

```python
for album in albums:
    album.photo_count = len(album.assets)
    album.date_range = (min(dates), max(dates))
    album.gps_center = average(gps_coordinates)
    album.gps_radius = max_distance_from_center
    album.themes = []  # populated by CLIP analysis
```

### Step 2: Profile Each Album

For each album, build a profile:

**GPS Profile:**
- Calculate the geographic center and radius of all geotagged photos
- If radius < 50km → "location-based album" (e.g., "Barcelona")
- If radius > 500km → "trip album" or "theme album"

**Temporal Profile:**
- Date range of photos
- Is it a single event (1-3 days) or ongoing collection?
- For event albums, new photos should be within the date range
- For collection albums, any date is valid
- `get_timeline_buckets(album_id=…)` settles that question without fetching a single asset: one or two buckets means an event, buckets spread across years mean a collection

**Visual Profile:**
- Use `search_smart` (CLIP) with descriptive terms derived from album name
- Sample 5 representative photos and note their visual characteristics

### Step 3: Find Candidate Photos

For each album, search for unassigned photos that match its profile:

```python
candidates = []

# GPS-based matching (for location albums)
# There is no radius search parameter — pull the map markers and
# filter by distance client-side (up to 500 geotagged assets)
if album.gps_center:
    markers = get_map_markers()
    nearby = [m for m in markers
              if haversine(m.lat, m.lon,
                           album.gps_center.lat, album.gps_center.lng)
              <= album.gps_radius * 1.5]  # slightly wider
    candidates.extend(nearby)
    # If the album maps to a known place name, also search geocoded EXIF:
    # search_metadata(city="Barcelona")

# CLIP-based matching (for theme albums)
if album.name:
    similar = search_smart(query=album.name)
    candidates.extend(similar)

# Date-based matching (for event albums)
if album.is_event:
    in_range = search_metadata(
        taken_after=album.date_range[0],
        taken_before=album.date_range[1]
    )
    candidates.extend(in_range)

# Filter: only photos NOT already in ANY album
candidates = [c for c in candidates if c.id not in all_album_asset_ids]
```

### Step 4: Score and Rank Candidates

For each candidate, compute a relevance score:

| Signal | Weight | Description |
|---|---|---|
| GPS proximity | 0.4 | Distance from album's geographic center |
| Visual similarity | 0.3 | CLIP score against album's representative photos |
| Temporal fit | 0.2 | How well the date fits the album's range |
| Source match | 0.1 | Same camera/source as existing album photos |

Only suggest candidates with score > 0.6.

### Step 5: Present Suggestions

```
ALBUM CURATION SUGGESTIONS
═══════════════════════════════════════

📁 Barcelona (42 photos, last updated: 2024-08-15)
   3 new photos found:
   - IMG_4521.jpg (2024-12-20, GPS: 41.38°N 2.17°E, score: 0.92)
   - IMG_4523.jpg (2024-12-20, GPS: 41.39°N 2.18°E, score: 0.89)
   - DSC_0012.jpg (2025-01-05, GPS: 41.40°N 2.16°E, score: 0.78)

📁 Family Dinners (28 photos, ongoing collection)
   5 new photos found:
   - IMG_5102.jpg (2025-02-14, CLIP: "dinner table", score: 0.81)
   - IMG_5103.jpg (2025-02-14, CLIP: "family gathering", score: 0.77)
   ...

📁 Lanzarote 2024 (156 photos, event: Oct 2024)
   0 new photos — album appears complete

SUMMARY: 8 photos suggested for 2 albums
Add all? [Yes / Review one by one / Skip]
```

### Step 6: Apply (User-Approved)

Use `add_assets_to_album` MCP tool to add approved photos.

## Album Types

The curator handles different album types differently:

| Type | Detection | Candidate Strategy |
|---|---|---|
| **Location** | All photos within 50km radius | GPS proximity search |
| **Event** | Photos span 1-7 days | Strict date range matching |
| **Trip** | Photos span 1-4 weeks, multiple locations | GPS along the route |
| **Theme** | No GPS pattern, mixed dates | CLIP visual similarity only |
| **People** | Album named after a person | `search_people(name=album.name)` for the id, then `search_metadata(person_ids=["<id>"])` |

## Scheduled Mode

This skill can be configured to run periodically via the `schedule` skill:

```
"Run album curation every Sunday at 9am"
→ Scans for new photos added in the past week
→ Generates suggestions
→ Saves report for user review
```

## Important Notes

- **Never adds photos automatically** — always presents suggestions for approval
- Respects album boundaries — won't suggest adding a screenshot to a travel album
- For shared albums (published via Immich shared links), suggests additions but warns about public visibility
- CLIP search requires the Immich ML container to be running
- Large libraries (>50K) may take 2-5 minutes to analyze all albums
- The scoring weights can be adjusted by the user if suggestions aren't relevant enough

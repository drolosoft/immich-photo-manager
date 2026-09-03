# 👁️ Auto Album Curator

> **New photos keep arriving. Your albums should keep up.** The curator monitors your library and suggests additions to existing albums.

You built a "Lanzarote 2026" album last month. Since then, 15 new photos from Lanzarote were uploaded. The curator finds them and suggests adding them.

---

## Step 1: Analyze existing albums

```
list_albums()
→ 52 albums found
```

Claude picks an album to curate:

```
get_album(album_id="abc123-...")
→ "🇪🇸 Lanzarote, Jan 2026"
   186 photos, GPS center: 29.04°N, -13.50°W
   Date range: Jan 1-20, 2026
```

## Step 2: Search for new matches

Claude searches for photos that match the album's pattern but aren't in it yet:

```
search_metadata(
    taken_after="2026-01-01",
    taken_before="2026-01-21",
    size=200
)
```

Then cross-references with the album's asset list:

```
get_map_markers(file_created_after="2026-01-01", file_created_before="2026-01-21")
```

## Step 3: Score candidates

Each candidate is scored on multiple signals:

```
NEW PHOTOS FOR "🇪🇸 Lanzarote, Jan 2026"
═════════════════════════════════════════

MATCH  20260115_143022.jpg   GPS: Arrecife (3.2 km from album center)  Score: 0.94
MATCH  20260118_192544.jpg   GPS: Costa Teguise (5.1 km)               Score: 0.91
MATCH  20260120_101250.jpg   GPS: Arrecife (2.8 km)                    Score: 0.93
SKIP   Screenshot_20260115.jpg  No GPS, no camera info                  Score: 0.12

Add 3 matching photos to the album? [Yes / Select / No]
```

| Signal | Weight |
|--------|:------:|
| GPS proximity to album center | 0.4 |
| Date within album range | 0.3 |
| Same camera as album photos | 0.2 |
| CLIP visual similarity | 0.1 |

## Step 4: Add to album

```
add_assets_to_album(
    album_id="abc123-...",
    asset_ids=["new1-...", "new2-...", "new3-..."]
)
→ 3 assets added
```

---

## MCP tools used

| Tool | Purpose | Calls |
|------|---------|:-----:|
| `list_albums` | Find existing albums | 1 |
| `get_album` | Get album details + asset list | 1 per album |
| `search_metadata` | Find new photos in date range | 1 |
| `get_map_markers` | Check GPS proximity | 1 |
| `add_assets_to_album` | Add matched photos | 1 per album |

## Album types and how they match

| Type | Primary signal | Example |
|------|---------------|---------|
| **Location** | GPS within 50km radius | "Lanzarote 2026" |
| **Event** | Date range (1-4 days) | "Wedding Aug 2025" |
| **Trip** | GPS along route + date range | "Road Trip Spain" |
| **Theme** | CLIP visual similarity | "Food & Restaurants" |

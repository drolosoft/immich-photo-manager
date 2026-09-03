# 🌍 Geographic Album Creation

> **"Create albums for all my trips"**: one sentence, dozens of albums.

The plugin scans every GPS coordinate in your library, clusters them into distinct locations, and creates one album per destination. No scripts, no manual sorting.

---

## Step 1: Discover all locations

```
get_map_markers()
→ 28,616 GPS markers across the library
```

Claude clusters these into distinct locations by proximity: photos within ~50km of each other belong to the same place.

## Step 2: Identify trip clusters

Claude groups the markers by location and date range:

```
TRIP CLUSTERS FOUND
═══════════════════

🇪🇸 Sevilla, Spain         - Jan 2, 2026 (14 photos)
🇪🇸 Lanzarote, Spain       - Jan 2-20, 2026 (186 photos)
🇪🇸 Torrijos, Spain        - Jan 2, 2026 (8 photos)
🇫🇷 Paris, France           - Mar 15-18, 2025 (243 photos)
🇮🇹 Roma, Italy             - Jun 10-14, 2024 (312 photos)
   ... and 47 more locations

Create albums for all? [Yes / Select / No]
```

## Step 3: Create albums

User approves. For each cluster:

```
search_metadata(city="Sevilla", taken_after="2026-01-02", taken_before="2026-01-03")
→ 14 assets found

create_album(
    name="🇪🇸 Sevilla, Jan 2026",
    description="14 photos from Sevilla, Andalusia",
    asset_ids=["ed0afd9a-...", "edbcf3dd-...", ...]
)
→ Album created
```

Repeat for each location. Claude names each album with the country flag, city, and date range.

## Step 4: Verify

```
list_albums()
→ 52 new albums created
```

Each album has a name, description, and all matching photos, organized by geography and time.

---

## MCP tools used

| Tool | Purpose | Calls |
|------|---------|:-----:|
| `get_map_markers` | Get all GPS coordinates | 1 |
| `search_metadata` | Find photos per location/date | 1 per cluster |
| `create_album` | Create each album with photos | 1 per cluster |
| `list_albums` | Verify results | 1 |

## What this does

- **GPS + CLIP + temporal matching**: photos without GPS can be included via visual similarity to geotagged neighbors
- **Smart naming**: country flags, city names, date ranges
- **Idempotent**: won't create duplicates if you run it again
- **One sentence**: you say "create albums for all my trips" and it handles the rest

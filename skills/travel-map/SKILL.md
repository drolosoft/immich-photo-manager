---
name: travel-map
description: >
  Generate an interactive map showing every location where photos were taken,
  clustered by city/region with photo counts, date ranges, and album links.
  Outputs a standalone HTML file with Leaflet.js that can be hosted or viewed locally.
  Use when the user says "travel map", "show me everywhere I've been", "photo map",
  "map my photos", "where have I traveled", "GPS map", "location map",
  "map of my trips", "generate a map", "interactive map",
  or any variation of wanting to see their photos plotted on a map.
version: 1.1.0
---

# Travel Map

## ⚠️ Connection Required: ALWAYS CHECK FIRST

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

Generate an interactive HTML map showing all locations where photos were taken. Clusters photos by geographic proximity, shows photo counts and date ranges per location, and optionally links to Immich albums.

## When to Use

- Visualize all travel destinations at a glance
- Discover forgotten trips (photos with GPS you didn't remember)
- Plan which geographic albums to create
- Share a "places I've been" page

## Map Generation Workflow

### Step 1: Extract GPS Data

Get all geotagged photos:

```sql
SELECT
  "id",
  ("exifInfo"->>'latitude')::float as lat,
  ("exifInfo"->>'longitude')::float as lng,
  "localDateTime",
  "originalPath",
  ("exifInfo"->>'city') as city,
  ("exifInfo"->>'state') as state,
  ("exifInfo"->>'country') as country
FROM asset
WHERE "deletedAt" IS NULL
  AND "exifInfo"->>'latitude' IS NOT NULL
  AND ("exifInfo"->>'latitude')::float != 0
ORDER BY "localDateTime";
```

Or use the MCP tool `get_map_markers` for a lighter dataset.

### Step 2: Cluster by Location

Group nearby photos into location clusters:

```python
from collections import defaultdict
import math

def haversine(lat1, lng1, lat2, lng2):
    """Distance in km between two GPS points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def cluster_locations(photos, radius_km=15):
    """Simple greedy clustering by distance."""
    clusters = []
    for photo in photos:
        placed = False
        for cluster in clusters:
            if haversine(photo.lat, photo.lng, cluster.center_lat, cluster.center_lng) < radius_km:
                cluster.add(photo)
                placed = True
                break
        if not placed:
            clusters.append(Cluster(photo))
    return clusters
```

Alternatively, use the reverse-geocoded city/country from EXIF. `search_cities` lists every city that appears in the library with its country and one representative asset, and `search_statistics(city=...)` gives the photo count for each one, so the place list needs no database access. The query below is the optional fallback when the first and last visit dates and the cluster centre are wanted in one pass; the plugin never provides database access, so it only applies to a user who already has `psql` on their own Immich.

```sql
SELECT
  "exifInfo"->>'country' as country,
  "exifInfo"->>'city' as city,
  count(*) as photos,
  min("localDateTime") as first_visit,
  max("localDateTime") as last_visit,
  avg(("exifInfo"->>'latitude')::float) as center_lat,
  avg(("exifInfo"->>'longitude')::float) as center_lng
FROM asset
WHERE "deletedAt" IS NULL
  AND "exifInfo"->>'latitude' IS NOT NULL
  AND "exifInfo"->>'country' IS NOT NULL
GROUP BY country, city
ORDER BY photos DESC;
```

### Step 3: Enrich Clusters

For each cluster:
- **Name**: Use the most common city name from EXIF. For a cluster built from raw coordinates, where no photo carries a geocoded name, call `reverse_geocode(lat, lon)` on the cluster centre: it resolves the place from Immich's own offline geodata, so no external service is contacted and no API key is needed
- **Photo count**: Total photos in the cluster
- **Date range**: First to last visit
- **Visit count**: Number of distinct visit periods (>30 days apart = separate visit)
- **Representative photo**: The photo closest to the cluster center (for thumbnail)
- **Album link**: If an Immich album exists for this location, link to it

### Step 4: Generate Interactive HTML Map

Write the HTML file below. Each library is pinned to one version and carries its `integrity` hash,
so the browser refuses a file that differs from the one these hashes were taken from. Keep the hashes
as they are; a new library version needs new hashes.

```html
<!DOCTYPE html>
<html>
<head>
  <title>My Travel Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H" crossorigin="anonymous" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"
    integrity="sha384-pmjIAcz2bAn0xukfxADbZIb3t8oRT9Sv0rvO+BR5Csr6Dhqq+nZs59P0pPKQJkEV" crossorigin="anonymous" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"
    integrity="sha384-wgw+aLYNQ7dlhK47ZPK7FRACiq7ROZwgFNg0m04avm4CaXS+Z9Y7nMu8yNjBKYC+" crossorigin="anonymous" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH" crossorigin="anonymous"></script>
  <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"
    integrity="sha384-eXVCORTRlv4FUUgS/xmOyr66XBVraen8ATNLMESp92FKXLAMiKkerixTiBvXriZr" crossorigin="anonymous"></script>
</head>
<body>
  <div id="map" style="height: 100vh; width: 100%"></div>
  <script>
    const locations = [/* cluster data injected here */];
    const map = L.map('map').setView([30, 0], 3);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    const markers = L.markerClusterGroup();
    locations.forEach(loc => {
      const marker = L.marker([loc.lat, loc.lng])
        .bindPopup(`
          <strong>${loc.name}</strong><br>
          ${loc.photos} photos<br>
          ${loc.first_visit} &mdash; ${loc.last_visit}<br>
          ${loc.visits} visit(s)
        `);
      markers.addLayer(marker);
    });
    map.addLayer(markers);
  </script>
</body>
</html>
```

### Step 5: Serve the map over localhost

Do not tell the user to open the file directly. OpenStreetMap answers a page opened from disk
(`file://`) with "Access blocked" tiles, because such a page sends no referrer and looks like an
app using the tile servers without identifying itself. Served from a local address the same page
works. Write the file into its own folder and start a small server there:

```bash
cd /path/to/map-folder && python3 -m http.server 9876
```

Then open `http://127.0.0.1:9876/travel-map.html` and tell the user the server runs until they close
that terminal. The plugin ships the same two lines as `assets/serve.sh`.

### Step 6: Add Optional Features

**Heatmap layer:**
```html
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"
  integrity="sha384-mFKkGiGvT5vo1fEyGCD3hshDdKmW3wzXW/x+fWriYJArD0R3gawT6lMvLboM22c0" crossorigin="anonymous"></script>
<script>
  const heatData = locations.map(l => [l.lat, l.lng, l.photos]);
  L.heatLayer(heatData, {radius: 25}).addTo(map);
</script>
```

**Timeline slider:**
Filter markers by year range using a slider control.

**Country statistics panel:**
Side panel showing countries visited, photos per country, total distance traveled.

**Search:**
Search bar to find a specific location on the map.

## Output Options

| Format | Description |
|---|---|
| **Standalone HTML** | One file, served from localhost (Step 5) or any web server |
| **Hosted page** | Deploy to your own domain or static hosting |
| **Markdown report** | Text summary with country list, no map |
| **JSON export** | Raw cluster data for custom visualization |

## Map Styles

- **Cluster map**: markers clustered by proximity, expand on zoom (default)
- **Heatmap**: density visualization, good for overview
- **Pin map**: individual pins for every location (best for <100 clusters)
- **Country choropleth**: countries colored by photo count

## Important Notes

- **Read-only**: this skill never modifies assets
- Requires photos to have GPS data (check with library-health-report first)
- Leaflet, MarkerCluster and leaflet.heat come from `unpkg.com`, pinned by version and `integrity` hash, and the tiles from `tile.openstreetmap.org`, so the page needs internet access and those two servers see the viewer's address and the areas shown
- For very large libraries (>100K geotagged photos), use the EXIF city/country grouping instead of GPS clustering to keep the HTML file manageable
- OpenStreetMap tiles are free but have usage limits. For high-traffic hosted maps, consider a tile provider
- Privacy: the map reveals where the user lives, works, and travels, so remind them before sharing publicly
- Photos without GPS are excluded (noted in the report as "X photos not mapped")

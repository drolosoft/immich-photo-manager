# Geographic Search Patterns

Reference data for searching photos by location. There is no radius/coordinate search parameter — location discovery combines four tools:

1. **`search_metadata(city=..., state=..., country=...)`** — text match against EXIF reverse-geocoded names. Most reliable when geocoding exists. Names are case-sensitive (e.g. `city="Barcelona"`).
2. **`search_smart(query=...)`** — CLIP semantic queries for places ("Colosseum Rome", "volcanic landscape Lanzarote"). Best fallback when GPS/geocoding is missing.
3. **`get_map_markers()`** — returns up to 500 GPS markers (asset ID, lat, lon). Filter the coordinates client-side against the reference table below to cluster photos by place.
4. **`taken_after` / `taken_before`** — trip date windows to supplement any of the above.

## Search Strategy by Location Type

### Countries with multiple visits
Search each known city/region separately, then merge results. Example for Mexico:
- `search_metadata(city="Tuxtla Gutiérrez")` and nearby Chiapas town names
- `search_metadata(city="Oaxaca")` / `search_metadata(state="Oaxaca")`
- `search_metadata(city="Ciudad de México")`
- Cross-check with `get_map_markers()` filtered near each center (coords below)
- Merge unique results → one "México" album or separate city albums

### City visits
Start with `search_metadata(city=...)`. If geocoding used a different name (local vs. English spelling), try variants, then fall back to `search_smart` with landmark queries. For marker filtering, keep points within roughly ±0.1° (~10km) of the city center.

### Island/regional visits
`search_metadata(state=...)` or the island name as city often works. For marker filtering, use a wider window: ±0.2–0.5° (~20–50km) around the center.

### Road trips / multi-stop
Search each stop separately (city names + date window), then combine into a thematic album. `get_map_markers(file_created_after=..., file_created_before=...)` scoped to the trip dates gives the full GPS trail to cluster.

## Common Destination Reference (expand as needed)

Use the names in `search_metadata` calls; use the coordinates to filter `get_map_markers()` output client-side (a marker within the suggested window belongs to that place).

| Location | Latitude | Longitude | Marker Filter Window |
|----------|----------|-----------|---------------------|
| Roma, Italia | 41.9028 | 12.4964 | ±0.15° (~15km) |
| Cinque Terre, Italia | 44.1461 | 9.6563 | ±0.10° (~10km) |
| Venezia, Italia | 45.4408 | 12.3155 | ±0.10° (~10km) |
| Trieste, Italia | 45.6495 | 13.7768 | ±0.10° (~10km) |
| Como, Italia | 45.8080 | 9.0852 | ±0.15° (~15km) |
| Cairo, Egypt | 30.0444 | 31.2357 | ±0.30° (~30km) |
| Luxor, Egypt | 25.6872 | 32.6396 | ±0.20° (~20km) |
| Ciudad de México | 19.4326 | -99.1332 | ±0.30° (~30km) |
| Oaxaca, México | 17.0732 | -96.7266 | ±0.50° (~50km) |
| Tuxtla Gutiérrez, México | 16.7528 | -93.1152 | ±1.00° (~100km) |
| Guatemala / Flores | 16.9304 | -89.8923 | ±0.50° (~50km) |
| Berlín, Germany | 52.5200 | 13.4050 | ±0.20° (~20km) |
| Londres, UK | 51.5074 | -0.1278 | ±0.20° (~20km) |
| Edimburgo, UK | 55.9533 | -3.1883 | ±0.15° (~15km) |
| Ámsterdam, Netherlands | 52.3676 | 4.9041 | ±0.15° (~15km) |
| Varsovia, Poland | 52.2297 | 21.0122 | ±0.15° (~15km) |
| Bogotá, Colombia | 4.7110 | -74.0721 | ±0.20° (~20km) |
| Santo Domingo, Dom. Rep. | 18.4861 | -69.9312 | ±0.30° (~30km) |
| Mauritius | -20.3484 | 57.5522 | ±0.40° (~40km) |
| Kärnten, Austria | 46.7222 | 13.8553 | ±0.40° (~40km) |
| Istria, Croatia | 45.1300 | 13.9000 | ±0.40° (~40km) |
| Barcelona, España | 41.3874 | 2.1686 | ±0.15° (~15km) |
| Lanzarote, España | 29.0469 | -13.5899 | ±0.25° (~25km) |
| La Palma, España | 28.6835 | -17.7642 | ±0.20° (~20km) |
| Plasencia, España | 40.0304 | -6.0907 | ±0.15° (~15km) |
| Sevilla, España | 37.3891 | -5.9845 | ±0.15° (~15km) |
| Madrid, España | 40.4168 | -3.7038 | ±0.20° (~20km) |
| Begur, España | 41.9553 | 3.2073 | ±0.10° (~10km) |
| La Vera, España | 40.1167 | -5.4500 | ±0.20° (~20km) |
| Mérida, España | 38.9160 | -6.3440 | ±0.10° (~10km) |
| Fuerteventura, España | 28.3587 | -14.0537 | ±0.30° (~30km) |

Note: 1° of latitude ≈ 111km everywhere; 1° of longitude shrinks with latitude (≈ 111km × cos(lat)). The windows above are intentionally coarse — a simple box filter is enough to cluster trip photos.

## CLIP Search Queries by Destination

When GPS and geocoded names are unavailable, use `search_smart` with these semantic queries:

| Destination | CLIP Queries |
|-------------|-------------|
| Lanzarote | "volcanic landscape", "black sand beach", "white village Canary Islands" |
| Cinque Terre | "colorful houses cliff ocean Italy", "Riomaggiore", "Italian riviera" |
| Egypt | "pyramid", "sphinx", "Nile river", "Luxor temple", "hieroglyphics" |
| Mexico (Chiapas) | "jungle waterfall Mexico", "Mayan ruins", "canyon Chiapas" |
| La Palma | "banana plantation Canary Islands", "observatory mountain", "laurel forest" |

## Album Splitting Guidelines

When to create sub-albums vs one album:
- **One album**: Short trip (1-7 days), single city/island, < 80 photos
- **Multiple albums**: Multi-city trip, > 80 photos per location, distinctly different areas
- **Example**: "Italia" could be one album OR separate "Roma", "Cinque Terre", "Venezia" — depends on photo count per location

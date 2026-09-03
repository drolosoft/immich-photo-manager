# 🧠 Natural Language Search

> **"Find my sunset photos from Italy"**: CLIP-powered visual search through conversation.

Immich has CLIP built in. The plugin lets you search with natural language and combine it with metadata filters (dates, locations, cameras) in a single request.

---

## Example 1: Simple visual search

You say: *"Find photos of sunset at the beach"*

```
search_smart(query="sunset at the beach", size=20)
→ 23 results ranked by visual similarity
```

Claude shows the results with thumbnails:

```
get_thumbnails_batch(asset_ids=["a1b2c3-...", "d4e5f6-...", ...], size="thumbnail")
```

An interactive HTML gallery opens with the results. You can select photos and take actions.

## Example 2: Visual + location filter

You say: *"Birthday cakes from 2024"*

```
search_smart(
    query="birthday cake",
    taken_after="2024-01-01",
    taken_before="2024-12-31",
    size=20
)
→ 8 results
```

CLIP finds visually similar photos, the date filter narrows it down.

## Example 3: Visual + geographic filter

You say: *"Photos of food in Barcelona"*

```
search_smart(
    query="food restaurant meal",
    city="Barcelona",
    size=30
)
→ 15 results, all food photos geotagged in Barcelona
```

## Example 4: Metadata-only search

You say: *"All photos taken with my iPhone in Spain"*

```
search_metadata(
    make="Apple",
    country="Spain",
    size=200
)
→ 1,247 results
```

No CLIP needed, pure EXIF filtering.

---

## MCP tools used

| Tool | Purpose |
|------|---------|
| `search_smart` | CLIP visual search with optional filters |
| `search_metadata` | EXIF-based search (camera, location, dates) |
| `get_thumbnails_batch` | Generate visual results |

## Good vs. less effective queries

| ✅ Works well | ❌ Less effective |
|--------------|-----------------|
| "sunset at the beach" | "photo from last Tuesday" |
| "birthday cake with candles" | "IMG_2847.jpg" |
| "mountains with snow" | "the photo John sent me" |
| "group photo at dinner" | Very specific proper nouns |

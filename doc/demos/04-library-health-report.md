# 🏥 Library Health Report

> **"How healthy is my photo library?"**: one command, full diagnostic.

A full assessment of your Immich library: asset inventory, metadata quality, storage breakdown, and recommendations you can act on.

---

## Step 1: Gather statistics

```
get_statistics()
→ { photos: 42,511, videos: 4,869, storage: "285.3 GB" }

get_map_markers()
→ 28,616 markers (67.3% of photos have GPS)
```

## Step 2: Analyze metadata quality

```
search_metadata(size=200, page=1)
search_metadata(size=200, page=2)
... (sampling across the library)
```

Claude samples photos across different time periods and checks EXIF completeness.

## Step 3: The report

```
LIBRARY HEALTH REPORT
═════════════════════

📊 INVENTORY
   Photos:     42,511
   Videos:      4,869
   Total:      47,380
   Storage:    285.3 GB

🗺️ GPS COVERAGE
   With GPS:    28,616 (67.3%)
   Without:     13,895 (32.7%)
   → Run metadata-fixer to infer GPS from neighbors

⏰ TIMESTAMP QUALITY
   Real EXIF dates:    38,204 (89.9%)
   Midnight (00:00):    2,847 (6.7%)  ⚠️ likely folder imports
   Noon (12:00):        1,460 (3.4%)  ⚠️ likely folder imports
   → Run metadata-fixer to interpolate from neighbors

📷 CAMERA BREAKDOWN
   Samsung Galaxy S24:  12,340 (29.0%)
   Apple iPhone:         8,921 (21.0%)
   Screenshots:          3,456 (8.1%)
   No camera info:      17,794 (41.9%)

💾 STORAGE BY TYPE
   JPEG:    198.2 GB (69.5%)
   HEIC:     52.1 GB (18.3%)
   Video:    28.7 GB (10.1%)
   PNG:       6.3 GB (2.2%)

✅ RECOMMENDATIONS
   1. Fix 4,307 suspicious timestamps with metadata-fixer
   2. Infer GPS for ~9,200 photos that have neighbors with coordinates
   3. Review 3,456 screenshots, consider moving to a separate album
   4. Check 17,794 photos with no camera info (possible downloads/imports)
```

---

## MCP tools used

| Tool | Purpose | Calls |
|------|---------|:-----:|
| `get_statistics` | Total counts and storage | 1 |
| `get_map_markers` | GPS coverage | 1 |
| `search_metadata` | Sample photos for EXIF analysis | ~5-10 |
| `get_asset_info` | Deep inspection of sampled assets | ~20-50 |

## What you get

- **Numbers, not guesses**: actual counts for every metric
- **Concrete next steps**: each finding links to a skill that can fix it
- **Repeatable**: run it monthly to track improvement

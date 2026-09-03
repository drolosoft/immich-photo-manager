---
name: metadata-fixer
description: >
  Scan for and fix broken or missing photo metadata: dates, GPS coordinates, timezone offsets,
  and camera info. Detects suspicious patterns (midnight/noon timestamps, missing GPS on geotagged trips)
  and proposes corrections using folder structure, neighboring photos, and EXIF inference.
  Use when the user says "fix metadata", "fix dates", "wrong dates", "missing GPS",
  "metadata repair", "exif fix", "photos have wrong time", "noon dates", "midnight timestamps",
  "fix my photo dates", "metadata fixer", or any variation of wanting to repair photo metadata.
version: 1.1.0
---

# Metadata Fixer

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

Scan an Immich library for broken, missing, or suspicious metadata and propose corrections. Focuses on the most impactful fields: dates, GPS coordinates, and timezone offsets.

## Why This Matters

Common metadata problems in imported photo libraries:

- **Noon/midnight timestamps**: dates recovered from folder paths lose the time component, defaulting to 00:00 or 12:00
- **Missing GPS**: some export tools strip GPS data, or photos taken in airplane mode have none
- **Wrong timezones**: photos taken abroad may have the wrong timezone offset, putting them hours off
- **No EXIF dates**: screenshots, downloaded images, and some messaging apps strip date metadata entirely

## Analysis Workflow

### Step 1: Scan for Issues

Over the API: walk the library with `get_timeline_buckets()`, then `get_timeline_bucket(time_bucket)` for the months to check. Each row carries the asset date, city and country, which is enough to spot exact-noon and exact-midnight timestamps and the days where some photos have a place and others do not. `get_asset_info` fills in the rest for a candidate.

The queries below are an optional fallback that runs the same scan in one pass. The plugin never provides database access, so they only apply to a user who already has `psql` on their own Immich:

```sql
-- Suspicious timestamps (exactly midnight or noon)
SELECT
  "id", "originalPath", "localDateTime",
  "exifInfo"->>'dateTimeOriginal' as exif_date,
  CASE
    WHEN extract(hour from "localDateTime") = 0
      AND extract(minute from "localDateTime") = 0 THEN 'MIDNIGHT'
    WHEN extract(hour from "localDateTime") = 12
      AND extract(minute from "localDateTime") = 0
      AND extract(second from "localDateTime") = 0 THEN 'NOON'
  END as issue_type
FROM asset
WHERE "deletedAt" IS NULL
  AND type = 'IMAGE'
  AND (
    (extract(hour from "localDateTime") = 0 AND extract(minute from "localDateTime") = 0)
    OR
    (extract(hour from "localDateTime") = 12 AND extract(minute from "localDateTime") = 0
     AND extract(second from "localDateTime") = 0)
  );

-- Missing GPS where neighbors have GPS (same day, same source)
WITH daily_gps AS (
  SELECT
    date_trunc('day', "localDateTime") as day,
    count(*) as total,
    count(*) FILTER (WHERE "exifInfo"->>'latitude' IS NOT NULL) as with_gps
  FROM asset WHERE "deletedAt" IS NULL AND type = 'IMAGE'
  GROUP BY 1
)
SELECT day, total, with_gps,
  total - with_gps as missing_gps,
  round(100.0 * with_gps / total, 1) as gps_pct
FROM daily_gps
WHERE with_gps > 0 AND with_gps < total
ORDER BY missing_gps DESC
LIMIT 20;

-- Missing EXIF date entirely
SELECT count(*) as no_exif_date
FROM asset
WHERE "deletedAt" IS NULL
  AND "exifInfo"->>'dateTimeOriginal' IS NULL;
```

### Step 2: Classify Issues

| Issue | Severity | Fix Strategy |
|---|---|---|
| Noon timestamps | Medium | Infer from folder path or neighboring photos |
| Midnight timestamps | Medium | Same as noon |
| Missing GPS | Low | Copy from nearest photo (same day, same camera) |
| Wrong timezone | High | Detect from GPS location → timezone lookup |
| No EXIF date at all | Low | Use file creation date or folder path |

### Step 3: Propose Fixes

**NEVER auto-fix.** Present findings and proposed corrections:

```
METADATA ISSUES FOUND
═══════════════════════════════

SUSPICIOUS TIMESTAMPS: 1,204 photos
  Noon (12:00:00):      892 photos (likely path-recovered dates)
  Midnight (00:00:00):  312 photos

  FIX STRATEGY: For each photo, check neighboring photos (±2 hours by
  file order within same folder) and interpolate the time. If no neighbors,
  keep the date but mark as "time unknown".

  Example:
    IMG_2847.jpg  2019-07-14 12:00:00 → 2019-07-14 15:23:41 (interpolated)
    IMG_2848.jpg  2019-07-14 12:00:00 → 2019-07-14 15:25:12 (interpolated)
    IMG_2849.jpg  2019-07-14 15:27:33 (has real EXIF, used as anchor)

MISSING GPS: 4,230 photos (on days where other photos have GPS)
  Fixable by neighbor inference: ~2,800 (66%)

  FIX STRATEGY: Copy GPS from nearest photo by timestamp on the same day,
  same camera/source. Only applies when gap < 2 hours.

Proceed with fixes? [Timestamps / GPS / Both / None]
```

### Step 4: Apply Fixes (User-Approved)

Use the `update_asset_metadata` MCP tool to apply corrections:

```python
# Update timestamps
update_asset_metadata(
    asset_id="uuid",
    date_time_original="2019-07-14T15:23:41.000Z"
)

# Update GPS coordinates
update_asset_metadata(
    asset_id="uuid",
    latitude=41.3874,
    longitude=2.1686
)
```

When a fix applies the same value to many photos (one day's GPS, one roll's date), use `update_assets_metadata(asset_ids=[...], latitude=..., longitude=...)` instead of looping: same fields, one call, and only the fields you pass are touched.

```python
# One day's photos, all missing GPS, all from the same place
update_assets_metadata(
    asset_ids=["uuid-1", "uuid-2", "uuid-3"],
    latitude=41.3874,
    longitude=2.1686
)
```

Keep `update_asset_metadata` (singular) for the fixes that differ per photo, such as an interpolated timestamp.

> **Known limitation:** Immich writes a `.xmp` sidecar when updating EXIF. If photos are in an external library with special characters (emojis) in the path, exiftool may fail silently. Photos uploaded directly through Immich work correctly.

Log every change for audit:

```python
fix_log = {
    "asset_id": "uuid",
    "field": "dateTimeOriginal",
    "old_value": "2019-07-14T12:00:00.000Z",
    "new_value": "2019-07-14T15:23:41.000Z",
    "strategy": "neighbor_interpolation",
    "confidence": 0.85,
    "anchor_asset": "uuid-of-neighbor"
}
```

### Step 5: Verify

After applying fixes, re-run the scan to confirm issue counts dropped.

## Fix Strategies Detail

### Neighbor Interpolation (for timestamps)
1. Sort photos in the same folder by filename (natural order)
2. Find the nearest photo with a real EXIF timestamp
3. Interpolate based on position in sequence
4. Assign confidence score based on distance from anchor

### GPS Inference (for missing coordinates)
1. Find photos from the same day, same camera, with GPS
2. If gap < 2 hours, copy the GPS coordinates
3. If gap > 2 hours, don't infer (user may have traveled)
4. Special case: photos within a burst (< 5 seconds apart) always share GPS

### Timezone Correction
1. If photo has GPS, look up timezone for those coordinates
2. Compare with the timezone offset in EXIF
3. If they differ, propose correction
4. Common case: photos taken on vacation with phone still on home timezone

## Important Notes

- **All fixes require explicit user approval**: never auto-modify metadata
- Changes are applied via the Immich API, which updates both the database and EXIF sidecar
- Always save a fix log (JSON) before applying any changes
- Confidence scores help users decide which fixes to trust
- For photos with NO useful context (no neighbors, no folder path, no GPS), recommend leaving them as-is rather than guessing
- Test with a small batch (10 photos) before applying to the full set

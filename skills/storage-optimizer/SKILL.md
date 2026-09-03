---
name: storage-optimizer
description: >
  Analyze disk usage in an Immich photo library and identify opportunities to reclaim storage —
  redundant RAW+JPEG pairs, oversized videos, bloated sidecar files, and format inefficiencies.
  Use when the user says "storage", "disk space", "what's eating my disk", "free up space",
  "storage report", "disk usage", "large files", "optimize storage", "space analysis",
  "how much space", "biggest files", or any variation of wanting to understand or reduce storage usage.
version: 1.1.0
---

# Storage Optimizer

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

Analyze storage usage in an Immich photo library, identify the biggest consumers, and recommend strategies to reclaim space without losing important content.

## When to Use

- Disk space running low on the Immich server
- After bulk imports to assess storage impact
- Planning storage capacity (how long until disk is full?)
- Deciding whether to keep RAW files, original videos, etc.

## Analysis Workflow

### Step 1: Storage Overview

`get_statistics` gives the totals (photos, videos, storage used) in one call, with no database access. The query below is the optional fallback for the per-type averages and maximums Immich's API does not report; the plugin never provides database access, so it only applies to a user who already has `psql` on their own Immich.

```sql
-- Total storage by asset type
SELECT type,
  count(*) as files,
  pg_size_pretty(sum(("exifInfo"->>'fileSizeInByte')::bigint)) as total_size,
  pg_size_pretty(avg(("exifInfo"->>'fileSizeInByte')::bigint)) as avg_size,
  pg_size_pretty(max(("exifInfo"->>'fileSizeInByte')::bigint)) as max_size
FROM asset WHERE "deletedAt" IS NULL
GROUP BY type;

-- Trash storage (reclaimable immediately)
SELECT
  count(*) as trashed_files,
  pg_size_pretty(sum(("exifInfo"->>'fileSizeInByte')::bigint)) as trash_size
FROM asset WHERE "deletedAt" IS NOT NULL;
```

### Step 2: Format Breakdown

```sql
-- File formats by count and size
SELECT
  upper(split_part("originalPath", '.', -1)) as format,
  count(*) as files,
  pg_size_pretty(sum(("exifInfo"->>'fileSizeInByte')::bigint)) as total_size,
  pg_size_pretty(avg(("exifInfo"->>'fileSizeInByte')::bigint)) as avg_size,
  round(100.0 * sum(("exifInfo"->>'fileSizeInByte')::bigint) /
    (SELECT sum(("exifInfo"->>'fileSizeInByte')::bigint) FROM asset WHERE "deletedAt" IS NULL), 1) as pct_of_total
FROM asset WHERE "deletedAt" IS NULL
GROUP BY format ORDER BY sum(("exifInfo"->>'fileSizeInByte')::bigint) DESC;
```

### Step 3: Identify Top Storage Consumers

**Large files (>50MB):**

The MCP tool `search_large_assets(min_size_mb=50, size=50)` answers this without database access. It returns the biggest files largest-first with filename, size in MB and date. Use the SQL below only when you need columns it does not return, such as the camera make or the original path.

```sql
SELECT "id", "originalPath", type,
  pg_size_pretty(("exifInfo"->>'fileSizeInByte')::bigint) as size,
  "exifInfo"->>'make' as camera,
  "localDateTime"
FROM asset
WHERE "deletedAt" IS NULL
  AND ("exifInfo"->>'fileSizeInByte')::bigint > 52428800  -- 50MB
ORDER BY ("exifInfo"->>'fileSizeInByte')::bigint DESC
LIMIT 50;
```

**RAW+JPEG pairs:**
```sql
-- Find RAW files that have a matching JPEG
WITH raws AS (
  SELECT "originalFileName",
    regexp_replace("originalFileName", '\.[^.]+$', '') as base_name,
    ("exifInfo"->>'fileSizeInByte')::bigint as size
  FROM asset
  WHERE "deletedAt" IS NULL
    AND upper(split_part("originalPath", '.', -1)) IN ('ARW', 'CR2', 'CR3', 'NEF', 'RAF', 'DNG', 'ORF', 'RW2')
),
jpegs AS (
  SELECT regexp_replace("originalFileName", '\.[^.]+$', '') as base_name
  FROM asset
  WHERE "deletedAt" IS NULL
    AND upper(split_part("originalPath", '.', -1)) IN ('JPG', 'JPEG')
)
SELECT count(*) as raw_with_jpeg,
  pg_size_pretty(sum(r.size)) as raw_size_reclaimable
FROM raws r
INNER JOIN jpegs j ON r.base_name = j.base_name;
```

**Videos by size tier:**
```sql
SELECT
  CASE
    WHEN ("exifInfo"->>'fileSizeInByte')::bigint > 1073741824 THEN '>1GB'
    WHEN ("exifInfo"->>'fileSizeInByte')::bigint > 524288000 THEN '500MB-1GB'
    WHEN ("exifInfo"->>'fileSizeInByte')::bigint > 104857600 THEN '100-500MB'
    WHEN ("exifInfo"->>'fileSizeInByte')::bigint > 52428800 THEN '50-100MB'
    ELSE '<50MB'
  END as size_tier,
  count(*) as videos,
  pg_size_pretty(sum(("exifInfo"->>'fileSizeInByte')::bigint)) as total
FROM asset
WHERE "deletedAt" IS NULL AND type = 'VIDEO'
GROUP BY 1 ORDER BY min(("exifInfo"->>'fileSizeInByte')::bigint) DESC;
```

### Step 4: Growth Projection

```sql
-- Monthly storage growth
SELECT
  date_trunc('month', "localDateTime") as month,
  count(*) as new_assets,
  pg_size_pretty(sum(("exifInfo"->>'fileSizeInByte')::bigint)) as monthly_growth
FROM asset WHERE "deletedAt" IS NULL
  AND "localDateTime" > now() - interval '12 months'
GROUP BY 1 ORDER BY 1;
```

Calculate: at current growth rate, how many months until disk is full?

When only a count is needed (how many videos, how many photos from one camera, how many favorites), use `search_statistics` instead of a query or a search: it returns the number alone, so a whole breakdown costs a handful of integers rather than pages of assets. `get_timeline_buckets()` gives the month-by-month volume the growth projection needs, also in one call.

### Step 5: Generate Report

```
STORAGE ANALYSIS
═══════════════════════════════════════

OVERVIEW
  Total storage:       182.4 GB
  Photos:              94.2 GB (39,596 files, avg 2.4 MB)
  Videos:              85.1 GB (4,983 files, avg 17.1 MB)
  Trash:               12.3 GB (8,433 files) ← RECLAIMABLE NOW

TOP CONSUMERS
  1. Videos >100MB:     43 files, 18.2 GB
  2. RAW files:         892 files, 22.4 GB (614 have matching JPEGs)
  3. HEIC photos:       7,890 files, 31.2 GB
  4. Large screenshots: 234 files, 1.8 GB

RECLAIMABLE SPACE
  Empty trash:                     12.3 GB
  Remove RAW where JPEG exists:    15.8 GB (614 RAW files)
  Remove large screenshots:         1.8 GB (234 files)
  TOTAL POTENTIAL:                 29.9 GB (16.4% of library)

GROWTH RATE
  Last 12 months:      2.1 GB/month average
  At current rate:     ~24 months until 250 GB disk full

RECOMMENDATIONS
  1. Empty trash immediately → 12.3 GB freed
  2. Review RAW+JPEG pairs → keep JPEGs, remove RAWs for 15.8 GB
  3. Review 43 videos >100MB — any worth compressing?
  4. 234 large screenshots — worth keeping?
```

## Optimization Actions (User-Approved)

- **Empty trash** → Immich API bulk delete with `force: true`
- **Remove RAW duplicates** → Delete RAW where JPEG exists (keep JPEG)
- **Flag large videos** → List for user review (no auto-action on videos)
- **Screenshot removal** → Integrate with photo-cleanup skill

**NEVER auto-delete.** Always present findings and wait for approval.

## Important Notes

- Storage calculations use EXIF fileSizeInByte which reflects the original file, not Immich's generated thumbnails/previews
- Immich also stores thumbnails, preview images, and ML embeddings — these are NOT included in the analysis but do consume disk space
- RAW+JPEG detection uses filename matching (base name without extension)
- Video transcoding recommendations depend on the user's quality preferences — always ask
- Growth projection assumes linear growth, which may not hold for seasonal photographers

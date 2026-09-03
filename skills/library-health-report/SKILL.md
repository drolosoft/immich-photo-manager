---
name: library-health-report
description: >
  Run a comprehensive health check on an Immich photo library — asset counts, storage usage,
  metadata completeness, orphaned files, and quality indicators.
  Use when the user says "library health", "health report", "library status", "library audit",
  "how healthy is my library", "photo stats", "library overview", "what's in my library",
  "library report", or any variation of wanting a comprehensive overview of their photo library's state.
version: 1.1.0
---

# Library Health Report

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

Generate a comprehensive health assessment of an Immich photo library. Covers asset inventory, storage breakdown, metadata quality, and actionable recommendations.

## When to Use

- First time exploring a new Immich library
- Periodic checkups (monthly/quarterly)
- After bulk imports to verify everything landed correctly
- Before cleanup operations to understand baseline

## Report Sections

### Section 0: What this server can do

Call `get_capabilities` once before anything else: it reports the server version, which features are actually enabled (OCR, smart search, facial recognition, map) and the quirks of that Immich major. A health report that says "GPS coverage 0%" is misleading when the map feature is simply off, and a section about OCR text makes no sense on a server without OCR. Mention the version in the report header.

### Section 1: Asset Inventory

Start with `get_statistics`. It is the official Immich count of photos, videos and storage used, in one call and with no database access. `search_statistics(...)` answers any narrower count ("how many videos", "how many favorites") the same cheap way.

The query below is an optional fallback for the columns the API does not expose, such as the trash breakdown by type. The plugin never provides database access, so it only applies if you already have `psql` on your own Immich:

```sql
-- Total assets by type
SELECT type, count(*) as total,
  pg_size_pretty(sum(("exifInfo"->>'fileSizeInByte')::bigint)) as total_size
FROM asset
WHERE "deletedAt" IS NULL
GROUP BY type;

-- Trash contents
SELECT type, count(*) as trashed
FROM asset
WHERE "deletedAt" IS NOT NULL
GROUP BY type;
```

Present as:

```
ASSET INVENTORY
  Photos:          39,596
  Videos:           4,983
  Total live:      44,579
  In trash:         8,433
  Storage used:    ~180 GB
```

### Section 2: Import Sources

Identify where photos came from:

```sql
SELECT
  CASE
    WHEN "originalPath" LIKE '%Apple Fotos%' OR "originalPath" LIKE '%Apple Photos%' THEN 'Apple Photos'
    WHEN "originalPath" LIKE '%Google Fotos%' OR "originalPath" LIKE '%Google Photos%' THEN 'Google Photos'
    WHEN "originalPath" LIKE '%upload%' THEN 'Direct Upload'
    ELSE split_part("originalPath", '/', 5)
  END as source,
  count(*) as total,
  min("localDateTime") as earliest,
  max("localDateTime") as latest
FROM asset WHERE "deletedAt" IS NULL
GROUP BY source ORDER BY total DESC;
```

### Section 3: Metadata Completeness

Check for gaps in critical metadata fields:

```sql
-- GPS coverage
SELECT
  count(*) as total,
  count(*) FILTER (WHERE "exifInfo"->>'latitude' IS NOT NULL) as has_gps,
  round(100.0 * count(*) FILTER (WHERE "exifInfo"->>'latitude' IS NOT NULL) / count(*), 1) as gps_pct
FROM asset WHERE "deletedAt" IS NULL AND type = 'IMAGE';

-- Date quality
SELECT
  count(*) FILTER (WHERE "exifInfo"->>'dateTimeOriginal' IS NOT NULL) as has_exif_date,
  count(*) FILTER (WHERE extract(hour from "localDateTime") = 12
    AND extract(minute from "localDateTime") = 0) as suspicious_noon,
  count(*) FILTER (WHERE extract(hour from "localDateTime") = 0
    AND extract(minute from "localDateTime") = 0) as suspicious_midnight
FROM asset WHERE "deletedAt" IS NULL AND type = 'IMAGE';

-- Camera info
SELECT
  count(*) FILTER (WHERE "exifInfo"->>'make' IS NOT NULL) as has_camera_make,
  count(*) FILTER (WHERE "exifInfo"->>'lensModel' IS NOT NULL) as has_lens
FROM asset WHERE "deletedAt" IS NULL AND type = 'IMAGE';
```

Present as:

```
METADATA QUALITY
  GPS coverage:        72.3% (28,616 of 39,596 photos)
  EXIF dates:          89.1% (35,280 photos)
  Suspicious dates:    1,204 (noon/midnight — likely recovered from paths)
  Camera info:         68.4% (27,072 photos)
  Lens info:           52.1% (20,623 photos)
```

### Section 4: Time Distribution

`get_timeline_buckets()` returns one bucket per month with its asset count in a single call, which is the whole year-by-year picture already: sum the buckets per year and the low years stand out. `get_calendar_heatmap(from_date=…, to_date=…)` adds the per-day detail for a year worth looking at more closely. Pass an explicit range: on Immich 2.x the counts are built from the timeline, one request per month in range, and an omitted bound falls back to the last 365 days.

The query below is the optional fallback when the photo/video split per year matters:

```sql
SELECT extract(year from "localDateTime") as year,
  count(*) as photos,
  count(*) FILTER (WHERE type = 'VIDEO') as videos
FROM asset WHERE "deletedAt" IS NULL
GROUP BY year ORDER BY year;
```

Highlight years with unusually low counts (potential missing imports).

### Section 5: File Format Breakdown

```sql
SELECT
  upper(split_part("originalPath", '.', -1)) as format,
  count(*) as total,
  pg_size_pretty(sum(("exifInfo"->>'fileSizeInByte')::bigint)) as size
FROM asset WHERE "deletedAt" IS NULL
GROUP BY format ORDER BY total DESC
LIMIT 15;
```

### Section 6: Recommendations

Based on findings, generate actionable recommendations:

- **Low GPS coverage?** → Suggest metadata-fixer skill
- **Suspicious dates?** → Suggest metadata-fixer skill
- **Multiple import sources?** → Suggest duplicate-report skill
- **Large trash?** → Suggest reviewing and permanently deleting
- **Year gaps?** → Suggest timeline-gaps skill
- **Heavy storage?** → Suggest storage-optimizer skill

## Output Format

The report can be presented as:
1. **Inline** — formatted text in the conversation
2. **Markdown file** — saved to the user's vault/workspace
3. **HTML dashboard** — interactive file with charts (uses Chart.js or Recharts)

Always ask the user which format they prefer.

## Important Notes

- This skill is **read-only** — it never modifies assets or metadata
- The whole report can be produced with the MCP tools alone: `get_capabilities`, `get_statistics`, `search_statistics`, `get_timeline_buckets` and `get_calendar_heatmap`
- The SQL blocks are an optional fallback for the few columns Immich's API does not expose (original paths, format breakdown). The plugin exposes no database tool, so running them means the user's own `psql` against their own Immich. Never ask for database credentials
- For libraries >50K assets, some queries may take 10-30 seconds
- Always show the query execution time so users know what to expect

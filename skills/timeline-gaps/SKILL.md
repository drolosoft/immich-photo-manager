---
name: timeline-gaps
description: >
  Analyze the photo timeline to find suspicious gaps: months or years with zero or very few photos.
  Helps identify failed imports, missing backups, or periods where photos exist in only one ecosystem.
  Use when the user says "timeline gaps", "missing months", "missing photos", "are there gaps",
  "what months am I missing", "photo timeline", "coverage check", "find missing periods",
  "when am I missing photos", or any variation of wanting to find holes in their photo timeline.
version: 1.1.0
---

# Timeline Gaps

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

Analyze the photo timeline month by month to detect gaps, anomalies, and coverage issues across import sources. Helps users discover missing imports, backup failures, or periods where photos only exist in one ecosystem.

## When to Use

- After importing from multiple sources to verify nothing was missed
- Periodic checkup to ensure continuous coverage
- Before deleting an import source to verify the other source covers those periods
- Investigating why certain memories seem to be missing

## Analysis Workflow

### Step 1: Build Monthly Timeline

Generate a complete month-by-month matrix across all sources. The MCP tool `get_timeline_buckets` returns one bucket per month with its asset count in a single call, so start there, and use the SQL below only when the per-source split matters, since the buckets do not know where a photo was imported from. The plugin never provides database access: the query is for a user who already has `psql` on their own Immich.

```sql
WITH months AS (
  SELECT generate_series(
    date_trunc('month', min("localDateTime")),
    date_trunc('month', max("localDateTime")),
    '1 month'::interval
  ) as month
  FROM asset WHERE "deletedAt" IS NULL
),
source_counts AS (
  SELECT
    date_trunc('month', "localDateTime") as month,
    CASE
      WHEN "originalPath" LIKE '%Apple%' THEN 'Apple'
      WHEN "originalPath" LIKE '%Google%' THEN 'Google'
      ELSE 'Other'
    END as source,
    count(*) as cnt
  FROM asset WHERE "deletedAt" IS NULL
  GROUP BY 1, 2
)
SELECT
  m.month,
  coalesce(sum(cnt) FILTER (WHERE source = 'Apple'), 0) as apple,
  coalesce(sum(cnt) FILTER (WHERE source = 'Google'), 0) as google,
  coalesce(sum(cnt) FILTER (WHERE source = 'Other'), 0) as other,
  coalesce(sum(cnt), 0) as total
FROM months m
LEFT JOIN source_counts sc ON m.month = sc.month
GROUP BY m.month
ORDER BY m.month;
```

### Step 2: Classify Each Month

Apply classification rules:

| Classification | Rule | Action |
|---|---|---|
| **EMPTY** | 0 photos total | Flag as critical gap |
| **SPARSE** | <10 photos AND user averaged >50/month that year | Flag as suspicious |
| **SINGLE-SOURCE** | One source has >90% of photos | Note dependency risk |
| **NORMAL** | Above thresholds | No action needed |

```python
# Classification logic
avg_monthly = total_photos / total_months

for month in timeline:
    if month.total == 0:
        month.status = 'EMPTY'
    elif month.total < max(10, avg_monthly * 0.1):
        month.status = 'SPARSE'
    elif month.dominant_source_pct > 0.9 and len(sources) > 1:
        month.status = 'SINGLE_SOURCE'
    else:
        month.status = 'NORMAL'
```

### Step 3: Detect Patterns

Look for systematic issues:

```sql
-- Consecutive empty months (indicates a bulk import failure)
-- Alternating source dominance (normal for dual-ecosystem users)
-- Sudden drops in a source (might indicate sync stopped)
-- Recent months with much lower counts (import not yet complete?)
```

### Step 4: Generate Report

```
TIMELINE ANALYSIS
══════════════════════════════════════

Coverage: Jan 2014 → Mar 2026 (147 months)

GAPS FOUND
  Empty months:      3
    - Aug 2015: 0 photos (Apple: 0, Google: 0)
    - Feb 2016: 0 photos (Apple: 0, Google: 0)
    - Nov 2019: 0 photos (Apple: 0, Google: 0)

  Sparse months:     7
    - Jan 2015: 4 photos (avg for 2015: 89/month)
    - Mar 2017: 2 photos (avg for 2017: 112/month)
    ...

SOURCE COVERAGE
  Apple Photos:  Jan 2016 → Mar 2026 (dominates 2016, 2018, 2024-2026)
  Google Photos: Mar 2014 → Dec 2023 (dominates 2017, 2019-2023)

  Single-source months: 48 (32%)
    Apple-only: 28 months
    Google-only: 20 months

YEAR OVERVIEW
  2014: ████░░░░░░░░  142 photos (Google only)
  2015: ████████░░░░  891 photos (sparse in Aug)
  2016: ██████████░░  1,204 photos (Apple dominant)
  ...

RECOMMENDATIONS
  1. Investigate Aug 2015, Feb 2016, Nov 2019 (check backups)
  2. Google Photos ends Dec 2023, intentional or missed import?
  3. 7 sparse months may indicate partial imports, cross-check with phone backups
```

### Step 5: Visual Timeline (Optional)

If the user wants an HTML output, generate an interactive timeline using a heatmap grid:
- Rows = years, columns = months
- Color intensity = photo count
- Color hue = dominant source (blue=Apple, red=Google, green=Other)
- Hover shows exact counts per source
- Empty cells highlighted in yellow/red

`get_calendar_heatmap(from_date=..., to_date=...)` returns the per-day counts this grid needs, already filtered to the days that have activity. Pass the narrowest range that answers the question: on Immich 2.x the counts are built from the timeline, one request per month in range, and an omitted bound falls back to the last 365 days rather than the whole library. `heatmap_type="Upload"` (import date instead of capture date) needs Immich 3.x.

## Cross-Source Gap Analysis

For users with multiple import sources, check if gaps in one source are covered by another:

```sql
-- Months where Apple has photos but Google doesn't
SELECT date_trunc('month', "localDateTime") as month, count(*)
FROM asset
WHERE "deletedAt" IS NULL AND "originalPath" LIKE '%Apple%'
AND date_trunc('month', "localDateTime") NOT IN (
  SELECT DISTINCT date_trunc('month', "localDateTime")
  FROM asset WHERE "deletedAt" IS NULL AND "originalPath" LIKE '%Google%'
)
GROUP BY 1 ORDER BY 1;
```

This answers: "If I delete all Google photos, which months would I lose coverage for?"

## Important Notes

- **Read-only**: this skill never modifies data
- Uses `localDateTime` (not `createdAt`) for accurate chronological analysis
- Photos with suspicious dates (midnight/noon) are flagged but still counted
- The "sparse" threshold adapts to the user's average volume: what's sparse for a heavy photographer is different from a casual one
- The month matrix and the heatmap come from `get_timeline_buckets` and `get_calendar_heatmap`, so the whole analysis runs on the MCP tools. Only the per-source split needs SQL, and `generate_series` there requires PostgreSQL (it won't work with SQLite)

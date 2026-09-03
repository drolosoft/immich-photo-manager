---
name: duplicate-report
description: >
  Run a full duplicate analysis on an Immich photo library using perceptual hashing.
  Finds cross-source duplicates (e.g. Apple Photos vs Google Photos exports), internal duplicates,
  and generates a detailed report with removal recommendations.
  Use when the user says "find duplicates", "duplicate report", "how many duplicates",
  "library health check", "photo dedup report", "run duplicate analysis",
  "compare my photo sources", or any variation of wanting to understand duplicate photos
  across import sources.
version: 1.2.0
---

# Duplicate Report

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

Generate a full duplicate analysis of an Immich photo library. Uses perceptual hashing to find visually identical photos even when they have different checksums (common when photos are exported from Apple Photos and Google Photos).

## Why Perceptual Hashing?

When users import the same photo library from multiple sources (Apple Photos export, Google Takeout, manual folder copies), the files are often **re-encoded** by each platform. This means:

- **Checksums differ**: same photo, different binary → SHA/MD5 won't match
- **Immich's built-in CLIP duplicate detection** uses too strict a threshold for re-encoded content
- **Filename matching** catches only a fraction (filenames often differ across platforms)

Perceptual hashing (pHash) computes a fingerprint based on the **visual content** of the image, not the binary data. Two re-encoded copies of the same photo produce the same perceptual hash.

## Prerequisites

The user's machine needs:

```bash
pip3 install Pillow imagehash pillow-heif --break-system-packages
```

- `Pillow`: image loading
- `imagehash`: perceptual hashing
- `pillow-heif`: HEIC/HEIF support (critical for Apple Photos)

## Analysis Workflow

### Step 0: ML-Based Duplicate Detection (Quick)

Before running the full perceptual hash scan, check Immich's built-in ML duplicate detection:

```
result = get_duplicates()
```

This returns groups of visually similar assets detected by Immich's ML engine. Present the count and let the user resolve obvious duplicates immediately using `resolve_duplicates`.

This is fast (no disk scan needed) but may miss re-encoded copies across import sources. For the full cross-source analysis, proceed to Step 1.

> Note: `resolve_duplicates` handles Immich ML duplicates natively. Perceptual hashing (Steps 1 to 3 below) catches cross-source re-encoded duplicates that ML may miss.

### Step 1: Discover Import Sources

Query Immich to identify distinct import sources from asset paths:

```sql
SELECT
  CASE
    WHEN "originalPath" LIKE '%Apple Fotos%' OR "originalPath" LIKE '%Apple Photos%' THEN 'Apple Photos'
    WHEN "originalPath" LIKE '%Google Fotos%' OR "originalPath" LIKE '%Google Photos%' THEN 'Google Photos'
    ELSE split_part("originalPath", '/', 5)  -- or whatever level gives the source folder
  END as source,
  count(*) as total
FROM asset WHERE "deletedAt" IS NULL
GROUP BY source ORDER BY total DESC;
```

Present the sources to the user and ask which ones to compare.

### Step 2: Run Perceptual Hash Scan

For each source directory, scan all image files and compute 256-bit perceptual hashes:

```python
from pillow_heif import register_heif_opener
register_heif_opener()

from PIL import Image
import imagehash

def compute_phash(filepath):
    with Image.open(filepath) as img:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return str(imagehash.phash(img, hash_size=16))
```

**Key parameters:**
- `hash_size=16` → 256-bit hash (high accuracy, very few false positives)
- Use `ThreadPoolExecutor` (NOT `ProcessPoolExecutor`, native HEIF libs deadlock on fork)
- 4 workers is optimal for most machines
- Report progress every 500 files

**Expected performance:** ~500 files/30 seconds on Apple Silicon, ~200 files/30 seconds on Intel.

### Step 3: Compute Overlap

Compare hash sets between sources:

```python
common = set(source_a_hashes.keys()) & set(source_b_hashes.keys())
a_only = set(source_a_hashes.keys()) - set(source_b_hashes.keys())
b_only = set(source_b_hashes.keys()) - set(source_a_hashes.keys())
```

For internal duplicates within a single source:
```python
internal_dupes = sum(len(v) - 1 for v in hashes.values() if len(v) > 1)
```

### Step 4: Generate Report

Present findings in a structured report:

```
DUPLICATE ANALYSIS REPORT

Library: [total] assets ([photos] photos + [videos] videos)
Sources analyzed: [Source A] ([count] files), [Source B] ([count] files)

CROSS-SOURCE DUPLICATES
  [Source A] <-> [Source B] visual matches:    [count] ([pct]% overlap)

UNIQUE TO EACH SOURCE
  [Source A]-only photos:               [count]
  [Source B]-only photos:               [count]

INTERNAL DUPLICATES
  Within [Source A]:                    [count]
  Within [Source B]:                    [count]

TOTAL REMOVABLE
  Cross-source duplicates:         [count]
  Internal duplicates:             [count]
  TOTAL:                           [count] files

RECOMMENDATION
  Keep: [Source with better metadata/folder structure]
  Remove: [Other source] copies where match exists
  Review: [count] [other]-only photos are NOT duplicates, keep them
```

### Step 5: Removal (User-Approved)

**NEVER auto-remove.** Always:

1. Present the report with counts
2. Ask user which categories to remove
3. Confirm the exact count
4. Execute removal in two steps:
   a. Move to Immich trash: `delete_assets(asset_ids=[...], force=False)`, safer and recoverable via `restore_assets` or `restore_trash`
   b. Physical file removal from disk (`os.remove()`) only after user confirms trash is correct
   c. For permanent deletion (user explicitly requests): `delete_assets(asset_ids=[...], force=True)`, irreversible
5. Log everything to a JSON file for audit

Batch Immich deletions in groups of 100 assets per call. For ML-detected duplicates, prefer `resolve_duplicates` which handles them natively in Immich.

For near-duplicates the user hesitates over (a burst, three tries at the same shot), offer `create_stack(asset_ids=[...])` as the middle option: the shots stay in the library but show as one item, with the first id passed as the cover. It is reversible with `delete_stack`, so it is the safe answer when "which one is best?" has no clear winner.

### Step 5b: Leave notes for the next pass

Before removal, remember the decision on every asset touched: `review_assets(kept_ids, "keep", "best of the group: <why>")` and `review_assets(trashed_ids, "duplicate_of", "duplicate of <kept filename>")`. A later run starts with `get_assets_notes(asset_ids)` and skips what already carries a verdict, so a 500-asset album is not re-analysed from scratch.

### Step 6: Verify

After removal, query Immich statistics to confirm the new count and present before/after comparison.

## Report Variations

### Quick Report (no disk scan)
The fast pass over the API is `get_duplicates`, which returns Immich's own ML-detected groups with their similarity scores, plus `search_large_assets` to see which of them are worth the space. Fast, but it misses re-encoded copies across sources.

The queries below go one level deeper (exact checksums, filename overlap between import paths). The plugin never provides database access, so they only apply to a user who already has `psql` on their own Immich.

```sql
-- Exact checksum duplicates
SELECT checksum, count(*) FROM asset
WHERE "deletedAt" IS NULL
GROUP BY checksum HAVING count(*) > 1;

-- Filename overlap between sources
SELECT count(*) FROM (
  SELECT "originalFileName" FROM asset WHERE "originalPath" LIKE '%Source A%'
  INTERSECT
  SELECT "originalFileName" FROM asset WHERE "originalPath" LIKE '%Source B%'
) t;
```

### Full Report (perceptual hash)
Scans actual files on disk. Catches re-encoded duplicates. Requires filesystem access and Python dependencies. Takes 10-20 minutes for ~40K photos on Apple Silicon.

### Year-by-Year Breakdown
Shows which source dominates each year, and helps users see where their photos came from over time:

```sql
SELECT year, source_a_count, source_b_count,
  CASE WHEN source_a_count > source_b_count THEN 'Source A' ELSE 'Source B' END as dominant
FROM (
  SELECT extract(year from "localDateTime") as year,
    count(*) FILTER (WHERE "originalPath" LIKE '%Source A%') as source_a_count,
    count(*) FILTER (WHERE "originalPath" LIKE '%Source B%') as source_b_count
  FROM asset WHERE "deletedAt" IS NULL
  GROUP BY year
) t ORDER BY year;
```

## Important Notes

- **Perceptual hashing has rare false positives**: two visually very similar (but different) photos may share a hash. The 256-bit hash size minimizes this, but users should spot-check a few matches before bulk removal.
- **Videos are excluded** from perceptual hashing: they need a different approach (frame extraction + hashing).
- **HEIC support is essential**: without `pillow-heif`, Apple Photos libraries will have massive error rates (50%+ of files).
- **ThreadPoolExecutor, not ProcessPoolExecutor**: native HEIF libraries deadlock when forked on macOS. Always use threads.
- **Background Immich scanning** may add new assets during analysis. Note this in the report if the post-cleanup count seems off.

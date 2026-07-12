# Skills Reference

Complete documentation for all 12 skills in the Immich Photo Manager plugin. Each skill is a specialized workflow that uses the MCP tools to perform intelligent photo management tasks.

---

## Overview

| # | Skill | Category | Modifies Data? | Requires |
|---|-------|----------|---------------|----------|
| 1 | [Album Manager](#1-album-manager) | Organization | Yes (creates albums) | MCP tools |
| 2 | [Photo Search](#2-photo-search) | Discovery | No | MCP tools |
| 3 | [Photo Cleanup](#3-photo-cleanup) | Maintenance | Yes (archive/delete) | MCP tools |
| 4 | [Duplicate Report](#4-duplicate-report) | Analysis | Yes (delete dupes) | Python + PostgreSQL + filesystem |
| 5 | [Library Health Report](#5-library-health-report) | Analysis | No | PostgreSQL |
| 6 | [Timeline Gaps](#6-timeline-gaps) | Analysis | No | PostgreSQL |
| 7 | [Metadata Fixer](#7-metadata-fixer) | Maintenance | Yes (updates EXIF) | PostgreSQL + Immich API |
| 8 | [Auto-Album Curator](#8-auto-album-curator) | Organization | Yes (adds to albums) | MCP tools |
| 9 | [Storage Optimizer](#9-storage-optimizer) | Analysis | Yes (optional delete) | PostgreSQL |
| 10 | [People Report](#10-people-report) | Analysis | No | PostgreSQL |
| 11 | [Travel Map](#11-travel-map) | Visualization | No | PostgreSQL |
| 12 | [Rotate Photos](#12-rotate-photos) | Maintenance | Yes (applies edits) | MCP tools |

**Safety principle**: Skills that modify data NEVER act automatically. They present findings, ask for approval, and only proceed with explicit confirmation.

---

## 1. Album Manager

**Trigger phrases**: "create an album", "organize photos by location", "album from my trip to X", "publish album", "list albums"

### What it does

Creates and curates Immich albums organized **geographically by default**. Albums represent places, not dates — if you visited Barcelona twice, you get one "Barcelona" album, not "Barcelona 2019" and "Barcelona 2023".

### Workflow

1. **Discover** — Searches for photos at a location using GPS coordinates, CLIP semantic search, or date ranges
2. **Filter** — Removes screenshots, duplicates, and low-quality images from candidates
3. **Curate** — Selects 20-50 representative photos (configurable)
4. **Create** — Names the album with country emoji + place name (e.g., "🇮🇹 Cinque Terre, Italia")
5. **Share** — Creates a shared link to make the album visible in the Gallery frontend

### Naming Convention

```
[Country emoji] Place, Country
🇮🇹 Cinque Terre, Italia
🇲🇽 Chiapas, México
🏝️ Lanzarote
🏙️ Barcelona
```

### Batch Mode

Say "create albums for all my trips" and the skill will:
- Scan all GPS data to identify distinct locations
- Propose an album list for approval
- Create all albums with progress reporting
- Err on the side of MORE albums (easier to merge than to discover missing ones)

### Example

```
User: "Create an album from my Rome trip in June 2023"
→ Searches city metadata ("Roma") + CLIP ("Colosseum, Roman ruins")
→ Cross-checks get_map_markers GPS points near Rome (41.90°N, 12.50°E)
→ Filters to June 2023 date range (taken_after/taken_before)
→ Finds 234 photos, curates to 45 best ones
→ Creates "🇮🇹 Roma, Italia" album
→ Creates shared link for Gallery
```

---

## 2. Photo Search

**Trigger phrases**: "find photos of", "search my photos", "photos from 2019", "photos near Barcelona", "do I have photos of sunsets"

### What it does

Natural language photo search that translates your intent into optimal Immich API queries. Combines GPS, CLIP (AI visual search), metadata, date ranges, and face recognition.

### Search Dimensions

| Dimension | Example Query | API Parameter |
|-----------|--------------|---------------|
| Visual/semantic | "sunset at the beach" | CLIP `query` |
| GPS location | "photos near Rome" | `get_map_markers` + client-side coordinate filtering |
| City/Country | "photos from Barcelona" | `city`, `country` |
| Date range | "photos from last Christmas" | `taken_after`, `taken_before` |
| Camera | "photos taken with iPhone" | `make`, `model` |
| Person | "who is Alice?" | `search_people(name)` — finds the person record; browse their photos in the Immich UI |
| Type | "all my videos" | `asset_type="VIDEO"` |
| Favorites | "my best photos" | `is_favorite=true` |

### Query Translation Examples

| You say | Skill does |
|---------|-----------|
| "photos from my Italy trip" | `country="Italy"` metadata + CLIP "Italy" |
| "screenshots on my phone" | CLIP "screenshot" + filename patterns (Screenshot*, Captura*) |
| "sunset photos" | CLIP search: "sunset" |
| "videos from Barcelona" | `city="Barcelona"` + `asset_type="VIDEO"` |
| "my best photos" | `is_favorite=true` |

### Result Format

```
Found 147 photos matching "sunset photos in Spain"
Spanning: June 2019 — August 2024
Locations: Lanzarote (89), Barcelona (34), Sevilla (24)
12 appear to be screenshots (flagged)
→ Want me to create an album from these?
```

---

## 3. Photo Cleanup

**Trigger phrases**: "clean up my photos", "remove screenshots", "find duplicates", "library cleanup", "free up space"

### What it does

Detects screenshots, duplicates, and low-quality images using multi-signal analysis. Reports findings by confidence level and waits for your approval before any action.

### Detection Categories

#### Screenshots (highest impact)

Candidates are surfaced with CLIP (`search_smart("screenshot")`) and filename patterns, then scored by combining multiple signals (dimensions and EXIF checked per asset via `get_asset_info` — they are not searchable):

| Signal | Weight | Method |
|--------|--------|--------|
| Screen resolution | High | `get_asset_info` dimensions exactly match known screen sizes |
| No GPS | Medium | EXIF GPS fields empty |
| No lens info | Medium | No focal length, aperture, or lens model |
| Filename pattern | Low | Contains "Screenshot", "Screen Shot", "Captura" |

**Confidence levels**:
- **High**: Screen resolution + no GPS + no lens → almost certainly a screenshot
- **Medium**: Screen resolution only, or no GPS + no lens but non-standard resolution
- **Low**: Single signal match → needs manual review

Known screen resolutions: iPhone (750x1334 through 1290x2796), Mac (1920x1080 through 3456x2234), Android (1080x1920 through 1440x3200).

#### Duplicates

| Type | Detection | Safety |
|------|-----------|--------|
| Exact duplicates | Same SHA-256 hash | Safe to remove copy |
| Format duplicates | Same timestamp + dimensions, different format | Keep highest quality |
| Near-duplicates | Same timestamp + high CLIP similarity | Present to user |
| Burst groups | Sequential timestamps < 2s apart | Let user pick best |

#### Low Quality

Very dark, very blurry, tiny resolution (<640x480), corrupt files. Always flagged for review, never auto-removed — some intentionally dark/blurry photos are artistic.

### Quick Scan Report

```
📊 Library: 44,579 assets (182 GB)
📱 Probable screenshots: ~2,400 (5.4%)
🔄 Probable duplicates: ~912 (2.0%)
📉 Low quality candidates: ~340 (0.8%)
💾 Estimated space recoverable: ~8.2 GB
```

### What is NEVER cleaned

- Photos with faces detected (valuable memories)
- Photos in existing albums (already curated)
- Favorited photos (explicitly marked as wanted)
- Videos (separate cleanup criteria)

---

## 4. Duplicate Report

**Trigger phrases**: "find duplicates", "duplicate report", "library health check", "compare my photo sources", "run duplicate analysis"

### What it does

Deep cross-source duplicate analysis using **perceptual hashing** (pHash). The only reliable method for finding duplicates across Apple Photos and Google Photos, where the same photo gets re-encoded by each platform — making checksums useless.

### Why not checksums?

When you import the same photo from Apple Photos and Google Takeout, the files are binary-different (re-encoded). Checksums, filenames, and even Immich's built-in CLIP duplicate detection all fail. Perceptual hashing compares the **visual content**, not the bytes.

### Prerequisites

```bash
pip3 install Pillow imagehash pillow-heif
```

- `pillow-heif` is critical — without it, 40%+ of Apple Photos (HEIC format) can't be processed
- Must use `ThreadPoolExecutor` (not `ProcessPoolExecutor`) — native HEIF libs deadlock on fork on macOS

### Workflow

1. **Discover sources** — Query Immich DB for distinct import paths (Apple, Google, manual, etc.)
2. **Hash scan** — Compute 256-bit perceptual hashes for all photos (~500 files/30s on Apple Silicon)
3. **Cross-match** — Find hashes that appear in multiple sources
4. **Internal scan** — Find hashes that appear multiple times within a single source
5. **Report** — Present overlap stats, unique counts, recommendations
6. **Remove** (user-approved) — Permanent delete from Immich + physical file removal
7. **Verify** — Post-cleanup count comparison

### Report Format

```
DUPLICATE ANALYSIS REPORT

Library: 44,618 assets (39,596 photos + 4,983 videos)
Sources: Apple Photos (20,604), Google Photos (18,896)

CROSS-SOURCE DUPLICATES
  Apple ↔ Google: 795 (4.0% overlap)

INTERNAL DUPLICATES
  Within Apple: 44
  Within Google: 73

TOTAL REMOVABLE: 912 files
```

### Performance

~40,000 photos in 10-15 minutes on Apple Silicon M4 Pro. Uses 4 threads.

---

## 5. Library Health Report

**Trigger phrases**: "library health", "health report", "library audit", "how healthy is my library", "photo stats"

### What it does

Comprehensive health assessment of your Immich library. Covers asset inventory, storage breakdown, metadata quality (GPS coverage, EXIF dates, camera info), import source breakdown, time distribution, and file format analysis.

### Report Sections

1. **Asset Inventory** — Total photos, videos, trash contents, storage used
2. **Import Sources** — Where photos came from (Apple, Google, manual, etc.) with date ranges
3. **Metadata Completeness** — GPS coverage %, EXIF date %, suspicious timestamps (noon/midnight), camera info %
4. **Time Distribution** — Year-by-year photo counts with anomaly detection
5. **File Format Breakdown** — Formats by count and size (HEIC, JPEG, PNG, RAW, etc.)
6. **Recommendations** — Actionable suggestions based on findings (links to other skills)

### Example Output

```
METADATA QUALITY
  GPS coverage:        72.3% (28,616 of 39,596 photos)
  EXIF dates:          89.1%
  Suspicious dates:    1,204 (noon/midnight — likely recovered from paths)
  Camera info:         68.4%

RECOMMENDATIONS
  → Low GPS? Use metadata-fixer
  → Suspicious dates? Use metadata-fixer
  → Multiple sources? Run duplicate-report
  → Year gaps? Check timeline-gaps
```

### Output Formats

- **Inline** — formatted text in conversation
- **Markdown file** — saved to vault/workspace
- **HTML dashboard** — interactive with charts

---

## 6. Timeline Gaps

**Trigger phrases**: "timeline gaps", "missing months", "are there gaps", "photo timeline", "coverage check", "what months am I missing"

### What it does

Analyzes your photo timeline month by month to detect empty periods, sparse months, and single-source coverage risks. Critical for users with multiple import sources who need to ensure nothing fell through the cracks.

### Month Classification

| Status | Rule | Meaning |
|--------|------|---------|
| **EMPTY** | 0 photos | Critical gap — check backups |
| **SPARSE** | <10% of monthly average | Suspicious — possible failed import |
| **SINGLE-SOURCE** | One source has >90% | Dependency risk if that source is deleted |
| **NORMAL** | Above thresholds | All good |

### Cross-Source Gap Analysis

Answers critical questions like: "If I delete all Google Photos, which months would I lose coverage for?"

### Report Format

```
Coverage: Jan 2014 → Mar 2026 (147 months)

GAPS FOUND
  Empty months: 3 (Aug 2015, Feb 2016, Nov 2019)
  Sparse months: 7

SOURCE COVERAGE
  Apple Photos:  Jan 2016 → Mar 2026 (dominates 2016, 2018, 2024+)
  Google Photos: Mar 2014 → Dec 2023 (dominates 2017, 2019-2023)
  Single-source months: 48 (32%)
```

### Visual Output (Optional)

Interactive HTML heatmap: rows = years, columns = months, color intensity = photo count, hue = dominant source.

---

## 7. Metadata Fixer

**Trigger phrases**: "fix metadata", "fix dates", "wrong dates", "missing GPS", "noon dates", "midnight timestamps", "exif fix"

### What it does

Scans for broken or suspicious photo metadata and proposes corrections. Focuses on the most impactful fields: dates, GPS coordinates, and timezone offsets.

### Common Issues Detected

| Issue | Severity | How it happens |
|-------|----------|---------------|
| Noon/midnight timestamps | Medium | Dates recovered from folder paths lose time component |
| Missing GPS | Low | Some export tools strip GPS, airplane mode photos |
| Wrong timezone | High | Photos taken abroad with phone on home timezone |
| No EXIF date | Low | Screenshots, downloaded images, messaging apps |

### Fix Strategies

- **Neighbor interpolation**: For timestamp fixes — sorts photos by filename, finds nearest neighbor with real EXIF time, interpolates
- **GPS inference**: Copies GPS from nearest photo on the same day, same camera (only if gap < 2 hours)
- **Timezone correction**: Looks up timezone from GPS coordinates, compares with EXIF offset

### Safety

- All fixes require explicit approval
- Confidence scores help decide which fixes to trust
- Fix log (JSON) saved before every batch
- Test with 10 photos before applying to full set

---

## 8. Auto-Album Curator

**Trigger phrases**: "update my albums", "refresh albums", "curate albums", "new photos for albums", "keep albums fresh"

### What it does

Monitors your library for new photos that match existing albums. Uses GPS proximity, CLIP visual similarity, and temporal patterns to suggest additions.

### Album Type Detection

| Type | Detection | Search Strategy |
|------|-----------|----------------|
| **Location** | All photos within 50km radius | GPS proximity |
| **Event** | Photos span 1-7 days | Strict date range |
| **Trip** | 1-4 weeks, multiple locations | GPS along route |
| **Theme** | No GPS pattern, mixed dates | CLIP visual similarity |
| **People** | Named after a person | Face recognition |

### Scoring

Each candidate photo gets a relevance score (0-1):

| Signal | Weight |
|--------|--------|
| GPS proximity to album center | 0.4 |
| CLIP visual similarity | 0.3 |
| Temporal fit | 0.2 |
| Source match | 0.1 |

Only photos scoring > 0.6 are suggested.

### Scheduled Mode

Can run on a schedule: "Run album curation every Sunday at 9am" — scans for new photos added in the past week and generates a suggestions report.

---

## 9. Storage Optimizer

**Trigger phrases**: "storage", "disk space", "what's eating my disk", "free up space", "large files", "optimize storage"

### What it does

Identifies the biggest storage consumers and recommends strategies to reclaim space. Analyzes RAW+JPEG pairs, oversized videos, file format distribution, and projects growth rate.

### Key Analyses

- **RAW+JPEG pairs**: RAW files that have a matching JPEG — RAW is often 10x larger
- **Video size tiers**: Groups videos by size (>1GB, 500MB-1GB, 100-500MB, etc.)
- **Format efficiency**: Which formats use the most space relative to count
- **Growth projection**: At current import rate, how many months until disk is full

### Report Format

```
RECLAIMABLE SPACE
  Empty trash:                     12.3 GB
  Remove RAW where JPEG exists:    15.8 GB (614 files)
  Large screenshots:                1.8 GB (234 files)
  TOTAL POTENTIAL:                 29.9 GB (16.4% of library)

GROWTH RATE
  Last 12 months: 2.1 GB/month
  Months until 250 GB disk full: ~24
```

---

## 10. People Report

**Trigger phrases**: "people report", "faces report", "who's in my library", "unnamed faces", "how many people"

### What it does

Analyzes Immich's face recognition data: who appears most, unnamed clusters worth naming, co-occurrence patterns (who appears together), and timeline per person.

### Prerequisites

Immich's face detection and recognition must be enabled (ML container running) and the face detection job should have completed at least once.

### Key Insights

- **Top people**: Ranked by photo count with date ranges
- **Unnamed clusters**: Largest unnamed face clusters likely representing real people worth naming
- **Coverage improvement**: "Naming these 15 clusters would increase coverage from 58% to 82%"
- **Co-occurrence**: Who appears together most often (e.g., "María & Juan: 1,204 photos together")
- **Timeline per person**: When each person first and last appears

### Privacy Note

Face data is sensitive. Reports should not be shared publicly without consent.

---

## 11. Travel Map

**Trigger phrases**: "travel map", "show me everywhere I've been", "photo map", "map my photos", "location map"

### What it does

Generates an interactive HTML map (Leaflet.js + MarkerCluster) showing every location where photos were taken. Clusters by geographic proximity, shows photo counts and date ranges, and optionally includes a heatmap overlay.

### Map Features

- **Clustered pins**: Expand on zoom to show individual locations
- **Popups**: Location name, photo count, date range, visit count
- **Heatmap layer**: Toggle density visualization
- **Dark mode**: Dark tile provider matching the overall theme
- **Responsive**: Full-screen on mobile, works on all browsers

### Output Formats

| Format | Use case |
|--------|----------|
| **Standalone HTML** | Self-contained, opens in any browser |
| **Hosted page** | Deploy to your own domain |
| **Markdown report** | Text summary, no map |
| **JSON export** | Raw data for custom visualization |

### Privacy Warning

The map reveals where you live, work, and travel. Auth is recommended before hosting publicly.

---

## 12. Rotate Photos

**Trigger phrases**: "rotate photos", "rotate album", "fix rotation", "photos are sideways", "bulk rotate", "wrong orientation", "upside down photos"

### What it does

Bulk rotate photos by album or asset IDs. Non-destructive — uses Immich's built-in edits API so originals are never touched. Rotation is visible in the web UI, mobile app, and shared links.

### Workflow

1. **Select** — In Immich, pick the wrongly-rotated photos and add them to a temp album
2. **Rotate** — `rotate_assets(album_id="...", angle=90)` rotates the entire album
3. **Verify** — Check the Immich UI; thumbnails update to show the rotation
4. **Adjust** — Rotate again if needed (accumulates: 90+90=180), or `revert_asset_edits` to undo

### Key Behavior

| Behavior | Detail |
|----------|--------|
| Accumulation | Calling rotate 90° twice = 180°. Reads current angle and adds. |
| Full circle | 360° removes all edits entirely (`isEdited` returns to `false`) |
| Per-asset | Rotation is stored on the asset, not the album. Shows everywhere. |
| Revert | `revert_asset_edits(album_id="...")` removes all edits cleanly |

### MCP Tools Used

| Tool | Purpose |
|------|---------|
| `rotate_assets` | Apply rotation (accepts `album_id` or `asset_ids`) |
| `revert_asset_edits` | Remove all edits, restore original orientation |

---

## Skill Dependencies

```
library-health-report ─────────→ Recommends other skills based on findings
         │
         ├── timeline-gaps       (if year gaps detected)
         ├── duplicate-report    (if multiple import sources)
         ├── metadata-fixer      (if low GPS/date coverage)
         └── storage-optimizer   (if trash is large)

album-manager ←── auto-album-curator  (keeps albums fresh)
                                      
photo-cleanup ←── duplicate-report    (advanced dedup)
              ←── storage-optimizer   (identifies cleanup targets)

travel-map ←── metadata-fixer        (better GPS = better map)
```

## Recommended Workflow for New Users

1. **Start with**: `library-health-report` — understand your library
2. **Then**: `duplicate-report` — clean up cross-source duplicates
3. **Then**: `photo-cleanup` — remove screenshots and junk
4. **Then**: `metadata-fixer` — repair dates and GPS
5. **Then**: `timeline-gaps` — verify nothing is missing
6. **Then**: `storage-optimizer` — reclaim space
7. **Finally**: `album-manager` + `travel-map` — organize and visualize
8. **Ongoing**: `auto-album-curator` + `people-report` — maintenance

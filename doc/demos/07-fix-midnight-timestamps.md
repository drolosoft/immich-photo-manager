# ⏰ Fix Midnight Timestamps

> **4,307 photos stuck at 00:00 or 12:00.** Folder imports lose the time component. The plugin recovers it from neighboring photos.

When photos are imported from folder structures (Google Takeout, Apple export), the date is preserved but the time often defaults to midnight (00:00) or noon (12:00). This breaks your timeline and makes chronological browsing useless.

---

## Step 1: Find suspicious timestamps

```
search_metadata(taken_after="2023-06-01", taken_before="2023-07-01", size=200)
```

Claude inspects each photo's `dateTimeOriginal`:

```
SUSPICIOUS TIMESTAMPS: June 2023
══════════════════════════════════

Midnight (00:00:00):  47 photos  ⚠️
Noon (12:00:00):      23 photos  ⚠️
Normal times:        189 photos  ✅

Show affected photos? [Yes / No]
```

## Step 2: Find anchors

For each suspicious photo, Claude looks for the nearest photo with a real EXIF timestamp:

```
get_asset_info(asset_id="...")  → 2023-06-14 12:00:00 (NOON, suspicious)
get_asset_info(asset_id="...")  → 2023-06-14 15:27:33 (real EXIF, anchor)
get_asset_info(asset_id="...")  → 2023-06-14 12:00:00 (NOON, suspicious)
```

## Step 3: Interpolate

Claude sorts photos by filename (natural order within the same folder) and interpolates times from the nearest anchor:

```
TIMESTAMP FIX PROPOSAL
═══════════════════════

IMG_2847.jpg  12:00:00 → 15:23:41  (interpolated from IMG_2849 anchor)
IMG_2848.jpg  12:00:00 → 15:25:12  (interpolated from IMG_2849 anchor)
IMG_2849.jpg  15:27:33             (anchor, real EXIF time)
IMG_2850.jpg  12:00:00 → 15:29:54  (interpolated from IMG_2849 anchor)

Confidence: 0.85 (anchor is 2 photos away)

Apply fixes? [Yes / No]
```

## Step 4: Write the fixes

```
update_asset_metadata(asset_id="...", date_time_original="2023-06-14T15:23:41.000Z")
update_asset_metadata(asset_id="...", date_time_original="2023-06-14T15:25:12.000Z")
update_asset_metadata(asset_id="...", date_time_original="2023-06-14T15:29:54.000Z")
```

## Step 5: Verify

Your timeline now shows photos in the correct chronological order instead of all bunched at midnight.

---

## MCP tools used

| Tool | Purpose | Calls |
|------|---------|:-----:|
| `search_metadata` | Find photos in date range | paginated |
| `get_asset_info` | Check timestamp quality | per photo |
| `update_asset_metadata` | Write corrected timestamps | per fix |

## How interpolation works

```
Timeline:  ──────────────────────────────────────→

Anchor:                    IMG_2849 (15:27:33) ⚓

Suspicious: IMG_2847 (12:00) → 15:23:41  (estimated: -2 positions × ~2min)
            IMG_2848 (12:00) → 15:25:12  (estimated: -1 position × ~2min)
            IMG_2850 (12:00) → 15:29:54  (estimated: +1 position × ~2min)
```

The gap between sequential photos from the same camera is typically 1-3 minutes. Claude uses this pattern to estimate missing times.

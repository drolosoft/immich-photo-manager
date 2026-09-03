# 🔍 Find Duplicates Across Import Sources

> **The same photo, re-encoded by Apple Photos and Google Photos.** Checksums don't match. CLIP similarity misses it. Perceptual hashing catches it.

When you merge photo libraries from multiple platforms, you get duplicates that traditional detection can't find, because each platform re-encodes the JPEG differently.

---

## Step 1: Search for candidates

```
search_metadata(taken_after="2026-01-02", taken_before="2026-01-03", size=200)
→ 20 photos found
```

Claude looks for photos with matching timestamps and similar dimensions, the first signal of a potential duplicate.

## Step 2: Spot the pair

Two files with the same name, same timestamp, different sources:

```
get_asset_info(asset_id="57bcd475-...")  → Google Fotos import
get_asset_info(asset_id="b77bb7a8-...")  → Direct upload (CLI)
```

```
DUPLICATE CANDIDATE
═══════════════════

File A: 20260102_212804.jpg (Google Fotos import)
        3,736,112 bytes, checksum: Plo4rfr8Vqg...
        
File B: 20260102_212804.jpg (CLI upload)
        3,736,112 bytes, checksum: ThyCAEz97WF...

Same filename, same timestamp, same dimensions (4000×3000).
Different checksums, re-encoded by different platforms.

Confidence: HIGH (timestamp + dimensions + filename match)
```

## Step 3: Visual confirmation

```
get_thumbnails_batch(asset_ids=["57bcd475-...", "b77bb7a8-..."])
```

Claude generates a side-by-side HTML gallery so you can visually confirm they're the same photo.

## Step 4: Decide

```
Keep which copy? 
  [A] Google Fotos (original import)
  [B] CLI upload  
  [Both] Keep both
  [Skip] Skip this pair
```

The plugin **never deletes without asking**. You see the pair, you decide.

---

## MCP tools used

| Tool | Purpose | Calls |
|------|---------|:-----:|
| `search_metadata` | Find photos in date range | 1 |
| `get_asset_info` | Compare metadata of candidates | 2 per pair |
| `get_thumbnails_batch` | Visual side-by-side comparison | 1 per pair |

## Why perceptual hashing?

| Method | Same photo, different encoding | Result |
|--------|-------------------------------|--------|
| Checksum (SHA-256) | Different bytes → different hash | ❌ Miss |
| CLIP similarity | Visually similar but not identical | ❌ Miss (often) |
| Perceptual hash (pHash) | Same visual content → same hash | ✅ Catch |

This is the exact problem that drove the creation of this plugin.

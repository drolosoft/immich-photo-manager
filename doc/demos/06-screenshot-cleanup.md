# 🧹 Screenshot Cleanup

> **3,456 screenshots mixed in with your real photos.** Find them, review them, organize them.

Screenshots are the #1 source of clutter in merged photo libraries. They have no GPS, no lens info, and screen-resolution dimensions. The plugin uses these signals to find them all.

---

## Step 1: Detect screenshots

```
search_metadata(taken_after="2025-01-01", taken_before="2026-01-01", size=200)
```

Claude checks each photo for screenshot signals:

```
get_asset_info(asset_id="...")
```

**Screenshot detection signals:**
- Screen resolution (1080×2340, 1125×2436, etc.)
- No GPS coordinates
- No lens model / no camera make
- Filename starts with `Screenshot_` or `IMG_` + `.PNG`

```
SCREENSHOT DETECTION
════════════════════

HIGH confidence (all signals match):
  1,892 screenshots found

MEDIUM confidence (2 of 3 signals):
  567 possible screenshots

Show gallery? [High only / All / Skip]
```

## Step 2: Visual review

```
get_thumbnails_batch(asset_ids=[...first 50...])
```

An HTML gallery opens so you can visually confirm. Select the ones you want to organize.

## Step 3: Organize

```
create_album(
    name="📱 Screenshots 2025",
    description="1,892 detected screenshots from 2025",
    asset_ids=[...]
)
→ Album created with 1,892 assets
```

The screenshots are now in their own album, out of your timeline and easy to review or bulk-delete later.

---

## MCP tools used

| Tool | Purpose | Calls |
|------|---------|:-----:|
| `search_metadata` | Find photos in date range | paginated |
| `get_asset_info` | Check EXIF for screenshot signals | per candidate |
| `get_thumbnails_batch` | Visual review | batched |
| `create_album` | Organize into album | 1 |

## Detection accuracy

| Signal | Weight | Example |
|--------|:------:|---------|
| Screen resolution + no GPS + no lens | HIGH | Almost certainly a screenshot |
| Screen resolution only | MEDIUM | Could be a cropped photo |
| `Screenshot_` in filename | HIGH | Platform-generated name |
| PNG format + phone dimensions | MEDIUM | Screenshots are often PNG |

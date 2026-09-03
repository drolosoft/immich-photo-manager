# 🖼️ Interactive Gallery

> **Self-contained HTML galleries with embedded thumbnails, 3 themes, and a Cowork Actions Panel for batch operations.**

The plugin generates HTML pages that work anywhere: no server needed, no external requests. Thumbnails are base64-embedded directly in the file.

---

## Step 1: Pick your photos

From an album:

```
get_album(album_id="abc123-...")
→ "🇪🇸 Lanzarote, Jan 2026", 186 photos
```

Or from a search:

```
search_smart(query="beach sunset", size=30)
→ 23 results
```

## Step 2: Fetch thumbnails

```
get_album_thumbnails(album_id="abc123-...", size="thumbnail", limit=50)
→ 50 thumbnails fetched as base64 data URIs
```

Each thumbnail is ~5-15 KB of base64 data embedded directly in the HTML. No external requests, no CORS issues, no broken images.

## Step 3: Generate the gallery

Claude builds a self-contained HTML file with:

- **3 themes**: Light, Dark, Auto (follows system preference)
- **4 view modes**: Grid, List, Timeline, Map
- **Selection mode**: Click photos to select them
- **Cowork Actions Panel**: batch operations on selected photos

```html
<!-- The gallery is a single HTML file, ~500KB for 50 photos -->
<!-- Opens in any browser, works offline, no dependencies -->
```

## Step 4: Use the Actions Panel

Select photos in the gallery, then click an action button:

```
┌─────────────────────────────┐
│  ✅ 12 photos selected       │
│                              │
│  [ Add to Album ]            │
│  [ Create New Album ]        │
│  [ Remove from Album ]       │
│  [ Generate Share Link ]     │
│  [ Copy Asset IDs ]          │
└─────────────────────────────┘
```

Each action generates a command you paste back into Claude. Claude executes it using the MCP tools.

---

## MCP tools used

| Tool | Purpose |
|------|---------|
| `get_album` / `search_smart` / `search_metadata` | Find the photos |
| `get_album_thumbnails` / `get_thumbnails_batch` | Fetch embedded thumbnails |
| `create_album` / `add_assets_to_album` | Execute gallery actions |
| `create_shared_link` | Publish gallery as shareable link |

## Why base64 embedding?

Claude Desktop runs galleries in an `about:` sandbox that blocks all external network requests. Base64 embedding is the only way to show images. This also means galleries work offline, in any browser, with zero dependencies.

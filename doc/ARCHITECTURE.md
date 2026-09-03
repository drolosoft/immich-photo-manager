# Architecture: How Photos Reach the User

Technical explanation of how immich-photo-manager delivers photo galleries to users in Cowork sessions without requiring any additional server setup, browser extensions, or authentication dance.

---

## The Problem

A Cowork session runs inside a sandboxed environment. The HTML viewer operates under an `about:` protocol origin, which means:

1. **No outbound network requests**: `fetch()`, `XMLHttpRequest`, and even `<img src="https://...">` are all blocked by the browser sandbox.
2. **No cookies or auth headers**: Even if requests weren't blocked, the viewer has no way to attach an Immich API key to image requests.
3. **No CORS negotiation**: The `about:` origin cannot participate in CORS preflight, so `Access-Control-Allow-Origin: *` on the Immich server does not help inside the Cowork sandbox. However, if CORS headers are configured on the reverse proxy, direct URL-based thumbnail loading works when the gallery is opened in a regular browser. See [CORS Setup Guide](./CORS-SETUP.md) for details.

This means the traditional approach of serving `<img src="https://immich-server/api/assets/{id}/thumbnail">` does not work.

---

## The Solution: Base64-Embedded Thumbnails

Instead of referencing external URLs, the plugin embeds every thumbnail directly into the HTML as a base64 data URI:

```html
<img src="data:image/jpeg;base64,/9j/4AAQSkZJRg..." />
```

The HTML file becomes a **fully self-contained document**: no network requests are needed to render any image. It works the same whether opened from a local file, an `about:` sandbox, or a regular browser tab.

---

## Data Flow (Step by Step)

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────┐
│  Claude   │────>│  MCP Server  │────>│  Immich API  │────>│  Immich DB │
│ (Cowork)  │<────│  (Python)    │<────│  (REST)      │<────│  + Storage │
└──────────┘     └──────────────┘     └──────────────┘     └────────────┘
      │
      │  1. search_metadata / search_smart  →  asset IDs + metadata
      │  2. get_thumbnails_batch            →  base64 JPEG data
      │  3. Inject into HTML template       →  self-contained HTML
      │  4. Write to outputs/               →  computer:// link
      │
      ▼
┌──────────────────────────────────────────────────────────────────────┐
│  HTML Gallery (fully self-contained, ~1MB for 50 photos)            │
│                                                                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                               │
│  │ base64  │ │ base64  │ │ base64  │  ...                           │
│  │ ~18 KB  │ │ ~18 KB  │ │ ~18 KB  │                               │
│  └─────────┘ └─────────┘ └─────────┘                               │
│                                                                      │
│  Zero network requests. Opens instantly. Works offline.              │
└──────────────────────────────────────────────────────────────────────┘
```

### Step 1: Search

Claude calls `search_metadata(city="Barcelona")` or `search_smart(query="sunset")` via the MCP server. Immich returns a paginated list of asset objects containing IDs, filenames, dates, and EXIF metadata. This is lightweight JSON, a few KB even for hundreds of results.

### Step 2: Thumbnail Fetch

Claude calls `get_thumbnails_batch(asset_ids=[...], size="thumbnail", limit=50)`. The MCP server iterates over the asset IDs, calling `GET /api/assets/{id}/thumbnail?size=thumbnail` for each one. Each thumbnail is a ~250px JPEG weighing 3-25 KB. The MCP server returns them as base64 strings.

### Step 3: HTML Generation

Claude reads the gallery template (`assets/viewer-template.html`) and replaces placeholders:

| Placeholder | Content |
|-------------|---------|
| `{{ALBUM_NAME}}` | Gallery title (e.g., "Barcelona") |
| `{{PHOTO_COUNT}}` | Number of photos in this gallery |
| `{{ALBUM_TOTAL}}` | Total photos available (may exceed displayed count) |
| `{{PAGE_SIZE}}` | Photos per page for lazy loading |
| `{{PHOTO_ENTRIES}}` | JS object literals with `src: 'data:image/jpeg;base64,...'` |
| `{{ALBUMS_JSON}}` | Related real albums from the user's library |
| `{{IMMICH_URL}}` | Immich server URL for "Open in Immich" links |
| `{{SEARCH_QUERY}}` | Original search terms |

### Step 4: Delivery

The completed HTML is written to the outputs directory and presented to the user via a `computer://` link. The user clicks it and sees the gallery immediately: no loading spinners, no auth prompts, no server configuration.

---

## Why Base64 Instead of Alternatives?

| Approach | Works in Cowork sandbox? | Requires server setup? | Notes |
|----------|:------------------------:|:---------------------:|-------|
| **External `<img src>`** | No | Yes (CORS) | Blocked by `about:` origin |
| **Proxy server** | No | Yes | Same network restriction |
| **Service Worker** | No | No | Not available in `about:` |
| **Base64 data URIs** | **Yes** | **No** | Self-contained, zero dependencies |

Base64 encoding increases file size by ~33% compared to raw binary, but for thumbnails averaging 18 KB this means ~24 KB per image in base64, which is fine for galleries of 50-100 photos (~1.2-2.4 MB total HTML).

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Average thumbnail size (raw) | ~18 KB |
| Average thumbnail size (base64) | ~24 KB |
| 50-photo gallery HTML | ~1.2 MB |
| 100-photo gallery HTML | ~2.4 MB |
| Thumbnail fetch time (50 photos) | ~8-15 seconds |
| Gallery render time (browser) | < 1 second |

### Lazy Loading

The template uses `IntersectionObserver` for pagination. The first `PAGE_SIZE` images load immediately; subsequent pages load their `src` from `dataset.src` only when scrolled into view. Combined with a "Load more" button, this keeps initial paint fast even for 100+ photo galleries.

---

## MCP Server Role

The MCP server acts as an authenticated bridge:

```
Claude  ←──stdio──→  MCP Server  ←──HTTPS──→  Immich API
                      (Python)                  (your server)
```

Claude never sees the API key directly. The MCP server:

1. Receives tool calls over stdio (standard MCP protocol)
2. Translates them to Immich REST API calls with the API key in headers
3. Returns structured results (JSON for metadata, base64 for images)

When the MCP server is not available (tools not loaded in the session), the skill detects this at the ping step and directs the user to `/setup-immich-photo-manager`.

---

## Fallback: Direct API Access

In sessions where the MCP server is not connected but the user provides their Immich URL and API key, Claude can use the same workflow via `httpx` in Python:

```python
import httpx, base64

url = "https://your-immich.example.com"
key = "YOUR-API-KEY-HERE"
headers = {"x-api-key": key}

# Search
r = httpx.post(f"{url}/api/search/metadata", headers=headers, json={"city": "Barcelona"})
assets = r.json()["assets"]["items"]

# Fetch thumbnails
for asset in assets:
    r = httpx.get(f"{url}/api/assets/{asset['id']}/thumbnail?size=thumbnail",
                  headers={**headers, "Accept": "image/jpeg"})
    b64 = base64.b64encode(r.content).decode()
    # Inject into HTML template as data:image/jpeg;base64,{b64}
```

This produces identical results to the MCP-based workflow. The only difference is that the API key is visible in the session context (acceptable for interactive use, not recommended for automation).

---

## Template System

The gallery template (`assets/viewer-template.html`) is a single self-contained HTML file with:

- **Triple theme support**: Light, System (auto-detects via `prefers-color-scheme`), and Dark modes with CSS custom properties
- **Responsive grid**: Adapts from 1 to 4+ columns based on viewport
- **Lazy loading**: IntersectionObserver-based progressive image loading
- **Album navigation**: Links to related real albums in the user's Immich library
- **"Open in Immich" links**: Each photo links back to the full-resolution version in the Immich web UI
- **Keyboard navigation**: Arrow keys for fullscreen browsing

The template is read once, placeholders are replaced, and the result is written as a static HTML file. No build step, no bundling, no dependencies.

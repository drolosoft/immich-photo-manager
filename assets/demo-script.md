# Demo Script — immich-photo-manager

> Source of truth for the demo. Update this file first, then regenerate `demo.html`.
> When adding new features, add a scene here and re-run the demo build.

## Version
- **Script version**: 3.0.0
- **Plugin version**: 1.1.0
- **Last recorded**: (pending)
- **Output**: `assets/demo.gif` (< 5 MB target)
- **Target duration**: ~17 seconds (3 scenes)

## How to regenerate

1. Edit this file with new/updated scenes
2. Update `assets/demo.html` to match (or ask Claude to regenerate from this script)
3. Record the GIF:

```bash
# One command — fully automated via Playwright + ffmpeg
node scripts/record-demo.js

# On headless Linux / CI (no display):
xvfb-run node scripts/record-demo.js
```

### First-time setup (prerequisites)

```bash
npm install playwright
npx playwright install chromium
# macOS: brew install ffmpeg
# Linux: apt install ffmpeg xvfb
```

### What the script does

1. Starts a local HTTP server serving `assets/demo.html`
2. Opens headless Chromium (800×520, 2× retina, dark mode)
3. Records the full animation via Playwright's video recorder (~20s)
4. Converts WebM → GIF with ffmpeg two-pass palette optimization
5. Saves to `assets/demo.gif` (~2-3 MB)

### Configuration (in `scripts/record-demo.js`)

| Variable | Default | Description |
|----------|---------|-------------|
| `WIDTH` | 800 | Viewport width |
| `HEIGHT` | 520 | Viewport height |
| `WAIT_MS` | 20000 | Recording duration (ms) |
| `TRIM_START` | 0.3 | Trim dark intro (seconds) |
| `GIF_FPS` | 10 | GIF frame rate |
| `MAX_COLORS` | 96 | GIF palette size |

---

## Header

| Field | Value |
|-------|-------|
| **Icon** | 📸 |
| **Title** | immich-photo-manager |
| **Badge** | Initially hidden, appears after Scene 1 |
| **Stats** | 42,596 photos · 5,060 videos · 94 tools (appears after connection) |

---

## Scene 1 — Connection & Setup (FIRST THING USERS SEE)

Shows the mandatory setup flow. Every skill requires a connected server.

| Field | Value |
|-------|-------|
| **Prompt** | `/setup-immich-photo-manager` |
| **Visual** | Setup card with server URL field |
| **Animation** | URL types itself in → ping fires → ✅ Connected result |
| **Duration** | ~4.5s |

### What to show:
- User sends `/setup-immich-photo-manager`
- Claude responds with a setup card:
  - Title: "🔗 Connect to Immich"
  - Input field with label "Server URL"
  - URL types itself in character by character: `http://192.168.1.100:2283`
  - After URL completes, ping tool call appears
  - Success result block: "✅ Connected · Immich v2.6.2"
  - Stats line: "42,596 photos · 5,060 videos · 124 albums"
- Header badge transitions from hidden to "MCP Connected" (green)
- Header right stats appear: "42,596 photos · 5,060 videos · 94 tools"

### Key message:
Users understand immediately that the plugin connects to THEIR Immich server.

---

## Scene 2 — Interactive Gallery + Selection + Action (HERO FEATURE)

Shows the complete workflow: browse → select → act.

| Field | Value |
|-------|-------|
| **Prompt** | Show me my Barcelona photos |
| **Tools** | `search_smart` → `get_album_thumbnails` (real tool names) |
| **Result** | Gallery with thumbnails, then interactive selection, then action |
| **Duration** | ~8s |

### Animation sequence:
1. User sends "Show me my Barcelona photos"
2. Claude responds with tool calls + gallery preview
3. Gallery appears with 8 photo thumbnails (4×2 grid)
4. **Animated selection** (the key moment):
   - After 1.5s: checkmark appears on photo 1 (top-left)
   - After 1.8s: checkmark appears on photo 4
   - After 2.1s: checkmark appears on photo 6
   - Selection badge updates: "3 selected"
5. **Action click** (after 2.8s):
   - "📂 Add to Album" button pulses/highlights with a glow
6. **Toast notification** (after 3.3s):
   - Slides up from bottom of gallery: "📂 Copied to Cowork chat"
   - Subtext: "Add these 3 photos to album: a1b2c3, d4e5f6, g7h8i9"

### What to show in the gallery:
- Dark theme gallery with "🏖️ Barcelona — Barceloneta / Playa" header
- Subtitle: "1,273 photos · Showing 20"
- **Cowork Actions bar**: Select toggle (active), badge showing selection count
- **8 photo thumbnails** in 4-column grid, gradient placeholders
- **Action panel** below grid: 10 color-coded buttons in 5×2 grid:
  - 📋 Copy IDs (terracotta)
  - ➕ Create Album (green)
  - 📂 Add to Album (teal) ← THIS ONE GETS HIGHLIGHTED
  - 🔍 Get EXIF (purple)
  - 🔎 Find Similar (indigo)
  - ⭐ Set Cover (gold)
  - ⬇️ Download (sky blue)
  - ❤️ Add to Favs (rose/pink)
  - ⚠️ Remove (amber)
  - 🗑️ Delete (red)
- File link: `barcelona.html — open in browser`

### Key message:
Select photos visually → one click → command ready in your Cowork chat.

---

## Scene 3 — Batch Geographic Album Creation

| Field | Value |
|-------|-------|
| **Prompt** | Create albums for all my trips |
| **Tools** | `get_map_markers` → `create_album` (×47) |
| **Result** | Polaroid cards + success block |
| **Duration** | ~5s |

### What to show:
- Tool call: `get_map_markers` scanning 34,281 geotagged photos
- Text: Found **118 destinations** across 14 countries
- 3 polaroid cards with stacked effect and handwritten font (Caveat):
  - 🇮🇹 Roma & Vaticano
  - 🇪🇬 Cairo & Giza
  - 🇲🇽 Oaxaca
- Success block: "✅ 118 albums created · 34,281 photos organized"

---

## Full Capabilities Covered

The demo touches these plugin capabilities:

| # | Capability | Scene |
|---|-----------|-------|
| 1 | Server connection & setup | Scene 1 |
| 2 | Smart photo search | Scene 2 |
| 3 | Interactive HTML gallery generation | Scene 2 |
| 4 | Photo selection (visual, multi-select) | Scene 2 |
| 5 | Cowork Actions Panel (clipboard bridge) | Scene 2 |
| 6 | Album management (add to album) | Scene 2 |
| 7 | Geographic detection & mapping | Scene 3 |
| 8 | Batch album creation | Scene 3 |
### Capabilities NOT shown (mentioned in README):
- Screenshot/duplicate detection & cleanup
- Travel map generation
- Metadata fixing
- Timeline gap analysis
- People/face report
- Auto album curation
- Storage optimization

---

## Animation Timing

| Step | Element | Delay after prev | Cumulative |
|------|---------|----------------:|------------|
| 1 | Scene 1 user (`/setup-immich-photo-manager`) | 600ms | 0.6s |
| 2 | Scene 1 setup card + URL typing | 1200ms | 1.8s |
| 3 | Separator | 3500ms | 5.3s |
| 4 | Scene 2 user message | 600ms | 5.9s |
| 5 | Scene 2 gallery appears | 1800ms | 7.7s |
| 6 | Photo 1 selected (checkmark pops) | 1800ms | 9.5s |
| 7 | Photo 4 selected | 500ms | 10.0s |
| 8 | Photo 6 selected + badge "3 selected" | 500ms | 10.5s |
| 9 | "Add to Album" button glows | 900ms | 11.4s |
| 10 | Toast "Copied to Cowork chat" | 700ms | 12.1s |
| 11 | Separator + toast dismiss | 1800ms | 13.9s |
| 12 | Scene 3 user message | 600ms | 14.5s |
| 13 | Scene 3 polaroids + success | 1800ms | 16.3s |
| 14 | Progress bar fills to 100% | 1500ms | 17.8s |
| | **Total** | | **~17s** |

---

## Visual Style

| Element | Value |
|---------|-------|
| **Container** | 900px wide, white surface, 16px border-radius |
| **Background** | #ece7df (Claude warm cream) |
| **Surface** | #faf8f5 (warm white) |
| **Accent** | #c96442 (Claude terracotta) |
| **Font** | Inter for UI, Caveat for polaroid labels, SF Mono for tool calls |
| **Gallery theme** | Dark (#1a1917 background) |
| **Photo placeholders** | Gradient blocks (no real photos for privacy) |
| **Setup card** | White card with border, URL input field |
| **Toast** | Semi-transparent dark bar sliding up from gallery bottom |
| **Watermark** | 📸🧹🗺️ immich-photo-manager v1.1.0 · drolosoft.com |

---

## Recording Settings

| Setting | Value |
|---------|-------|
| **Method** | `scripts/record-demo.js` (Playwright + ffmpeg) |
| **Browser** | Headless Chromium, 800×520, 2× deviceScaleFactor |
| **Color scheme** | dark |
| **Format** | GIF, two-pass palette, < 5 MB |
| **FPS** | 10 |
| **Duration** | ~20s (trimmed 0.3s dark intro) |
| **Output size** | ~2.5 MB |
| **Overlays** | None (clean recording) |

---

## Safety Rules
- ONLY use gradient placeholders for photos — never real photos
- No faces, no real names, no real GPS data
- Delete any test albums after recording
- Verify GIF doesn't contain sensitive info before committing

---

## Post-Recording Checklist
1. [ ] GIF is under 5 MB
2. [ ] Save to `assets/demo.gif`
3. [ ] Update README.md `<img>` tag (already points to `assets/demo.gif`)
4. [ ] Commit + push to both remotes
5. [ ] Rebuild .plugin with `./build-plugin.sh`

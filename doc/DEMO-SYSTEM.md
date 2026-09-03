# Demo System: immich-photo-manager

> **Context prompt for Claude sessions working on the demo.**
> Read this file at the start of any session that involves modifying, recording, or embedding the demo.
> This document is the single source of truth for how the demo pipeline works.

---

## What this is

The immich-photo-manager plugin has a **self-playing animated demo page** (`assets/demo.html`) that shows the plugin's features in a simulated Cowork conversation. This page is:

1. **Recorded as a GIF** (`assets/demo.gif`) for the GitHub README
2. **Embedded as an iframe** on drolosoft.com for the plugin's marketing page
3. **The visual identity of the plugin**: it's what users see first when evaluating whether to install it

The demo is NOT static. It evolves with the plugin. Every time a skill is added, a visual is improved, or the Cowork UI changes, the demo needs to be updated and re-recorded.

---

## Architecture

```
assets/demo-script.md     ← Source of truth (scenes, timing, visual spec)
       ↓ (manual or Claude-assisted)
assets/demo.html           ← Self-contained animated HTML page
       ↓ (automated: scripts/record-demo.js)
assets/demo.gif            ← Output for GitHub README + drolosoft.com
```

### demo-script.md
Describes each scene, timing, visual style, and animation sequence. **Edit this first** when making changes. Then update demo.html to match.

### demo.html
A single self-contained HTML file (~470 KB) with:
- Base64-embedded real photos from the Immich library (thumbnail size, ~200×200)
- CSS animations and transitions for all visual effects
- JavaScript `play()` function with `setTimeout` chains for the animation sequence
- Dark-theme gallery mimicking the real plugin output
- Cowork-style UI elements (Claude avatar, user messages, tool calls)
- Total animation duration: ~17-18 seconds

**Key sections** (search by these comments in the code):
- `/* Cowork actions bar */`: Select button, Move to Album button, badge
- `@keyframes selectBtnClick`: Select button flash/glow animation
- `@keyframes btnClick`: Action button click animation
- `SELECT_INDICES = [0, 3, 5]`: Which gallery photos get selected
- `function play()`: The full animation sequence with timing
- `function typeUrl()`: URL typing animation in Scene 1
- `function selectPhoto()`: Photo selection with checkmark pop
- `function smoothScroll()`: Pixel-precise scrolling between scenes

**Photos in the gallery** (thumb-0 through thumb-7):
- These are real photos from the author's Immich library, fetched via the Immich MCP API
- To replace a photo: use `mcp__immich__get_asset_thumbnail` to get the image, convert to 200×200 square JPEG, base64 encode, and replace the `background-image:url(data:image/jpeg;base64,...)` in the corresponding `<div class="gallery-thumb" id="thumb-N">` element
- Use Python/Pillow for image conversion: WebP → crop square → resize 200×200 → JPEG quality 70 → base64

### demo.gif
Generated automatically by `scripts/record-demo.js`. Never edit this file manually.

### scripts/record-demo.js
Playwright + ffmpeg automated recorder. Configuration:

| Variable | Current | Description |
|----------|---------|-------------|
| `WIDTH` | 800 | Viewport width |
| `HEIGHT` | 640 | Viewport height |
| `WAIT_MS` | 20000 | Recording duration (ms) |
| `TRIM_START` | 0.3 | Trim initial dark frame (s) |
| `GIF_FPS` | 10 | Frames per second |
| `MAX_COLORS` | 96 | GIF palette size |
| `zoom` | 0.7 | CSS zoom applied to page body |

**Prerequisites:**
```bash
npm install playwright && npx playwright install chromium
# Emoji font (Linux): download NotoColorEmoji.ttf to ~/.local/share/fonts/
```

**Run:**
```bash
node scripts/record-demo.js          # macOS
xvfb-run node scripts/record-demo.js # Linux / Cowork sandbox
```

---

## The demo scenes (current: v3)

### Scene 1: Connection & Setup
User sends `/setup` → Claude shows a setup card → URL types itself → ping → ✅ Connected · Immich v2.6.2 → stats appear in header.

### Scene 2: Interactive Gallery + Selection + Action
User asks "Show me my Barcelona photos" → tool calls → gallery with 8 real photos → **Select button flashes** → 3 photos get selected with checkmark animation → "Add to Album" button glows → click → toast → confirmation messages → album view.

### Scene 3: Geographic Album Creation
User asks "Create albums for all my trips" → tool calls → polaroid cards (Roma, Cairo, Oaxaca) → ✅ 118 albums created.

---

## Workflow for modifying the demo

### Changing animation timing
Edit the `play()` function in `demo.html`. The `at(delay, fn)` pattern adds cumulative delays:
```javascript
at(600, () => reveal('s1-user'));     // 600ms after start
at(1200, () => reveal('s1-card'));    // 1800ms after start (600+1200)
```

### Replacing a gallery photo
1. Search Immich: `search_smart` with a descriptive query + city filter
2. Get thumbnail: `get_asset_thumbnail` with `size=thumbnail`
3. Convert: WebP → square crop → 200×200 JPEG → base64
4. Replace in demo.html: find `id="thumb-N"` and swap the base64 string

### Adding a new scene
1. Update `demo-script.md` with the new scene spec
2. Add HTML elements in `demo.html` (hidden by default with `opacity: 0`)
3. Add animation steps in `play()` using `at()`, `reveal()`, `fadeIn()`, `smoothScroll()`
4. Adjust `WAIT_MS` in `record-demo.js` if the animation got longer

### Re-recording after changes
```bash
node scripts/record-demo.js   # or xvfb-run on Linux
```
The GIF lands in `assets/demo.gif`. Commit and push to both remotes.

---

## Embedding on drolosoft.com

The demo can be embedded in two ways:

### Option A: GIF (current, for GitHub README)
```html
<img src="https://raw.githubusercontent.com/drolosoft/immich-photo-manager/main/assets/demo.gif"
     alt="immich-photo-manager demo" width="800">
```
**Pros:** Works everywhere, no JavaScript needed.
**Cons:** 3-4 MB, no interactivity, lossy quality, loops forever.

### Option B: iframe with demo.html (recommended for drolosoft.com)
```html
<iframe src="https://drolosoft.github.io/immich-photo-manager/assets/demo.html"
        width="800" height="640"
        style="border: none; border-radius: 16px; overflow: hidden;"
        loading="lazy">
</iframe>
```
**Pros:** Crisp rendering, smaller transfer (~470 KB), interactive potential, single play.
**Cons:** Requires GitHub Pages or hosting, needs JavaScript enabled.

To enable GitHub Pages hosting:
1. Go to drolosoft/immich-photo-manager → Settings → Pages
2. Set source to "Deploy from a branch" → `main` → `/ (root)`
3. The demo will be available at: `https://drolosoft.github.io/immich-photo-manager/assets/demo.html`

### Option C: Hybrid
Use the iframe on drolosoft.com, fall back to GIF for GitHub README and plugin registry.

---

## Files I will modify

When working on demo improvements, I will modify these files inside the `assets/` directory:

| File | What changes | Why |
|------|-------------|-----|
| `assets/demo-script.md` | Scene descriptions, timing tables, visual spec | Source of truth, always update first |
| `assets/demo.html` | HTML structure, CSS animations, JS timing, base64 photos | The actual demo page |
| `assets/demo.gif` | Re-recorded output | Auto-generated by record-demo.js |
| `scripts/record-demo.js` | Viewport size, zoom, FPS, duration | Only when recording params change |

I will **not** modify skills, commands, MCP config, or any other plugin functionality when working on the demo. Those are separate concerns.

---

## Quality checklist

Before committing a demo change:

- [ ] `demo-script.md` matches what `demo.html` actually shows
- [ ] All emojis render correctly (no squares, needs the Noto Color Emoji font)
- [ ] Gallery photos are real Immich thumbnails, not placeholders
- [ ] Select button has visible flash/glow before photo selection
- [ ] All 3 scenes play completely within the recording window
- [ ] Scroll transitions are smooth, no content cut off
- [ ] GIF is < 5 MB
- [ ] GIF aspect ratio is landscape (wider than tall)
- [ ] demo.html works standalone in a browser (open directly, animation auto-plays)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Emojis show as squares in GIF | Install Noto Color Emoji font before recording |
| Content cut off at bottom | Decrease zoom (0.7 → 0.65) or increase HEIGHT |
| GIF too large | Reduce GIF_FPS (8), MAX_COLORS (64), or increase zoom |
| Animation too fast/slow | Edit `at()` delays in `play()` function |
| Photo looks wrong in gallery | Re-fetch from Immich, convert to 200×200 square JPEG |
| Recording is blank/black | Ensure demo.html `play()` fires on `window.load` |

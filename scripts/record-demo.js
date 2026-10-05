#!/usr/bin/env node
/**
 * record-demo.js — Record assets/demo.html animation as an optimized GIF.
 *
 * Uses Playwright (headless Chromium) to render the self-playing demo page,
 * captures video via Playwright's built-in recorder, then converts to GIF
 * with ffmpeg using a two-pass palette approach for best quality/size ratio.
 *
 * Usage:
 *   node scripts/record-demo.js              # macOS (has a display)
 *   xvfb-run node scripts/record-demo.js     # Linux / CI (headless)
 *
 * Prerequisites:
 *   npm install playwright
 *   npx playwright install chromium
 *   brew install ffmpeg   (macOS)  /  apt install ffmpeg  (Linux)
 *
 * Output: assets/demo.gif (~2-3 MB, 800×520, 10fps, ~20s)
 */

const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

// ── Paths ──────────────────────────────────────────────────────────────
const ROOT = path.resolve(__dirname, '..');
// demo.html lives on the gh-pages branch (it is too large for the plugin
// folder), so the default is the worktree next to the repo; DEMO_HTML overrides it.
const DEMO_PATH = process.env.DEMO_HTML
  || path.join(ROOT, '..', 'immich-photo-manager-pages', 'assets', 'demo.html');
const OUTPUT_GIF = path.join(ROOT, 'assets', 'demo.gif');
const VIDEO_DIR = path.join(require('os').tmpdir(), 'demo-video');
const PALETTE = path.join(require('os').tmpdir(), 'demo-palette.png');

// ── Config ─────────────────────────────────────────────────────────────
const PORT = 9876;
const WIDTH = 800;
const HEIGHT = 640;
const WAIT_MS = 20_000;    // animation duration + buffer
const TRIM_START = 0.3;    // trim dark intro (seconds)
const GIF_FPS = 10;
const MAX_COLORS = 96;

// ── HTTP server to serve demo.html ─────────────────────────────────────
function startServer() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const html = fs.readFileSync(DEMO_PATH, 'utf8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(html);
    });
    server.listen(PORT, () => {
      console.log(`  HTTP server → http://localhost:${PORT}`);
      resolve(server);
    });
  });
}

// ── Main ───────────────────────────────────────────────────────────────
(async () => {
  console.log('\n🎬 record-demo.js\n');

  // 1. Serve demo.html
  const server = await startServer();
  fs.mkdirSync(VIDEO_DIR, { recursive: true });

  // 2. Launch headless browser with video recording
  console.log('  Launching Chromium...');
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const context = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    recordVideo: { dir: VIDEO_DIR, size: { width: WIDTH, height: HEIGHT } },
    deviceScaleFactor: 2,
    colorScheme: 'dark',
  });

  const page = await context.newPage();

  // 3. Play the animation
  console.log('  Navigating to demo...');
  await page.goto(`http://localhost:${PORT}`, { waitUntil: 'load' });

  // Zoom out so all content fits in a landscape viewport
  await page.evaluate(() => {
    document.body.style.zoom = '0.7';
  });

  console.log(`  Recording (${WAIT_MS / 1000}s)...`);
  await page.waitForTimeout(WAIT_MS);

  // 4. Finalize video
  const videoPath = await page.video().path();
  await context.close();
  await browser.close();
  server.close();
  console.log(`  Video → ${videoPath}`);

  // 5. Convert to GIF (two-pass palette for quality)
  console.log('  Generating optimized GIF...');
  const scaleFilter = `fps=${GIF_FPS},scale=${WIDTH}:-1:flags=lanczos`;

  execFileSync('ffmpeg', [
    '-y', '-ss', String(TRIM_START), '-i', videoPath,
    '-vf', `${scaleFilter},palettegen=max_colors=${MAX_COLORS}:stats_mode=diff`,
    PALETTE,
  ], { stdio: 'pipe' });

  execFileSync('ffmpeg', [
    '-y', '-ss', String(TRIM_START), '-i', videoPath, '-i', PALETTE,
    '-lavfi', `${scaleFilter}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle`,
    OUTPUT_GIF,
  ], { stdio: 'pipe' });

  // 6. Report
  const size = (fs.statSync(OUTPUT_GIF).size / 1024 / 1024).toFixed(2);
  console.log(`\n  ✅ ${OUTPUT_GIF}`);
  console.log(`     ${size} MB · ${WIDTH}×${HEIGHT} · ${GIF_FPS}fps\n`);

  // Cleanup temp files
  try { fs.unlinkSync(videoPath); } catch {}
  try { fs.unlinkSync(PALETTE); } catch {}
})();

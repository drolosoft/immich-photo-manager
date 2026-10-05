#!/usr/bin/env node
/**
 * capture-screenshots.js — Take screenshots from the demo animation at key moments.
 *
 * Uses Playwright to open demo.html, waits for each scene to render,
 * and captures PNG screenshots for the README.
 *
 * Usage:
 *   node scripts/capture-screenshots.js
 *
 * Prerequisites:
 *   npm install playwright
 *   npx playwright install chromium
 *
 * Output: assets/screenshot-*.png
 */

const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const DEMO_PATH = path.join(ROOT, 'assets', 'demo.html');
const PORT = 9877;
const WIDTH = 1200;
const HEIGHT = 800;

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

async function screenshot(page, name, ms, description) {
  console.log(`  ⏳ Waiting ${ms}ms for: ${description}...`);
  await page.waitForTimeout(ms);
  const outPath = path.join(ROOT, 'assets', `screenshot-${name}.png`);
  await page.screenshot({ path: outPath, fullPage: false });
  const size = (fs.statSync(outPath).size / 1024).toFixed(0);
  console.log(`  📸 ${outPath} (${size} KB)`);
}

(async () => {
  console.log('\n📸 capture-screenshots.js\n');

  const server = await startServer();

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    deviceScaleFactor: 2,
    colorScheme: 'dark',
  });
  const page = await context.newPage();

  console.log('  Navigating to demo...');
  await page.goto(`http://localhost:${PORT}`, { waitUntil: 'load' });

  // Zoom to fit nicely
  await page.evaluate(() => {
    document.body.style.zoom = '0.85';
  });

  // Timeline (cumulative from page load):
  // ~600ms: Scene 1 user msg
  // ~1800ms: Scene 1 setup card
  // ~5300ms: Scene 2 separator + user msg
  // ~6100ms: Gallery appears
  // ~9600ms: 3 photos selected + panel shows "3 photos selected"
  // ~10500ms: Add to album button glows
  // ~13000ms: Paste command + confirmation
  // ~15000ms: Album view with added photos
  // ~17500ms: Geographic albums with flags

  // Screenshot 1: Setup complete (connection verified, badge visible)
  // Need ~5500ms total from load for setup result + badge to appear
  await screenshot(page, '01-setup', 5500, 'Setup complete with connection verified');

  // Screenshot 2: Gallery with photos visible (before selection)
  await screenshot(page, '02-gallery', 3000, 'Gallery with photos loaded');

  // Screenshot 3: Gallery with 3 photos selected + Cowork Actions Panel
  await screenshot(page, '03-gallery-selection', 4000, 'Gallery with selections + Cowork panel');

  // Screenshot 4: Paste command + album confirmation
  await screenshot(page, '04-cowork-action', 4000, 'Cowork action: paste command + confirmation');

  // Screenshot 5: Updated album view
  await screenshot(page, '05-album-view', 2000, 'Album view with added photos');

  // Screenshot 6: Geographic album creation (final scene)
  await screenshot(page, '06-geographic-albums', 3000, 'Geographic album creation with flags');

  await browser.close();
  server.close();

  console.log('\n  ✅ All screenshots captured!\n');
})();

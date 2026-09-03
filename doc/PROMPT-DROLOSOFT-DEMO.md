# Prompt: Embed immich-photo-manager demo on drolosoft.com

> Copy-paste this into a Cowork session working on the drolosoft.com website.

---

## Context

The **immich-photo-manager** plugin has an animated demo page that shows the plugin in action. It lives in the GitHub repo `drolosoft/immich-photo-manager` under `assets/`:

- **`assets/demo.html`**: Self-contained animated HTML page (~470 KB). It auto-plays on load: simulates a Cowork conversation showing server connection, photo search with an interactive gallery, photo selection, album actions, and batch geographic album creation. Duration: ~18 seconds. Contains base64-embedded real photos, CSS animations, and a JavaScript `play()` function that orchestrates the full sequence.

- **`assets/demo.gif`**: Pre-recorded GIF of the demo (800×640, ~3 MB). Generated automatically from demo.html using Playwright + ffmpeg. Used in the GitHub README.

- **`assets/demo-script.md`**: Source of truth for the demo scenes, timing, and visual spec.

## What I need

Embed the demo on the immich-photo-manager page of drolosoft.com. Two options:

### Option A: iframe (preferred, lighter and crisper)
```html
<iframe src="https://drolosoft.github.io/immich-photo-manager/assets/demo.html"
        width="800" height="640"
        style="border: none; border-radius: 16px; overflow: hidden;"
        loading="lazy">
</iframe>
```
This requires GitHub Pages enabled on the `drolosoft/immich-photo-manager` repo (Settings → Pages → Deploy from branch `main`, root `/`).

### Option B: GIF fallback (heavier but universal)
```html
<img src="https://raw.githubusercontent.com/drolosoft/immich-photo-manager/main/assets/demo.gif"
     alt="immich-photo-manager demo" width="800"
     style="border-radius: 16px;">
```

## Important

- The demo files (`assets/demo.html`, `assets/demo.gif`, `assets/demo-script.md`) are maintained in the `drolosoft/immich-photo-manager` repo, NOT in the drolosoft.com repo.
- I will modify these files frequently (adding scenes, replacing photos, adjusting timing) and re-record the GIF. The drolosoft.com page doesn't need to change when that happens because it loads the demo via URL (iframe or raw GitHub).
- The demo.html page is fully self-contained: no external dependencies, no API calls, no cookies. It just plays an animation on load.
- If using the iframe approach, the page needs GitHub Pages enabled. The URL would be: `https://drolosoft.github.io/immich-photo-manager/assets/demo.html`
- The demo has a dark-themed gallery section. Make sure the surrounding page design doesn't clash. A neutral or dark section background works best.

## Suggested placement

On the immich-photo-manager product/plugin page, after the headline and before the features list. Something like:

```
[Hero: plugin name + one-liner]
[Demo iframe or GIF, centered, 800px wide]
[Features / skills list]
[Install instructions]
[CTA: Install plugin]
```

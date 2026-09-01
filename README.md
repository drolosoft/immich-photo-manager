<p align="center">
  <img src="assets/icon.png" alt="immich-photo-manager" width="100">
</p>

<h1 align="center">immich-photo-manager</h1>

<p align="center">
  <a href="https://github.com/drolosoft/immich-photo-manager/actions/workflows/ci.yml"><img src="https://github.com/drolosoft/immich-photo-manager/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://glama.ai/mcp/servers/drolosoft/immich-photo-manager"><img src="https://glama.ai/mcp/servers/drolosoft/immich-photo-manager/badges/score.svg" alt="immich-photo-manager MCP server"></a>
  <a href="https://github.com/drolosoft/immich-photo-manager/releases/latest"><img src="https://img.shields.io/github/v/release/drolosoft/immich-photo-manager" alt="GitHub Release"></a>
  <a href="https://immich.app"><img src="https://img.shields.io/badge/Immich-ecosystem-blueviolet.svg" alt="Immich"></a>
  <a href="https://pypi.org/project/immich-photo-manager/"><img src="https://img.shields.io/pypi/v/immich-photo-manager" alt="PyPI"></a>
</p>
<p align="center">
  <a href="tests/live/"><img src="https://img.shields.io/badge/tested_live_on_Immich-2.7.5_%7C_3.1.0-2ea44f" alt="Tested live on Immich 2.7.5 and 3.1.0"></a>
  <a href="tests/"><img src="https://img.shields.io/badge/unit_tests-88_on_every_push-2ea44f" alt="88 unit tests on every push"></a>
  <a href="doc/demos/"><img src="https://img.shields.io/badge/demos-12_real_sessions-blue" alt="12 demos from real sessions"></a>
</p>

> **MCP server for intelligent photo management with [Immich](https://immich.app) — your self-hosted library, understood.**

If your [Immich](https://immich.app) library has grown past what you can manage by hand, **immich-photo-manager** gives any AI assistant direct access to your instance — search, organize, deduplicate, and curate albums through natural conversation. Works with Claude, Gemma, or any MCP-compatible client. Runs locally and talks only to your Immich; your originals stay on your server (see [what leaves your network](#what-leaves-your-network)).

> **Tested, not assumed.** Every push runs 210 unit tests on CI. Every release is also run **live against real Immich 2.7.5 and 3.1.0** (Docker, all 72 tools over the MCP protocol's legacy era, state re-read after each write) before it is tagged; both protocol eras — the legacy handshake and stateless 2026-07-28 — are pinned on every push by SDK-free wire tests ([`tests/test_raw_wire_eras.py`](tests/test_raw_wire_eras.py)). The kit is in [`tests/live/`](tests/live/), reproducible by anyone. The demos in [`doc/demos/`](doc/demos/) are transcripts of real sessions, [Demo 11](doc/demos/11-album-walkthrough.md) is this exact flow prompt by prompt, and [Demo 12](doc/demos/12-video-frames-and-pdf.md) runs the video frames and PDF photobook on a real clip. Details: [How it's tested](#how-its-tested).

<p align="center"><img src="./assets/demo.gif" alt="immich-photo-manager demo" width="800"></p>

---

## What It Does

Say **"create albums for all my trips"** and watch it work:

<p align="center"><img src="./assets/screenshot-06-geographic-albums.png" alt="Geographic album creation" width="700"></p>

GPS coordinates, CLIP visual search, and temporal matching — combined in one request to create dozens of curated albums. No scripts, no manual sorting.

---

## Quick Start

### Prerequisites

- A running [Immich](https://immich.app) instance (self-hosted, v1.90+)
- An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
- **Python 3.10+** with `pip` ([download](https://www.python.org/downloads/))

### Install (Claude Code plugin)

```sh
git clone https://github.com/drolosoft/immich-photo-manager.git
cd immich-photo-manager
pip3 install -r src/requirements.txt      # the plugin runs on your system python3

claude plugin marketplace add ./
claude plugin install immich-photo-manager
```

Open Claude Code (restart it if it was already open) and connect it to your Immich. Guided:

```
/setup-immich-photo-manager
```

It asks for your server URL and API key, checks them against the server, saves them, and shows your library numbers:

<p align="center"><img src="./assets/screenshot-01-setup.png" alt="/setup-immich-photo-manager: connected, Immich version and library size" width="700"></p>

Or skip the guide and say it in one line (same thing underneath):

```
Update my Immich credentials to http://immich.local:2283 with API key <your API key>
```

Either way the credentials are saved for every session from then on; repeat to change server or key. Confirm any time with:

```
What Immich version am I connected to?
```

That's the whole install. Claude Desktop, Cowork or another MCP client instead of Claude Code? That is the plain MCP server without the skills: see [Getting Started, route B](doc/GETTING-STARTED.md#route-b-script-claude-desktop-cowork-other-mcp-clients).

### Update the plugin

One line, no reinstall:

```sh
cd immich-photo-manager && git pull      # the clone you installed from
claude plugin marketplace update drolosoft-marketplace
claude plugin update immich-photo-manager@drolosoft-marketplace
```

Then restart Claude Code. `drolosoft-marketplace` is the name the marketplace gets when you add it from the clone (`claude plugin marketplace list` shows it). Your saved credentials carry over.

After pulling a new version, run `pip3 install -r src/requirements.txt` again: 1.7.1 added the video (`av`) and PDF (`fpdf2`) libraries to the plugin's dependencies. On the uvx route, `uvx --refresh immich-photo-manager --help` once, then restart the client.

### What leaves your network

The plugin process runs on your machine and only talks to your Immich. But everything the assistant *reads* through it goes to the model you use: filenames, dates, EXIF, album lists, and, when you ask it to look at pictures, thumbnails (250px by default, 1440px previews on request). Originals are never fetched. With Claude that means those thumbnails leave your network; with a local model over MCP (LM Studio, Ollama) nothing does. Nothing is sent unless you ask for it: listing albums or fixing dates moves text only, "tell me what's in these photos" moves images.

A PDF report follows the same rule: `export_pdf` writes the file to disk on the machine running the server, and it is not sent anywhere unless you pass `return_base64=true`. The file goes where `output_path` says (default your Desktop); existing files are never overwritten. Frames that only go into the PDF never leave your machine and cost no tokens; only the frames you ask the model to look at do. When the assets carry GPS, the Places page draws a map with tiles from `tile.openstreetmap.org` — the only third-party call this plugin makes; pass `map=false` to skip it and keep everything inside your network.

### Connect, check, switch — all by talking

You never edit config files after setup. The connection is managed in conversation:

| You say | What happens |
|---|---|
| **"What Immich version am I connected to?"** | Reports the server version and the URL it's talking to |
| **"Update my Immich credentials to `https://photos.example.com` with API key `…`"** | Validates the key against that server, hot-swaps the live connection, persists it — no restart |
| **"Show my Immich connection"** | URL + masked API key |

One connection at a time: to work with a second Immich (a test instance, a friend's server), say the *update* sentence again; say it once more to go back. Wrong URL or key? It tells you, and keeps the previous connection.

> Try the full walkthrough: **[Demo 11 — Album Walkthrough](doc/demos/11-album-walkthrough.md)** — read an album item by item, find who repeats, create a sub-album, tag and describe every photo.

### Works in Claude Code

The same plugin runs in **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** — search your library, curate albums, and generate galleries right from the terminal.

<p align="center"><img src="./doc/demos/cc/claude-code-conversation.png" alt="Split screen: Claude Code terminal generating a photo gallery on the left, browser showing the resulting gallery with album cards on the right" width="800"></p>

> Full conversation transcript: **[Claude Code demo](doc/demos/cc/claude-code-example-demo.txt)**

### Works with Any MCP Client

immich-photo-manager is an **MCP server** — it works with any AI assistant that speaks the Model Context Protocol, not just Claude.

Use the package entry point directly with `uvx`:

```json
{
  "mcpServers": {
    "immich": {
      "command": "uvx",
      "args": ["immich-photo-manager"],
      "env": {
        "IMMICH_BASE_URL": "https://your-immich-server.com",
        "IMMICH_API_KEY": "your-api-key"
      }
    }
  }
}
```

`immich-photo-manager` defaults to MCP stdio transport. Set `MCP_TRANSPORT=http` when you want to run the server as a Streamable HTTP service.

**Claude Desktop on macOS:** the app does not see your shell's PATH, so write the full path to `uvx` in `"command"` (run `which uvx` in a terminal; typically `/Users/<you>/.local/bin/uvx` or `/opt/homebrew/bin/uvx`). Run `uvx immich-photo-manager --help` once in a terminal so the first download is done, then quit Claude Desktop with Cmd+Q and reopen it. If it still does not show up, the reason is in `~/Library/Logs/Claude/mcp-server-immich.log`.

```
============================================================
IMMICH-PHOTO-MANAGER × GEMMA 4 (LM STUDIO)
============================================================

Immich: https://your-immich-server.com
Model:  gemma4-26b-it (local, LM Studio)
Query:  "Show me my Lanzarote albums"

1. Getting MCP tool schemas...
   72 MCP tools available

2. Asking Gemma 4...
   Gemma 4 chose: list_albums({})

3. Executing 'list_albums' against Immich...
   Found 124 total albums, 14 Lanzarote albums:
     - Lanzarote Amarillo (26 photos)
     - Lanzarote Rojo (201 photos)
     - Lanzarote Azul (187 photos)
     - Lanzarote Marrón (208 photos)
     - Lanzarote Negro (193 photos)
     - Lanzarote Verde (201 photos)
     - Lanzarote Gasolina (174 photos)
     ...

4. Gemma 4 interpreting results...
   "I found 14 Lanzarote albums — 7 color-themed with
    1,190 photos and 7 location-specific albums."

RESULT: Zero cloud dependency — fully self-hosted stack.
```

| Client | Status |
|--------|--------|
| Claude Code | Tested |
| Claude Desktop | Tested |
| LM Studio (Gemma 4) | Tested |
| Cursor, Windsurf, VS Code, Cline, Zed | Compatible (MCP stdio) |

> Full transcript: **[Gemma 4 demo](doc/demos/cc/lm-studio-gemma4-demo.txt)** · Test script: `test-lmstudio-mcp.py`

---

## Highlights

- **AI-powered search** — natural language photo search via CLIP ("sunset at the beach", "birthday cake")
- **Geographic albums** — create albums organized by place, combining GPS + CLIP + temporal matching
- **Metadata repair** — fix noon/midnight timestamps, infer missing GPS from neighboring photos, correct timezone offsets
- **Library cleanup** — detect screenshots, duplicates, and low-quality images with multi-signal analysis
- **Duplicate detection** — cross-source analysis using perceptual hashing (finds re-encoded copies across Apple Photos, Google Photos, and other imports)
- **Bulk rotation** — rotate entire albums or selections at once (90°/180°/270°); non-destructive, accumulates across calls, one-click revert
- **PDF reports** — album or selection to a PDF with metadata, video frames and Claude's captions, built on your machine; the photobook layout gives each chosen video moment a full page with its own caption, and the cover/index/places pages are optional
- **Video frames** — cut evenly spaced frames out of any clip, or a segment (`start`/`end`) down to one frame per second (`interval`), so Claude can describe what happens in it; Immich itself keeps one poster per video
- **People & face management** — list, search, merge, and organize recognized people; reassign misidentified faces; view face thumbnails
- **Trash & asset lifecycle** — safely delete assets to trash, permanently remove, restore from trash; complete asset lifecycle management
- **Library health** — one command for asset inventory, metadata quality, storage breakdown, and recommendations
- **Tags & organization** — create, apply, and manage tags across your library; bulk tag and untag assets
- **Interactive galleries** — self-contained HTML pages with embedded thumbnails, 3 themes, 4 view modes, and a Cowork Actions Panel for batch operations

<p align="center"><img src="./assets/screenshot-03-gallery-selection.png" alt="Interactive gallery with Cowork Actions" width="700"></p>

> Select photos in the gallery, click an action, and paste the command into Claude. See **[Skills Reference](doc/SKILLS.md)** for all 13 skills.

---

## Why immich-photo-manager?

Immich is excellent at storing and viewing your photos. But managing a large library — deduplication, metadata repair, album curation, storage analysis — still requires manual effort or custom scripts.

| | Manual / scripts | immich-photo-manager |
|:---:|---|---|
| 🔍 | Write API calls, parse JSON | **Natural language** — "find my sunset photos from Italy" |
| 🗺️ | Export GPS, cluster manually | **Geographic albums** — automatic GPS + CLIP + temporal matching |
| 🧹 | Hash files, diff checksums | **Perceptual hashing** — finds re-encoded duplicates across import sources |
| 🔧 | Edit EXIF one file at a time | **Metadata repair** — batch-fix timestamps, infer GPS, correct timezones |
| 📊 | Query database, build reports | **Library health** — one command for metadata quality, storage, recommendations |
| 🔄 | Rotate one photo at a time | **Bulk rotation** — rotate entire albums at once, non-destructive |
| 🏷️ | No tag management in UI | **Tags** — create, bulk apply/remove across assets |
| 🛡️ | Manual review of every action | **Safety first** — shows findings, asks before acting |

---

## How it's tested

- **Unit suite, every push**: 88 pytest cases on Python 3.10 and 3.13 (HTTP mocked), plus ruff. Releases are tagged only when this gate is green.
- **Live, every tool, two Immich versions**: [`tests/live/`](tests/live/) starts real Immich **2.7.5** and **3.1.0** in Docker, fills them with a small library, and drives all 72 tools over the MCP protocol, re-reading state after each write. Run before every release; last full run 2026-09-01, 102/102 checks on both.
- **In use**: [PyPI](https://pypi.org/project/immich-photo-manager/) downloads, merged PRs from four outside contributors, and the demos in [`doc/demos/`](doc/demos/) are transcripts of real sessions.

## Built with Claude

This is a Claude plugin, and Claude is a collaborator on the code: the design, the API compatibility decisions, and what to test are the author's; a good part of the implementation and the test harness were written with Claude Code. Every change ships through the same gate either way: tests on CI, and for anything touching Immich's API, the live run above.

## Documentation

| Document | Description |
|----------|-------------|
| **[Getting Started](doc/GETTING-STARTED.md)** | Installation, manual MCP setup, deployment options, and troubleshooting |
| **[Environment Setup](doc/GETTING-STARTED.md#environment-setup-detailed)** | Detailed setup: git, Python, venv, HTTP/stdio launch, Open WebUI, and common issues |
| **[Skills Reference](doc/SKILLS.md)** | All 13 skills — workflows, triggers, parameters, output formats |
| **[MCP Tools Reference](doc/MCP-TOOLS.md)** | All 72 MCP tools — parameters, return types, examples |
| **[Architecture](doc/ARCHITECTURE.md)** | How base64-embedded thumbnails solve the Cowork sandbox restriction |
| **[MCP 2026-07-28](doc/MCP-2026-07-28.md)** | Dual-era support: legacy handshake and the stateless revision from one server, and how it is verified |
| **[CORS Setup Guide](doc/CORS-SETUP.md)** | Optional — enable direct URL thumbnail loading for browser-viewed galleries |

---

## 🦙 Glama Score

<p align="center">
  <a href="https://glama.ai/mcp/servers/drolosoft/immich-photo-manager"><img src="https://glama.ai/mcp/servers/drolosoft/immich-photo-manager/badges/card.svg" alt="immich-photo-manager on Glama"></a>
</p>

---

## Contributing

Contributions are welcome — bug fixes, new skills, feature ideas. Open an issue or submit a PR.

If immich-photo-manager helps manage your library, consider giving it a star on GitHub — it helps others discover the project.

---

## Support

If immich-photo-manager saved you time or made your photo library easier to manage, consider buying me a coffee — it keeps the next one coming!

<p align="center">
<a href="https://buymeacoffee.com/juan.andres.morenorub.io"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50"></a>
</p>

---

## License

**MIT License** — free to use, modify, and distribute.

**Forged by [Drolosoft](https://drolosoft.com)** · *Tools we wish existed*

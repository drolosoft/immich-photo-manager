---
name: album-report
description: >
  Turn an album or a selection into a PDF report: metadata per photo, frames per video,
  and Claude's own description of what is in each one. Use when the user says "PDF of the album",
  "album report", "export to PDF", "make a document with these photos", "catalog the album",
  "identify what is in each video and put it in a PDF", or any variation of wanting a
  printable report of a set of photos and videos.
version: 1.0.0
---

# Album Report

## ⚠️ Connection Required — ALWAYS CHECK FIRST

**Before doing ANYTHING else in this skill, call `ping` on the Immich MCP server.**

- If `ping` succeeds → proceed with the skill normally.
- If `ping` fails or the MCP tools are not available → **STOP. Do not continue.** Tell the user:

> ❌ **Immich is not connected.** This plugin needs a running Immich MCP server to work.
>
> Run **/setup-immich-photo-manager** to configure your Immich connection. You'll need:
> 1. Your Immich server URL (e.g., `http://192.168.1.100:2283`)
> 2. An Immich API key ([how to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key))
> 3. The MCP server configured (see **/setup-immich-photo-manager**)
>
> Nothing in this plugin will work until the connection is configured.

**Do NOT skip this check. Do NOT try to run any other tool first. Always ping, always block if it fails.**

Build a PDF on the user's machine with `export_pdf`. Metadata comes from Immich; the descriptions come from you, after looking at the images.

## Workflow

1. `get_export_preview(album_id=…)` (or `asset_ids=…` from a search). Note the count and which items are videos, with their duration.
2. Look: `get_album_images(album_id, size="thumbnail")` for photos. For each video, `get_video_frames(asset_id, count=6)`.
3. For a long video, skim it first with one call: `get_video_frames(asset_id, interval=5, sheet=true)` returns contact sheets (30 stamped frames per image) instead of dozens of images. If a video needs a closer look (something passes between two frames), narrow it: `get_video_frames(asset_id, count=8, start=8, end=12)`, or `interval=1` for one frame per second. When the tool answers with `confirm_required`, tell the user the number of frames and the estimated tokens and continue only if they agree (`confirm=true`).
4. Write one caption per asset (what it shows, in the user's language) into `captions={asset_id: text}`.
5. `export_pdf(album_id=…, captions=…, frames_per_video=6)`; report the path, pages and warnings. Offer `layout="grid"` for big sets, `map=true` when there is GPS data (explain it fetches OpenStreetMap tiles), and a higher `frames_per_video` (up to 120, free of tokens) for videos that matter.
6. If the user wants the photos themselves and not only the report, `get_download_info(album_id=…)` says how big the zip would be and how many archives Immich would split it into, and `download_archive(output_path=…, album_id=…)` writes the originals next to the PDF. Say the size before downloading: originals and videos add up fast, and an existing file is never overwritten.

## Photobook

When the user wants an album book (one subject per page, like a car spotter's collection), use `layout="photobook"` with `frames_per_video=1`. A single blind frame is the middle of the video: after looking at a video's frames, pick its best moment and pass it in `frame_times={asset_id: [seconds]}` so the page carries the representative frame, not a lucky one. Then: every asset gets a full page, the image fitted without cropping, the caption under it; a video reads like a photo through its one preview-sized frame. Identify subjects by looking at `get_asset_image(size="preview")`, never at a thumbnail: closely related models (a Veyron against a Chiron) need the pixels. Write captions that say something real about the subject, and vary them when the same subject repeats. For a book meant for print, add `image_size="original"`: the stored photos at print quality instead of the 1440px previews. Live Photos count once (the motion clip folds into its still).

## Cost to state up front

Every frame you look at is one image in the context (~1.6k tokens as thumbnail). Frames that go only into the PDF cost nothing. Start with 6 per video; go finer only where the user asks.

## Requirements

None beyond the package since 1.7.1 (`fpdf2` and PyAV are dependencies). The tools say so when a library is missing.

## Example prompts

- "Make a PDF of the hypercars album with what you see in each video"
- "Export the photos of Curie to a PDF, grid layout"
- "Cut one frame per second of that clip and put them all in the report"

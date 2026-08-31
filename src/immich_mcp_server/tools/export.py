"""PDF export: preview what would be exported, then build the PDF on this machine.

Two tools live here. `get_export_preview` lists the assets an export would
contain so the model knows what exists before it looks at images and writes
captions. `export_pdf` fetches the images (and cuts video frames), hands
everything to `pdf_export.build` and writes the file where the user asked.

Every `@mcp.tool()` here registers on the shared FastMCP app from `..app` when this
module is imported; `server.py` imports all tool modules and re-exports the functions.
"""

import asyncio
import base64
import datetime
import io
import json
import os

from mcp.server.fastmcp import Context

from .. import __version__, pdf_export, video_frames
from ..app import mcp, _client
from ..pdf_export import AssetEntry, Document

# Hard ceiling on assets per export. Above this a PDF stops being a document
# and the fetch time (one preview per asset, in series) stops being reasonable.
EXPORT_MAX = 500

# `return_base64` above this size is refused: every megabyte of PDF is roughly
# 350k tokens once base64-encoded into the conversation.
BASE64_MAX_BYTES = 2 * 1024 * 1024

# Seconds to wait for one map tile from the event loop while `render_map` runs
# in a worker thread. Above the client's own 10 s HTTP timeout on purpose.
TILE_WAIT_SECONDS = 15

# Originals go into the PDF capped at this long side: A4 at 300 dpi is about
# 2480 px, so 3000 keeps print quality without embedding 40 MB camera files.
ORIGINAL_MAX_SIDE = 3000


def _duration_seconds(raw: dict) -> float:
    """Video duration in seconds from an Immich asset.

    Immich returns the duration either as a number of milliseconds or as an
    "H:MM:SS.mmm" string depending on the endpoint and version; both were seen
    on 2.7.5 and 3.1.0. Anything else counts as unknown (0.0).
    """
    raw_duration = raw.get("duration")
    if isinstance(raw_duration, (int, float)):
        return round(float(raw_duration) / 1000.0, 3)
    if isinstance(raw_duration, str) and ":" in raw_duration:
        hours, minutes, seconds = raw_duration.split(":")
        return round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 3)
    return 0.0


def _place(raw: dict) -> str:
    """'City, Country' from the asset's EXIF, or an empty string when there is none."""
    exif = raw.get("exifInfo") or {}
    return ", ".join(part for part in (exif.get("city"), exif.get("country")) if part)


def _summary(raw: dict) -> dict:
    """The few fields of an asset that the preview shows and the PDF prints."""
    return {
        "id": raw["id"],
        "type": raw.get("type", ""),
        "filename": raw.get("originalFileName", ""),
        "taken_at": raw.get("fileCreatedAt", ""),
        "place": _place(raw),
        "people": [person.get("name", "") for person in (raw.get("people") or []) if person.get("name")],
        "duration": _duration_seconds(raw) if raw.get("type") == "VIDEO" else None,
    }


async def _collect_assets(client, album_id: str, asset_ids: list[str], limit: int):
    """Resolve the export source to (title, raw assets, notes).

    Exactly one of `album_id` / `asset_ids` must be given. `limit` is clamped
    to 1..EXPORT_MAX; one extra asset is requested so the cut can be reported
    honestly instead of silently returning a shorter list.
    """
    if bool(album_id) == bool(asset_ids):
        raise ValueError("Pass exactly one of album_id or asset_ids.")
    limit = max(1, min(int(limit or 100), EXPORT_MAX))
    notes: list[str] = []
    if album_id:
        album = await client.get_album(album_id)
        title = album.get("albumName") or "Immich export"
        raw = await client.get_album_assets(album_id, limit=limit + 1, with_exif=True)
    else:
        title = ""
        raw = await client.get_assets_by_ids(asset_ids[: limit + 1], with_exif=True)
    if len(raw) > limit:
        raw = raw[:limit]
        notes.append(f"limit {limit} reached: only the first {limit} assets are included")
    # A Live Photo is one moment stored twice: the still points at its motion
    # clip through livePhotoVideoId. Keep the still, fold the clip.
    motion_ids = {asset.get("livePhotoVideoId") for asset in raw if asset.get("livePhotoVideoId")}
    if motion_ids:
        kept = [asset for asset in raw if asset["id"] not in motion_ids]
        folded = len(raw) - len(kept)
        if folded:
            raw = kept
            notes.append(f"{folded} live photo motion clip(s) folded into their photos")
    if not raw:
        raise ValueError("No assets found for that album/ids.")
    return title, raw, notes


def _entry_from_asset(raw: dict, captions: dict) -> AssetEntry:
    """An `AssetEntry` with the metadata filled in and no images yet."""
    exif = raw.get("exifInfo") or {}
    summary = _summary(raw)
    return AssetEntry(
        id=summary["id"],
        kind=summary["type"],
        filename=summary["filename"],
        taken_at=summary["taken_at"][:19].replace("T", " "),
        place=summary["place"],
        camera=" ".join(part for part in (exif.get("make"), exif.get("model")) if part),
        people=summary["people"],
        tags=[tag.get("name", "") for tag in (raw.get("tags") or []) if tag.get("name")],
        caption=str(captions.get(summary["id"], "")),
        lat=exif.get("latitude"),
        lon=exif.get("longitude"),
    )


async def _attach_video_frames(client, entry: AssetEntry, frames: int, interval: float,
                               frame_size: str, times: list[float], notes: list[str]) -> bool:
    """Cut frames for a video entry into `entry.images`; True when at least one frame landed.

    Any failure degrades to the poster (the caller fetches it) and leaves a
    note for the response: a bad video must never take the whole export down.
    """
    try:
        data = await client.get_video_playback(entry.id)
        if times:
            # The caller looked at the video and chose these exact moments.
            result = await asyncio.to_thread(video_frames.extract_frames_at, data, times, frame_size)
        else:
            result = await asyncio.to_thread(
                video_frames.extract_frames, data, frames, frame_size, None, 0.0, 0.0, interval
            )
    except video_frames.TooManyFrames as exc:
        notes.append(f"{entry.filename}: {exc}; poster used")
        return False
    except video_frames.NoVideoBackend as exc:
        # One note for the whole export is enough; every video would repeat it.
        if not any("poster" in note for note in notes):
            notes.append(f"video frames unavailable ({exc}): posters used")
        return False
    except Exception as exc:
        notes.append(f"{entry.filename}: frames failed ({exc}); poster used")
        return False
    if not result["frames"]:
        notes.append(f"{entry.filename}: no frames decoded; poster used")
        return False
    entry.images = [base64.b64decode(frame["data"]) for frame in result["frames"]]
    entry.timestamps = [frame["timestamp"] for frame in result["frames"]]
    return True


def _downscaled_original(data: bytes) -> bytes:
    """The original re-encoded as a JPEG no larger than ORIGINAL_MAX_SIDE.

    Raises whatever Pillow raises when the format cannot be decoded (a HEIC
    without a HEIF plugin, a RAW file); the caller falls back to the preview.
    """
    import io

    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as image:
        # Photos carry their rotation in EXIF; apply it or portrait shots lie down.
        image = ImageOps.exif_transpose(image)
        image.thumbnail((ORIGINAL_MAX_SIDE, ORIGINAL_MAX_SIDE))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=90)
        return buffer.getvalue()


async def _photo_bytes(client, entry: AssetEntry, image_size: str, notes: list[str]) -> bytes:
    """The image that represents a photo (or a video's poster) at the asked quality."""
    if image_size == "original" and entry.kind == "IMAGE":
        original = await client.get_asset_original(entry.id)
        try:
            return await asyncio.to_thread(_downscaled_original, original["data"])
        except Exception:
            notes.append(f"{entry.id}: original could not be decoded ({original.get('type')}); preview used")
    size = image_size if image_size in ("thumbnail", "preview") else "preview"
    thumb = await client.get_asset_thumbnail(entry.id, size)
    return base64.b64decode(thumb["data"])


async def _asset_entry(client, raw: dict, image_size: str, frames: int, interval: float,
                       frame_size: str, times: list[float], notes: list[str], captions: dict) -> AssetEntry:
    """Build the entry for one asset: metadata, then frames for a video or the poster/preview."""
    entry = _entry_from_asset(raw, captions)
    wants_frames = entry.kind == "VIDEO" and (frames > 0 or interval > 0 or bool(times))
    if wants_frames and await _attach_video_frames(client, entry, frames, interval, frame_size, times, notes):
        return entry
    entry.images = [await _photo_bytes(client, entry, image_size, notes)]
    return entry


async def _render_places_map(client, entries: list[AssetEntry], notes: list[str]) -> bytes | None:
    """The OpenStreetMap image for the Places page, or None with a note explaining why."""
    points = [(entry.lat, entry.lon) for entry in entries if entry.lat is not None and entry.lon is not None]
    if not points:
        notes.append("map requested but no asset has GPS data")
        return None

    # `render_map` is synchronous and runs in a worker thread, while the tile
    # download is a coroutine on the event loop. The callback bridges the two
    # and memoizes so a tile shared by several points is fetched once.
    tiles: dict = {}
    loop = asyncio.get_running_loop()

    def fetch(zoom, tile_x, tile_y):
        """One tile's PNG bytes, fetched on the event loop from the worker thread."""
        key = (zoom, tile_x, tile_y)
        if key not in tiles:
            future = asyncio.run_coroutine_threadsafe(client.fetch_tile(zoom, tile_x, tile_y), loop)
            tiles[key] = future.result(TILE_WAIT_SECONDS)
        return tiles[key]

    map_png = await asyncio.to_thread(pdf_export.render_map, points, fetch)
    if map_png is None:
        notes.append("map could not be drawn (tiles unavailable); Places table only")
    return map_png


def _resolve_output_path(output_path: str, title: str) -> str:
    """Where the PDF goes: the user's path, a directory, or the Desktop by default.

    A directory gets a file named after the title inside it; a path without
    the extension gets one. Existing files are never overwritten (`unique_path`).
    """
    if output_path:
        path = os.path.expanduser(output_path)
        if os.path.isdir(path):
            path = os.path.join(path, f"{pdf_export.slugify(title)}.pdf")
        elif not path.lower().endswith(".pdf"):
            path = f"{path}.pdf"
    else:
        path = os.path.expanduser(f"~/Desktop/{pdf_export.slugify(title)}.pdf")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    return pdf_export.unique_path(path)


def _count_pages(pdf: bytes) -> int:
    """Page count through pypdf when it is installed, else by scanning the objects."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(io.BytesIO(pdf)).pages)
    except Exception:
        # pypdf missing or unable to parse: the file is already written, so a
        # rough count is better than breaking the JSON contract.
        return pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")


@mcp.tool()
async def get_export_preview(ctx: Context, album_id: str = "", asset_ids: list[str] = [], limit: int = 100) -> str:
    """List what export_pdf would include (id, type, filename, date, place, people,
    video duration) so you know which assets exist before looking at images and
    writing captions. Pass exactly one of album_id / asset_ids. Read-only.

    Args:
        album_id: Album UUID, or
        asset_ids: Explicit asset UUIDs (search results, a selection).
        limit: Max assets (1-500, default 100).

    Returns: JSON {title, count, assets:[...], warnings:[...]} or {"error": ...}.
    """
    try:
        title, raw, notes = await _collect_assets(_client(ctx), album_id, asset_ids, limit)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps({
        "title": title,
        "count": len(raw),
        "assets": [_summary(asset) for asset in raw],
        "warnings": notes,
    })


@mcp.tool()
async def export_pdf(
    ctx: Context, album_id: str = "", asset_ids: list[str] = [], output_path: str = "",
    title: str = "", captions: dict = {}, layout: str = "detail", frames_per_video: int = 4,
    frame_interval: float = 0.0, frame_times: dict = {}, image_size: str = "preview",
    frame_size: str = "auto", map: bool = False, limit: int = 100, return_base64: bool = False,
) -> str:
    """Build a PDF (cover, index, places, one section per asset) from an album or a
    list of assets, on the machine running this server. Immich metadata (date, place,
    camera, people, tags) is always included; pass `captions` {asset_id: text} with
    what you saw to add your analysis. Video frames go straight into the PDF and cost
    no tokens (up to 120 per video). The PDF never enters the conversation unless
    return_base64=True.

    Args:
        album_id: Album UUID, or asset_ids: explicit asset UUIDs (exactly one of the two).
        output_path: Where to write (default ~/Desktop/<title>.pdf). Existing files are never overwritten.
        title: Cover title (default: album name or "Immich export <date>").
        captions: {asset_id: text} written after looking at the images.
        layout: 'detail' (one asset per page with its data, default), 'grid' (six per page)
            or 'photobook' (one asset per page, image as large as it fits, caption under it;
            pair it with frames_per_video=1 so a video reads like a photo).
        frames_per_video: Frames per video, evenly spaced (0-120, default 4; 0 = poster only).
        frame_interval: One frame every N seconds instead of frames_per_video (same 120 cap).
        frame_times: {asset_id: [seconds, ...]} exact moments for specific videos, chosen
            after looking at their frames ("the representative frame"). Wins over
            frames_per_video/frame_interval for the listed videos; others keep the spread.
        image_size: 'preview' (default, 1440px), 'thumbnail', or 'original' for photos:
            the stored file, print quality, re-encoded to at most 3000px (a format
            the server cannot decode, like some HEIC, falls back to preview with a note).
        frame_size: video frame size in the PDF: 'auto' (default: preview up to 4 frames
            per video, thumbnail above), 'preview' or 'thumbnail'.
        map: Add an OpenStreetMap map to the Places page (fetches tiles from tile.openstreetmap.org).
        limit: Max assets (1-500, default 100).
        return_base64: Also return the PDF bytes (skipped above 2 MB; every MB is
            roughly 350k tokens in the conversation).

    Returns: JSON {path, pages, bytes, assets_included, assets_skipped:[{id, reason}], warnings:[...]}.
    """
    client = _client(ctx)
    try:
        album_title, raw, notes = await _collect_assets(client, album_id, asset_ids, limit)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    if not pdf_export._fpdf_available():
        return json.dumps({"error": "PDF export needs fpdf2: `pip install fpdf2` (it ships with immich-photo-manager since 1.7.1)."})

    # Arguments come from the model: clamp and default them rather than fail.
    frames = max(0, min(int(frames_per_video or 0), video_frames.MAX_FRAMES))
    interval = float(frame_interval or 0)
    if layout not in ("detail", "grid", "photobook"):
        layout = "detail"
    if image_size not in ("thumbnail", "preview", "original"):
        image_size = "preview"
    # Few frames end up large on the page, so they deserve preview quality; a
    # long strip stays at thumbnail size to keep the file reasonable.
    if frame_size not in ("thumbnail", "preview"):
        frame_size = "preview" if (0 < frames <= 4 and not interval) else "thumbnail"
    title = title or album_title or f"Immich export {datetime.date.today().isoformat()}"

    # One asset failing (a 404 preview, a broken file) is reported, not fatal.
    entries: list[AssetEntry] = []
    skipped: list[dict] = []
    for asset in raw:
        try:
            times = [float(moment) for moment in (frame_times or {}).get(asset.get("id"), [])]
            entries.append(await _asset_entry(client, asset, image_size, frames, interval, frame_size, times, notes, captions or {}))
        except Exception as exc:
            skipped.append({"id": asset.get("id"), "reason": str(exc)[:200]})
    if not entries:
        return json.dumps({"error": "No asset could be fetched.", "assets_skipped": skipped})

    map_png = await _render_places_map(client, entries, notes) if map else None

    photos = sum(1 for entry in entries if entry.kind == "IMAGE")
    exported_on = datetime.date.today().isoformat()
    doc = Document(
        title=title,
        subtitle=f"{len(entries)} assets · {photos} photos, {len(entries) - photos} videos · exported {exported_on}",
        source_url=client.base_url,
        version=__version__,
        layout=layout,
        assets=entries,
        places=pdf_export.places_table(entries),
        map_png=map_png,
    )
    try:
        pdf = await asyncio.to_thread(pdf_export.build, doc)
    except pdf_export.NoPdfBackend as exc:
        return json.dumps({"error": str(exc)})

    path = _resolve_output_path(output_path, title)
    with open(path, "wb") as handle:
        handle.write(pdf)

    pdf_b64 = None
    if return_base64:
        if len(pdf) > BASE64_MAX_BYTES:
            notes.append("PDF larger than 2 MB: base64 not returned (read it from `path`)")
        else:
            pdf_b64 = base64.b64encode(pdf).decode("ascii")
    out = {
        "path": path,
        "pages": _count_pages(pdf),
        "bytes": len(pdf),
        "assets_included": len(entries),
        "assets_skipped": skipped,
        "warnings": notes,
    }
    if pdf_b64 is not None:
        out["pdf_base64"] = pdf_b64
    return json.dumps(out)

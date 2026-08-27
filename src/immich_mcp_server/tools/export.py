"""PDF export: preview what would be exported, then build the PDF on this machine.

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

EXPORT_MAX = 500


def _duration_seconds(raw: dict) -> float:
    raw_duration = raw.get("duration")
    if isinstance(raw_duration, (int, float)):
        return round(float(raw_duration) / 1000.0, 3)
    if isinstance(raw_duration, str) and ":" in raw_duration:
        hours, minutes, seconds = raw_duration.split(":")
        return round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 3)
    return 0.0


def _place(raw: dict) -> str:
    exif = raw.get("exifInfo") or {}
    return ", ".join(part for part in (exif.get("city"), exif.get("country")) if part)


def _summary(raw: dict) -> dict:
    return {
        "id": raw["id"], "type": raw.get("type", ""), "filename": raw.get("originalFileName", ""),
        "taken_at": raw.get("fileCreatedAt", ""), "place": _place(raw),
        "people": [person.get("name", "") for person in (raw.get("people") or []) if person.get("name")],
        "duration": _duration_seconds(raw) if raw.get("type") == "VIDEO" else None,
    }


async def _collect_assets(client, album_id: str, asset_ids: list[str], limit: int):
    """(title, raw assets, notes). Exactly one of album_id / asset_ids."""
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
    if not raw:
        raise ValueError("No assets found for that album/ids.")
    return title, raw, notes


async def _asset_entry(client, raw: dict, image_size: str, frames: int, interval: float,
                       notes: list[str], captions: dict) -> AssetEntry:
    exif = raw.get("exifInfo") or {}
    summary = _summary(raw)
    entry = AssetEntry(
        id=summary["id"], kind=summary["type"], filename=summary["filename"], taken_at=summary["taken_at"][:19].replace("T", " "),
        place=summary["place"], camera=" ".join(part for part in (exif.get("make"), exif.get("model")) if part),
        people=summary["people"], tags=[tag.get("name", "") for tag in (raw.get("tags") or []) if tag.get("name")],
        caption=str(captions.get(summary["id"], "")), lat=exif.get("latitude"), lon=exif.get("longitude"),
    )
    if entry.kind == "VIDEO" and (frames > 0 or interval > 0):
        try:
            data = await client.get_video_playback(entry.id)
            result = await asyncio.to_thread(video_frames.extract_frames, data, frames, "thumbnail", None, 0.0, 0.0, interval)
            if not result["frames"]:
                notes.append(f"{entry.filename}: no frames decoded; poster used")
            else:
                entry.images = [base64.b64decode(frame["data"]) for frame in result["frames"]]
                entry.timestamps = [frame["timestamp"] for frame in result["frames"]]
                return entry
        except video_frames.TooManyFrames as exc:
            notes.append(f"{entry.filename}: {exc}; poster used")
        except video_frames.NoVideoBackend as exc:
            if not any("poster" in note for note in notes):
                notes.append(f"video frames unavailable ({exc}): posters used")
        except Exception as exc:  # decode failure on one file must not kill the export
            notes.append(f"{entry.filename}: frames failed ({exc}); poster used")
    thumb = await client.get_asset_thumbnail(entry.id, image_size)
    entry.images = [base64.b64decode(thumb["data"])]
    return entry


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
    return json.dumps({"title": title, "count": len(raw), "assets": [_summary(asset) for asset in raw], "warnings": notes})

@mcp.tool()
async def export_pdf(
    ctx: Context, album_id: str = "", asset_ids: list[str] = [], output_path: str = "",
    title: str = "", captions: dict = {}, layout: str = "detail", frames_per_video: int = 4,
    frame_interval: float = 0.0, image_size: str = "preview", map: bool = False,
    limit: int = 100, return_base64: bool = False,
) -> str:
    """Build a PDF (cover, index, places, one section per asset) from an album or a
    list of assets, on the machine running this server. Immich metadata (date, place,
    camera, people, tags) is always included; pass `captions` {asset_id: text} with
    what you saw to add your analysis. Video frames go straight into the PDF and cost
    no tokens (up to 120 per video). The PDF never enters the conversation unless
    return_base64=True. Needs `pip install immich-photo-manager[pdf]`.

    Args:
        album_id: Album UUID, or asset_ids: explicit asset UUIDs (exactly one of the two).
        output_path: Where to write (default ~/Desktop/<title>.pdf). Existing files are never overwritten.
        title: Cover title (default: album name or "Immich export <date>").
        captions: {asset_id: text} written after looking at the images.
        layout: 'detail' (one asset per page, default) or 'grid' (six per page).
        frames_per_video: Frames per video, evenly spaced (0-120, default 4; 0 = poster only).
        frame_interval: One frame every N seconds instead of frames_per_video (same 120 cap).
        image_size: 'preview' (default) or 'thumbnail' for photos.
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
        return json.dumps({"error": "PDF export needs fpdf2: `pip install immich-photo-manager[pdf]`."})
    frames = max(0, min(int(frames_per_video or 0), video_frames.MAX_FRAMES))
    if layout not in ("detail", "grid"):
        layout = "detail"
    if image_size not in ("thumbnail", "preview"):
        image_size = "preview"
    title = title or album_title or f"Immich export {datetime.date.today().isoformat()}"

    entries: list[AssetEntry] = []
    skipped: list[dict] = []
    for asset in raw:
        try:
            entries.append(await _asset_entry(client, asset, image_size, frames, float(frame_interval or 0), notes, captions or {}))
        except Exception as exc:
            skipped.append({"id": asset.get("id"), "reason": str(exc)[:200]})
    if not entries:
        return json.dumps({"error": "No asset could be fetched.", "assets_skipped": skipped})

    map_png = None
    if map:
        points = [(entry.lat, entry.lon) for entry in entries if entry.lat is not None and entry.lon is not None]
        if points:
            tiles: dict = {}
            loop = asyncio.get_running_loop()

            def fetch(zoom, tile_x, tile_y):
                key = (zoom, tile_x, tile_y)
                if key not in tiles:
                    tiles[key] = asyncio.run_coroutine_threadsafe(client.fetch_tile(zoom, tile_x, tile_y), loop).result(15)
                return tiles[key]

            map_png = await asyncio.to_thread(pdf_export.render_map, points, fetch)
            if map_png is None:
                notes.append("map could not be drawn (tiles unavailable); Places table only")
        else:
            notes.append("map requested but no asset has GPS data")

    photos = sum(1 for entry in entries if entry.kind == "IMAGE")
    doc = Document(
        title=title, subtitle=f"{len(entries)} assets · {photos} photos, {len(entries) - photos} videos · exported {datetime.date.today().isoformat()}",
        source_url=client.base_url, version=__version__, layout=layout, assets=entries,
        places=pdf_export.places_table(entries), map_png=map_png,
    )
    try:
        pdf = await asyncio.to_thread(pdf_export.build, doc)
    except pdf_export.NoPdfBackend as exc:
        return json.dumps({"error": str(exc)})

    if output_path:
        path = os.path.expanduser(output_path)
        if os.path.isdir(path):
            path = os.path.join(path, f"{pdf_export.slugify(title)}.pdf")
        elif not path.lower().endswith(".pdf"):
            path = f"{path}.pdf"
    else:
        path = os.path.expanduser(f"~/Desktop/{pdf_export.slugify(title)}.pdf")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    path = pdf_export.unique_path(path)
    with open(path, "wb") as handle:
        handle.write(pdf)
    try:
        from pypdf import PdfReader
        pages = len(PdfReader(io.BytesIO(pdf)).pages)
    except Exception:  # pypdf missing or unable to parse: fall back, never break the JSON contract
        pages = pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")
    pdf_b64 = None
    if return_base64:
        if len(pdf) > 2 * 1024 * 1024:
            notes.append("PDF larger than 2 MB: base64 not returned (read it from `path`)")
        else:
            pdf_b64 = base64.b64encode(pdf).decode("ascii")
    out = {
        "path": path, "pages": pages, "bytes": len(pdf),
        "assets_included": len(entries), "assets_skipped": skipped, "warnings": notes,
    }
    if pdf_b64 is not None:
        out["pdf_base64"] = pdf_b64
    return json.dumps(out)


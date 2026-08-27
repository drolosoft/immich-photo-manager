"""Compose an A4 PDF (cover, index, places, one section per asset) with fpdf2.

Pure: takes bytes and strings, returns bytes. No HTTP, no Immich. Optional
dependency `fpdf2` (`pip install immich-photo-manager[pdf]`), which brings Pillow.
"""

from __future__ import annotations

import io
import logging
import math
import os
import re
from dataclasses import dataclass, field

# fpdf2's font subsetting (fontTools) logs "glyf pruned"/"Retaining" chatter at
# INFO level straight to stderr; this is noise for an MCP server, so silence it
# at import time regardless of the caller's root logging config.
logging.getLogger("fontTools").setLevel(logging.WARNING)
logging.getLogger("fontTools.subset").setLevel(logging.WARNING)

A4_W, A4_H, MARGIN = 210.0, 297.0, 15.0
CONTENT_W = A4_W - 2 * MARGIN
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/opt/homebrew/share/fonts/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]


class NoPdfBackend(RuntimeError):
    """fpdf2 is not installed."""


@dataclass
class AssetEntry:
    id: str
    kind: str  # "IMAGE" | "VIDEO"
    filename: str
    taken_at: str
    place: str
    camera: str
    people: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    caption: str = ""
    images: list[bytes] = field(default_factory=list)  # 1 for a photo, N frames for a video
    timestamps: list[float] = field(default_factory=list)
    lat: float | None = None
    lon: float | None = None


@dataclass
class Document:
    title: str
    subtitle: str
    source_url: str
    version: str
    layout: str = "detail"  # "detail" | "grid"
    assets: list[AssetEntry] = field(default_factory=list)
    places: list[tuple[str, str, int]] = field(default_factory=list)
    map_png: bytes | None = None


def _fpdf_available() -> bool:
    try:
        import fpdf  # noqa: F401
    except Exception:
        return False
    return True


def slugify(text: str) -> str:
    s = text.lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "immich-export"


def unique_path(path: str) -> str:
    """Never overwrite: x.pdf → x-2.pdf → x-3.pdf ..."""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{root}-{n}{ext}"):
        n += 1
    return f"{root}-{n}{ext}"


def places_table(assets: list[AssetEntry]) -> list[tuple[str, str, int]]:
    counts: dict[tuple[str, str], int] = {}
    for asset in assets:
        if not asset.place:
            continue
        parts = [part.strip() for part in asset.place.split(",")]
        city, country = (parts[0], parts[-1]) if len(parts) > 1 else ("", parts[0])
        counts[(country, city)] = counts.get((country, city), 0) + 1
    return sorted(((c, ci, n) for (c, ci), n in counts.items()), key=lambda t: (-t[2], t[0], t[1]))


class _Pdf:
    """Thin wrapper over fpdf.FPDF with a Unicode font when one is found."""

    def __init__(self, doc: Document):
        from fpdf import FPDF

        self.doc = doc
        self.pdf = FPDF(orientation="P", unit="mm", format="A4")
        self.pdf.set_auto_page_break(auto=True, margin=MARGIN)
        self.pdf.set_margins(MARGIN, MARGIN, MARGIN)
        self.unicode = False
        for path in FONT_CANDIDATES:
            if os.path.exists(path):
                self.pdf.add_font("body", "", path)
                self.family = "body"
                self.unicode = True
                break
        else:
            self.family = "helvetica"
        self.pdf.set_font(self.family, size=11)

    def text(self, s: str) -> str:
        return s if self.unicode else s.encode("latin-1", "replace").decode("latin-1")

    def font(self, size: float, bold: bool = False):
        # Bold needs a second TTF; with the unicode font we simulate emphasis by size only.
        style = "B" if (bold and not self.unicode) else ""
        self.pdf.set_font(self.family, style=style, size=size)

    def image(self, data: bytes, x: float, y: float, max_w: float, max_h: float) -> float:
        """Draw `data` fitting in max_w × max_h at (x, y); returns the drawn height."""
        from PIL import Image as PILImage

        with PILImage.open(io.BytesIO(data)) as image:
            width, height = image.size
        scale = min(max_w / width, max_h / height)
        drawn_w, drawn_h = width * scale, height * scale
        self.pdf.image(io.BytesIO(data), x=x + (max_w - drawn_w) / 2, y=y, w=drawn_w, h=drawn_h)
        return drawn_h

    def footer_all(self):
        # y = A4_H - 10 sits below the auto-page-break trigger (A4_H - MARGIN), so
        # drawing there with auto page break still enabled would make fpdf2 slide
        # the write onto the next page (or, on the last page, append a stray blank
        # page). Disable it for this final, content-free pass.
        total = self.pdf.pages_count
        self.pdf.set_auto_page_break(False)
        for page_number in range(1, total + 1):
            self.pdf.page = page_number
            self.font(8)
            self.pdf.set_xy(MARGIN, A4_H - 10)
            self.pdf.cell(
                CONTENT_W,
                5,
                self.text(f"immich-photo-manager v{self.doc.version} · {self.doc.source_url} · page {page_number}/{total}"),
                align="C",
            )


def _cover(writer: _Pdf):
    doc = writer.doc
    writer.pdf.add_page()
    writer.font(26, bold=True)
    writer.pdf.set_xy(MARGIN, 40)
    writer.pdf.multi_cell(CONTENT_W, 12, writer.text(doc.title), align="C")
    writer.font(12)
    writer.pdf.multi_cell(CONTENT_W, 7, writer.text(doc.subtitle), align="C")
    first = next((entry.images[0] for entry in doc.assets if entry.images), None)
    if first:
        writer.image(first, MARGIN, 80, CONTENT_W, 150)


def _index(writer: _Pdf) -> list:
    writer.pdf.add_page()
    writer.font(16, bold=True)
    writer.pdf.cell(CONTENT_W, 10, writer.text("Index"), new_x="LMARGIN", new_y="NEXT")
    writer.font(9)
    links = []
    for i, asset in enumerate(writer.doc.assets, 1):
        link = writer.pdf.add_link()
        links.append(link)
        line = f"{i:>3}. {asset.filename}  {asset.taken_at[:10]}  {asset.place}".rstrip()
        writer.pdf.cell(CONTENT_W, 5, writer.text(line), link=link, new_x="LMARGIN", new_y="NEXT")
    return links


def _places(writer: _Pdf):
    writer.pdf.add_page()
    writer.font(16, bold=True)
    writer.pdf.cell(CONTENT_W, 10, writer.text("Places"), new_x="LMARGIN", new_y="NEXT")
    writer.font(10)
    if not writer.doc.places:
        writer.pdf.cell(CONTENT_W, 6, writer.text("No location data in these assets."), new_x="LMARGIN", new_y="NEXT")
    for country, city, n in writer.doc.places:
        writer.pdf.cell(60, 6, writer.text(country))
        writer.pdf.cell(80, 6, writer.text(city))
        writer.pdf.cell(20, 6, str(n), align="R", new_x="LMARGIN", new_y="NEXT")
    if writer.doc.map_png:
        y = writer.pdf.get_y() + 6
        max_h = A4_H - y - 20
        if max_h < 60:
            writer.pdf.add_page()
            y = MARGIN
            max_h = A4_H - y - 20
        writer.image(writer.doc.map_png, MARGIN, y, CONTENT_W, max_h)


def _meta_lines(asset: AssetEntry) -> list[str]:
    lines = [asset.filename, f"Taken: {asset.taken_at}" if asset.taken_at else ""]
    if asset.place:
        lines.append(f"Place: {asset.place}")
    if asset.camera:
        lines.append(f"Camera: {asset.camera}")
    if asset.people:
        lines.append("People: " + ", ".join(asset.people))
    if asset.tags:
        lines.append("Tags: " + ", ".join(asset.tags))
    return [line for line in lines if line]


def _detail(writer: _Pdf, asset: AssetEntry, link):
    writer.pdf.add_page()
    writer.pdf.set_link(link, page=writer.pdf.page)
    y = MARGIN
    if asset.kind == "VIDEO" and len(asset.images) > 1:
        cols, gap = 4, 3
        w = (CONTENT_W - gap * (cols - 1)) / cols
        for i, img in enumerate(asset.images):
            col = i % cols
            if col == 0 and i > 0:
                y += w * 0.6 + 8
                if y + w * 0.6 + 40 > A4_H - MARGIN:
                    writer.pdf.add_page()
                    y = MARGIN
            x = MARGIN + col * (w + gap)
            writer.image(img, x, y, w, w * 0.6)
            writer.font(7)
            ts = asset.timestamps[i] if i < len(asset.timestamps) else 0.0
            writer.pdf.set_xy(x, y + w * 0.6 + 1)
            writer.pdf.cell(w, 4, f"{ts:.1f} s", align="C")
        y += w * 0.6 + 10
    elif asset.images:
        y += writer.image(asset.images[0], MARGIN, y, CONTENT_W, 150) + 4
    writer.pdf.set_xy(MARGIN, y)
    writer.font(10)
    for line in _meta_lines(asset):
        writer.pdf.cell(CONTENT_W, 5.5, writer.text(line), new_x="LMARGIN", new_y="NEXT")
    if asset.caption:
        writer.pdf.ln(2)
        writer.font(11)
        writer.pdf.multi_cell(CONTENT_W, 6, writer.text(asset.caption))


def _grid(writer: _Pdf, assets: list[AssetEntry], links: list):
    cols, rows, gap = 2, 3, 6
    cell_w = (CONTENT_W - gap) / cols
    cell_h = (A4_H - 2 * MARGIN - 10 - gap * (rows - 1)) / rows
    for i, asset in enumerate(assets):
        slot = i % (cols * rows)
        if slot == 0:
            writer.pdf.add_page()
        writer.pdf.set_link(links[i], page=writer.pdf.page)
        x = MARGIN + (slot % cols) * (cell_w + gap)
        y = MARGIN + (slot // cols) * (cell_h + gap)
        if asset.images:
            writer.image(asset.images[0], x, y, cell_w, cell_h - 14)
        writer.font(8)
        writer.pdf.set_xy(x, y + cell_h - 13)
        note = f" · {len(asset.images)} frames" if asset.kind == "VIDEO" else ""
        writer.pdf.cell(cell_w, 4, writer.text(f"{asset.filename}  {asset.taken_at[:10]}{note}"), new_x="LEFT", new_y="NEXT")
        writer.pdf.set_x(x)
        writer.pdf.cell(cell_w, 4, writer.text(asset.caption[:90]))


def build(doc: Document) -> bytes:
    """Compose the PDF and return its bytes. Raises NoPdfBackend when fpdf2 is missing."""
    if not _fpdf_available():
        raise NoPdfBackend(
            "PDF export needs fpdf2: install the optional extra `pip install immich-photo-manager[pdf]`."
        )
    writer = _Pdf(doc)
    _cover(writer)
    links = _index(writer)
    _places(writer)
    if doc.layout == "grid":
        _grid(writer, doc.assets, links)
    else:
        for asset, link in zip(doc.assets, links):
            _detail(writer, asset, link)
    writer.footer_all()
    return bytes(writer.pdf.output())


MAX_TILES = 16
TILE = 256


def _tile_xy(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def render_map(points: list[tuple[float, float]], fetch_tile) -> bytes | None:
    """Stitch OSM tiles around `points` (≤ MAX_TILES) and draw a dot per point. None on failure."""
    if not points:
        return None
    try:
        from PIL import Image as PILImage, ImageDraw

        lats = [lat for lat, _lon in points]
        lons = [lon for _lat, lon in points]
        for zoom in range(12, 0, -1):
            x0, y1 = _tile_xy(min(lats), min(lons), zoom)
            x1, y0 = _tile_xy(max(lats), max(lons), zoom)
            tx0, tx1 = int(math.floor(x0)), int(math.floor(x1))
            ty0, ty1 = int(math.floor(y0)), int(math.floor(y1))
            tx0, tx1 = sorted((tx0, tx1))
            ty0, ty1 = sorted((ty0, ty1))
            if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) <= MAX_TILES:
                break
        cols, rows = tx1 - tx0 + 1, ty1 - ty0 + 1
        canvas = PILImage.new("RGB", (cols * TILE, rows * TILE), "white")
        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                tile = PILImage.open(io.BytesIO(fetch_tile(zoom, tx, ty))).convert("RGB")
                canvas.paste(tile, ((tx - tx0) * TILE, (ty - ty0) * TILE))
        draw = ImageDraw.Draw(canvas)
        for lat, lon in points:
            x, y = _tile_xy(lat, lon, zoom)
            px, py = (x - tx0) * TILE, (y - ty0) * TILE
            draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill="#d33", outline="white", width=2)
        out = io.BytesIO()
        canvas.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return None

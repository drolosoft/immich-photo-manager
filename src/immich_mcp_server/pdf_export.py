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
    for a in assets:
        if not a.place:
            continue
        parts = [p.strip() for p in a.place.split(",")]
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

        with PILImage.open(io.BytesIO(data)) as im:
            w, h = im.size
        scale = min(max_w / w, max_h / h)
        dw, dh = w * scale, h * scale
        self.pdf.image(io.BytesIO(data), x=x + (max_w - dw) / 2, y=y, w=dw, h=dh)
        return dh

    def footer_all(self):
        # y = A4_H - 10 sits below the auto-page-break trigger (A4_H - MARGIN), so
        # drawing there with auto page break still enabled would make fpdf2 slide
        # the write onto the next page (or, on the last page, append a stray blank
        # page). Disable it for this final, content-free pass.
        total = self.pdf.pages_count
        self.pdf.set_auto_page_break(False)
        for n in range(1, total + 1):
            self.pdf.page = n
            self.font(8)
            self.pdf.set_xy(MARGIN, A4_H - 10)
            self.pdf.cell(
                CONTENT_W,
                5,
                self.text(f"immich-photo-manager v{self.doc.version} · {self.doc.source_url} · page {n}/{total}"),
                align="C",
            )


def _cover(p: _Pdf):
    d = p.doc
    p.pdf.add_page()
    p.font(26, bold=True)
    p.pdf.set_xy(MARGIN, 40)
    p.pdf.multi_cell(CONTENT_W, 12, p.text(d.title), align="C")
    p.font(12)
    p.pdf.multi_cell(CONTENT_W, 7, p.text(d.subtitle), align="C")
    first = next((a.images[0] for a in d.assets if a.images), None)
    if first:
        p.image(first, MARGIN, 80, CONTENT_W, 150)


def _index(p: _Pdf) -> list:
    p.pdf.add_page()
    p.font(16, bold=True)
    p.pdf.cell(CONTENT_W, 10, p.text("Index"), new_x="LMARGIN", new_y="NEXT")
    p.font(9)
    links = []
    for i, a in enumerate(p.doc.assets, 1):
        link = p.pdf.add_link()
        links.append(link)
        line = f"{i:>3}. {a.filename}  {a.taken_at[:10]}  {a.place}".rstrip()
        p.pdf.cell(CONTENT_W, 5, p.text(line), link=link, new_x="LMARGIN", new_y="NEXT")
    return links


def _places(p: _Pdf):
    p.pdf.add_page()
    p.font(16, bold=True)
    p.pdf.cell(CONTENT_W, 10, p.text("Places"), new_x="LMARGIN", new_y="NEXT")
    p.font(10)
    if not p.doc.places:
        p.pdf.cell(CONTENT_W, 6, p.text("No location data in these assets."), new_x="LMARGIN", new_y="NEXT")
    for country, city, n in p.doc.places:
        p.pdf.cell(60, 6, p.text(country))
        p.pdf.cell(80, 6, p.text(city))
        p.pdf.cell(20, 6, str(n), align="R", new_x="LMARGIN", new_y="NEXT")
    if p.doc.map_png:
        y = p.pdf.get_y() + 6
        p.image(p.doc.map_png, MARGIN, y, CONTENT_W, A4_H - y - 20)


def _meta_lines(a: AssetEntry) -> list[str]:
    lines = [a.filename, f"Taken: {a.taken_at}" if a.taken_at else ""]
    if a.place:
        lines.append(f"Place: {a.place}")
    if a.camera:
        lines.append(f"Camera: {a.camera}")
    if a.people:
        lines.append("People: " + ", ".join(a.people))
    if a.tags:
        lines.append("Tags: " + ", ".join(a.tags))
    return [line for line in lines if line]


def _detail(p: _Pdf, a: AssetEntry, link):
    p.pdf.add_page()
    p.pdf.set_link(link, page=p.pdf.page)
    y = MARGIN
    if a.kind == "VIDEO" and len(a.images) > 1:
        cols, gap = 4, 3
        w = (CONTENT_W - gap * (cols - 1)) / cols
        for i, img in enumerate(a.images):
            col = i % cols
            if col == 0 and i > 0:
                y += w * 0.6 + 8
                if y + w * 0.6 + 40 > A4_H - MARGIN:
                    p.pdf.add_page()
                    y = MARGIN
            x = MARGIN + col * (w + gap)
            p.image(img, x, y, w, w * 0.6)
            p.font(7)
            ts = a.timestamps[i] if i < len(a.timestamps) else 0.0
            p.pdf.set_xy(x, y + w * 0.6 + 1)
            p.pdf.cell(w, 4, f"{ts:.1f} s", align="C")
        y += w * 0.6 + 10
    elif a.images:
        y += p.image(a.images[0], MARGIN, y, CONTENT_W, 150) + 4
    p.pdf.set_xy(MARGIN, y)
    p.font(10)
    for line in _meta_lines(a):
        p.pdf.cell(CONTENT_W, 5.5, p.text(line), new_x="LMARGIN", new_y="NEXT")
    if a.caption:
        p.pdf.ln(2)
        p.font(11)
        p.pdf.multi_cell(CONTENT_W, 6, p.text(a.caption))


def _grid(p: _Pdf, assets: list[AssetEntry], links: list):
    cols, rows, gap = 2, 3, 6
    cell_w = (CONTENT_W - gap) / cols
    cell_h = (A4_H - 2 * MARGIN - 10 - gap * (rows - 1)) / rows
    for i, a in enumerate(assets):
        slot = i % (cols * rows)
        if slot == 0:
            p.pdf.add_page()
        p.pdf.set_link(links[i], page=p.pdf.page)
        x = MARGIN + (slot % cols) * (cell_w + gap)
        y = MARGIN + (slot // cols) * (cell_h + gap)
        if a.images:
            p.image(a.images[0], x, y, cell_w, cell_h - 14)
        p.font(8)
        p.pdf.set_xy(x, y + cell_h - 13)
        note = f" · {len(a.images)} frames" if a.kind == "VIDEO" else ""
        p.pdf.cell(cell_w, 4, p.text(f"{a.filename}  {a.taken_at[:10]}{note}"), new_x="LEFT", new_y="NEXT")
        p.pdf.set_x(x)
        p.pdf.cell(cell_w, 4, p.text(a.caption[:90]))


def build(doc: Document) -> bytes:
    """Compose the PDF and return its bytes. Raises NoPdfBackend when fpdf2 is missing."""
    if not _fpdf_available():
        raise NoPdfBackend(
            "PDF export needs fpdf2: install the optional extra `pip install immich-photo-manager[pdf]`."
        )
    p = _Pdf(doc)
    _cover(p)
    links = _index(p)
    _places(p)
    if doc.layout == "grid":
        _grid(p, doc.assets, links)
    else:
        for a, link in zip(doc.assets, links):
            _detail(p, a, link)
    p.footer_all()
    return bytes(p.pdf.output())


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

        lats = [p[0] for p in points]
        lons = [p[1] for p in points]
        for z in range(12, 0, -1):
            x0, y1 = _tile_xy(min(lats), min(lons), z)
            x1, y0 = _tile_xy(max(lats), max(lons), z)
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
                tile = PILImage.open(io.BytesIO(fetch_tile(z, tx, ty))).convert("RGB")
                canvas.paste(tile, ((tx - tx0) * TILE, (ty - ty0) * TILE))
        draw = ImageDraw.Draw(canvas)
        for lat, lon in points:
            x, y = _tile_xy(lat, lon, z)
            px, py = (x - tx0) * TILE, (y - ty0) * TILE
            draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill="#d33", outline="white", width=2)
        out = io.BytesIO()
        canvas.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return None

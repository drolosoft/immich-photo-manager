"""Compose an A4 PDF (cover, index, places, one section per asset) with fpdf2.

Pure: takes bytes and strings, returns bytes. No HTTP, no Immich. The caller
(`tools/export.py`) fetches images and frames and fills a `Document`; this
module only lays it out. Needs `fpdf2` (a dependency of the package since 1.7.1),
which brings Pillow along.
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

# Page geometry in millimetres (fpdf2's default unit).
A4_W, A4_H, MARGIN = 210.0, 297.0, 15.0
CONTENT_W = A4_W - 2 * MARGIN

# Height of the footer band reserved at the bottom of every page.
FOOTER_H = 10.0

# Video frames in a detail page: four per row, this many mm between them, and
# a landscape 5:3 box per frame (thumbnails are 250 px wide).
FRAME_COLS = 4
FRAME_GAP = 3.0
FRAME_ASPECT = 0.6

# Grid layout: two columns by three rows per page.
GRID_COLS = 2
GRID_ROWS = 3
GRID_GAP = 6.0

# The core PDF fonts are Latin-1 only. When one of these TTFs exists the text
# keeps its accents and symbols; otherwise characters outside Latin-1 become "?".
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/opt/homebrew/share/fonts/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]

# OpenStreetMap asks for polite volumes; 16 tiles (up to 4 x 4) is one screen
# of map and plenty for a places overview. Tiles are 256 px squares.
MAX_TILES = 16
TILE = 256
MAP_MAX_ZOOM = 12
DOT_RADIUS = 6


# The fixed words printed on the pages. Captions come from the model in the
# conversation's language already; these are the plugin's own labels.
LABELS = {
    "en": {
        "index": "Index", "places": "Places", "no_location": "No location data in these assets.",
        "taken": "Taken", "place": "Place", "camera": "Camera", "people": "People", "tags": "Tags",
        "page": "page",
    },
    "es": {
        "index": "Índice", "places": "Lugares", "no_location": "Estos elementos no llevan localización.",
        "taken": "Fecha", "place": "Lugar", "camera": "Cámara", "people": "Personas", "tags": "Etiquetas",
        "page": "página",
    },
}


class NoPdfBackend(RuntimeError):
    """fpdf2 is not installed."""


@dataclass
class AssetEntry:
    """One photo or video as it appears in the PDF: metadata plus its images."""

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
    timestamps: list[float] = field(default_factory=list)  # one per frame, seconds
    frame_captions: list[str] = field(default_factory=list)  # photobook: one caption per frame
    lat: float | None = None
    lon: float | None = None


@dataclass
class Document:
    """Everything `build` needs: the cover text, the assets, the places table and the map."""

    title: str
    subtitle: str
    source_url: str
    version: str
    layout: str = "detail"  # "detail" | "grid" | "photobook"
    language: str = "en"  # labels on the pages; "en" or "es", unknown falls back to "en"
    assets: list[AssetEntry] = field(default_factory=list)
    places: list[tuple[str, str, int]] = field(default_factory=list)
    map_png: bytes | None = None
    # Front matter is on by default; a photobook meant for printing may want none of it.
    with_cover: bool = True
    with_index: bool = True
    with_places: bool = True
    # "full" (plugin, server and page number), "pages" (page number only) or "none".
    footer: str = "full"
    # Repeat the title at the top of every page but the cover; off by default.
    with_header: bool = False


def _fpdf_available() -> bool:
    """True when fpdf2 can be imported (a dependency, but a broken install must not crash the server)."""
    try:
        import fpdf  # noqa: F401
    except Exception:
        return False
    return True


def slugify(text: str) -> str:
    """A filename-safe version of a title: lowercase, words joined by dashes."""
    slug = text.lower().replace("'", "")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or "immich-export"


def unique_path(path: str) -> str:
    """Never overwrite: x.pdf → x-2.pdf → x-3.pdf ..."""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    suffix = 2
    while os.path.exists(f"{root}-{suffix}{ext}"):
        suffix += 1
    return f"{root}-{suffix}{ext}"


def places_table(assets: list[AssetEntry]) -> list[tuple[str, str, int]]:
    """(country, city, count) rows for the Places page, most photographed first."""
    counts: dict[tuple[str, str], int] = {}
    for asset in assets:
        if not asset.place:
            continue
        parts = [part.strip() for part in asset.place.split(",")]
        city, country = (parts[0], parts[-1]) if len(parts) > 1 else ("", parts[0])
        counts[(country, city)] = counts.get((country, city), 0) + 1
    rows = [(country, city, total) for (country, city), total in counts.items()]
    rows.sort(key=_places_sort_key)
    return rows


def _places_sort_key(row: tuple[str, str, int]) -> tuple[int, str, str]:
    """Most photographed place first; ties fall back to alphabetical country, then city."""
    country, city, total = row
    return (-total, country, city)


class _Pdf:
    """Thin wrapper over fpdf.FPDF with a Unicode font when one is found."""

    def __init__(self, doc: Document):
        """Open an A4 portrait document and pick the first Unicode font that exists on this machine."""
        from fpdf import FPDF

        self.doc = doc
        self.labels = LABELS.get(getattr(doc, "language", "en"), LABELS["en"])
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

    def text(self, value: str) -> str:
        """`value` as the current font can print it (Latin-1 with replacement when no TTF)."""
        if self.unicode:
            return value
        return value.encode("latin-1", "replace").decode("latin-1")

    def font(self, size: float, bold: bool = False):
        """Select the body font at `size`; bold only exists for the core font."""
        # A bold TTF would be a second file to ship; with the Unicode font the
        # headings stand out by size alone.
        style = "B" if (bold and not self.unicode) else ""
        self.pdf.set_font(self.family, style=style, size=size)

    def image(self, data: bytes, left: float, top: float, max_w: float, max_h: float) -> float:
        """Draw `data` centred in a max_w x max_h box at (left, top); returns the drawn height."""
        from PIL import Image as PILImage

        with PILImage.open(io.BytesIO(data)) as image:
            width, height = image.size
        scale = min(max_w / width, max_h / height)
        drawn_w, drawn_h = width * scale, height * scale
        self.pdf.image(io.BytesIO(data), x=left + (max_w - drawn_w) / 2, y=top, w=drawn_w, h=drawn_h)
        return drawn_h

    def decorate_pages(self):
        """The final pass over every page: the footer (by mode) and the optional title header.

        The footer sits below the auto-page-break trigger (A4_H - MARGIN), so
        writing there with auto page break enabled would make fpdf2 slide the
        text onto the next page and append a blank page at the end. This pass
        runs after all content exists, so the break can be switched off.
        """
        total = self.pdf.pages_count
        self.pdf.set_auto_page_break(False)
        for page_number in range(1, total + 1):
            self.pdf.page = page_number
            self.font(8)
            if self.doc.footer == "pages":
                footer = f"{self.labels['page']} {page_number}/{total}"
            elif self.doc.footer == "full":
                footer = (f"immich-photo-manager v{self.doc.version} · {self.doc.source_url}"
                          f" · {self.labels['page']} {page_number}/{total}")
            else:
                footer = ""
            if footer:
                self.pdf.set_xy(MARGIN, A4_H - FOOTER_H)
                self.pdf.cell(CONTENT_W, 5, self.text(footer), align="C")
            # The cover already carries the title large; every other page can
            # repeat it small at the top when the header is on.
            on_cover = self.doc.with_cover and page_number == 1
            if self.doc.with_header and not on_cover:
                self.pdf.set_xy(MARGIN, 6)
                self.pdf.cell(CONTENT_W, 5, self.text(self.doc.title), align="C")


def _cover(writer: _Pdf):
    """Title, subtitle and the first image as the cover picture."""
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
    """One line per asset; returns the links so the asset pages can register themselves."""
    writer.pdf.add_page()
    writer.font(16, bold=True)
    writer.pdf.cell(CONTENT_W, 10, writer.text(writer.labels["index"]), new_x="LMARGIN", new_y="NEXT")
    writer.font(9)
    links = []
    for position, asset in enumerate(writer.doc.assets, 1):
        link = writer.pdf.add_link()
        links.append(link)
        line = f"{position:>3}. {asset.filename}  {asset.taken_at[:10]}  {asset.place}".rstrip()
        writer.pdf.cell(CONTENT_W, 5, writer.text(line), link=link, new_x="LMARGIN", new_y="NEXT")
    return links


def _places(writer: _Pdf):
    """The country / city / count table, with the map below it when there is one."""
    writer.pdf.add_page()
    writer.font(16, bold=True)
    writer.pdf.cell(CONTENT_W, 10, writer.text(writer.labels["places"]), new_x="LMARGIN", new_y="NEXT")
    writer.font(10)
    if not writer.doc.places:
        writer.pdf.cell(CONTENT_W, 6, writer.text(writer.labels["no_location"]), new_x="LMARGIN", new_y="NEXT")
    for country, city, total in writer.doc.places:
        writer.pdf.cell(60, 6, writer.text(country))
        writer.pdf.cell(80, 6, writer.text(city))
        writer.pdf.cell(20, 6, str(total), align="R", new_x="LMARGIN", new_y="NEXT")
    if not writer.doc.map_png:
        return
    # A long table can leave too little room under it; the map then gets its
    # own page rather than a sliver at the bottom.
    top = writer.pdf.get_y() + 6
    max_h = A4_H - top - 2 * FOOTER_H
    if max_h < 60:
        writer.pdf.add_page()
        top = MARGIN
        max_h = A4_H - top - 2 * FOOTER_H
    writer.image(writer.doc.map_png, MARGIN, top, CONTENT_W, max_h)


def _meta_lines(asset: AssetEntry, labels: dict) -> list[str]:
    """The metadata block under an asset, one line per known field."""
    lines = [asset.filename, f"{labels['taken']}: {asset.taken_at}" if asset.taken_at else ""]
    if asset.place:
        lines.append(f"{labels['place']}: {asset.place}")
    if asset.camera:
        lines.append(f"{labels['camera']}: {asset.camera}")
    if asset.people:
        lines.append(f"{labels['people']}: " + ", ".join(asset.people))
    if asset.tags:
        lines.append(f"{labels['tags']}: " + ", ".join(asset.tags))
    return [line for line in lines if line]


def _frame_strip(writer: _Pdf, asset: AssetEntry, top: float) -> float:
    """Draw a video's frames four per row with the timestamp under each; returns the new top."""
    cell_w = (CONTENT_W - FRAME_GAP * (FRAME_COLS - 1)) / FRAME_COLS
    cell_h = cell_w * FRAME_ASPECT
    row_h = cell_h + 8
    for position, image in enumerate(asset.images):
        col = position % FRAME_COLS
        if col == 0 and position > 0:
            top += row_h
            # Keep room for the row plus the metadata block; else start a page.
            if top + cell_h + 40 > A4_H - MARGIN:
                writer.pdf.add_page()
                top = MARGIN
        left = MARGIN + col * (cell_w + FRAME_GAP)
        writer.image(image, left, top, cell_w, cell_h)
        writer.font(7)
        timestamp = asset.timestamps[position] if position < len(asset.timestamps) else 0.0
        writer.pdf.set_xy(left, top + cell_h + 1)
        writer.pdf.cell(cell_w, 4, f"{timestamp:.1f} s", align="C")
    return top + cell_h + 10


def _detail(writer: _Pdf, asset: AssetEntry, link):
    """One page per asset: the image (or the frame strip), the metadata, the caption."""
    writer.pdf.add_page()
    writer.pdf.set_link(link, page=writer.pdf.page)
    top = MARGIN
    if asset.kind == "VIDEO" and len(asset.images) > 1:
        top = _frame_strip(writer, asset, top)
    elif asset.images:
        top += writer.image(asset.images[0], MARGIN, top, CONTENT_W, 150) + 4
    writer.pdf.set_xy(MARGIN, top)
    writer.font(10)
    for line in _meta_lines(asset, writer.labels):
        writer.pdf.cell(CONTENT_W, 5.5, writer.text(line), new_x="LMARGIN", new_y="NEXT")
    if asset.caption:
        writer.pdf.ln(2)
        writer.font(11)
        writer.pdf.multi_cell(CONTENT_W, 6, writer.text(asset.caption))



def _photobook_page(writer: _Pdf, image: bytes, header: str, caption: str, link):
    """One full page: the image as large as it fits, a small metadata line, the caption.

    The image is fitted, never cropped (letterbox/pillarbox), so nothing at the
    edges is lost; a photobook of cars must not cut off wheels or plates.
    """
    writer.pdf.add_page()
    # Only the asset's first page is an index target; frame pages pass link=None.
    if link is not None:
        writer.pdf.set_link(link, page=writer.pdf.page)
    caption_space = 34.0
    image_height = A4_H - 2 * MARGIN - caption_space
    drawn = 0.0
    offset = 0.0
    if image:
        # A width-bound (landscape) image is much shorter than the area; centre
        # it vertically instead of gluing it to the top with a white gap below.
        import io as io_module

        from PIL import Image as PILImage

        with PILImage.open(io_module.BytesIO(image)) as measured:
            width, height = measured.size
        scale = min(CONTENT_W / width, image_height / height)
        offset = max(0.0, (image_height - height * scale) / 2)
        drawn = writer.image(image, MARGIN, MARGIN + offset, CONTENT_W, image_height)
    top = MARGIN + offset + min(drawn, image_height) + 4
    writer.pdf.set_xy(MARGIN, top)
    writer.font(8)
    writer.pdf.cell(CONTENT_W, 4, writer.text(header), new_x="LMARGIN", new_y="NEXT")
    if caption:
        writer.font(11)
        writer.pdf.multi_cell(CONTENT_W, 6, writer.text(caption))


def _photobook(writer: _Pdf, asset: AssetEntry, link):
    """One asset per page — except a video with several chosen frames, which unfolds
    into one full page per frame, each with its timestamp and (optionally) its own
    caption. That is what #15 asked for: full frames like photos, not a thumbnail strip.
    """
    base_header = "  ·  ".join(part for part in (asset.filename, asset.taken_at[:10], asset.place) if part)
    if asset.kind == "VIDEO" and len(asset.images) > 1:
        for position, frame in enumerate(asset.images):
            timestamp = asset.timestamps[position] if position < len(asset.timestamps) else 0.0
            header = f"{base_header}  ·  {timestamp:.1f} s"
            if position < len(asset.frame_captions):
                # Per-frame captions replace the asset caption entirely.
                caption = asset.frame_captions[position]
            else:
                # Without per-frame captions the asset caption opens the sequence once.
                caption = asset.caption if position == 0 else ""
            _photobook_page(writer, frame, header, caption, link if position == 0 else None)
        return
    first_image = asset.images[0] if asset.images else b""
    _photobook_page(writer, first_image, base_header, asset.caption, link)


def _grid(writer: _Pdf, assets: list[AssetEntry], links: list):
    """Six assets per page: a thumbnail, the filename and date, the caption's first line."""
    per_page = GRID_COLS * GRID_ROWS
    cell_w = (CONTENT_W - GRID_GAP) / GRID_COLS
    cell_h = (A4_H - 2 * MARGIN - FOOTER_H - GRID_GAP * (GRID_ROWS - 1)) / GRID_ROWS
    for position, asset in enumerate(assets):
        slot = position % per_page
        if slot == 0:
            writer.pdf.add_page()
        writer.pdf.set_link(links[position], page=writer.pdf.page)
        left = MARGIN + (slot % GRID_COLS) * (cell_w + GRID_GAP)
        top = MARGIN + (slot // GRID_COLS) * (cell_h + GRID_GAP)
        if asset.images:
            writer.image(asset.images[0], left, top, cell_w, cell_h - 14)
        writer.font(8)
        writer.pdf.set_xy(left, top + cell_h - 13)
        note = f" · {len(asset.images)} frames" if asset.kind == "VIDEO" else ""
        writer.pdf.cell(cell_w, 4, writer.text(f"{asset.filename}  {asset.taken_at[:10]}{note}"), new_x="LEFT", new_y="NEXT")
        writer.pdf.set_x(left)
        writer.pdf.cell(cell_w, 4, writer.text(asset.caption[:90]))


def build(doc: Document) -> bytes:
    """Compose the PDF and return its bytes. Raises NoPdfBackend when fpdf2 is missing."""
    if not _fpdf_available():
        raise NoPdfBackend(
            "PDF export needs fpdf2: `pip install fpdf2` (it ships with immich-photo-manager since 1.7.1)."
        )
    writer = _Pdf(doc)
    if doc.with_cover:
        _cover(writer)
    # Without an index page there is nothing to click, but the asset pages still
    # expect one link each, so dangling links stand in for the real ones.
    links = _index(writer) if doc.with_index else [writer.pdf.add_link() for _ in doc.assets]
    if doc.with_places:
        _places(writer)
    if doc.layout == "grid":
        _grid(writer, doc.assets, links)
    elif doc.layout == "photobook":
        for asset, link in zip(doc.assets, links):
            _photobook(writer, asset, link)
    else:
        for asset, link in zip(doc.assets, links):
            _detail(writer, asset, link)
    writer.decorate_pages()
    return bytes(writer.pdf.output())


def _tile_xy(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Fractional slippy-map tile coordinates of a point (Web Mercator, OSM convention)."""
    tiles_per_side = 2 ** zoom
    tile_x = (lon + 180.0) / 360.0 * tiles_per_side
    latitude = math.radians(lat)
    tile_y = (1 - math.log(math.tan(latitude) + 1 / math.cos(latitude)) / math.pi) / 2 * tiles_per_side
    return tile_x, tile_y


def _tile_bounds(points: list[tuple[float, float]]) -> tuple[int, int, int, int, int]:
    """(zoom, first_col, last_col, first_row, last_row): the tightest zoom whose grid fits in MAX_TILES."""
    lats = [lat for lat, _lon in points]
    lons = [lon for _lat, lon in points]
    for zoom in range(MAP_MAX_ZOOM, 0, -1):
        # Tile rows grow southwards, so the south-west corner has the larger row.
        west_x, south_y = _tile_xy(min(lats), min(lons), zoom)
        east_x, north_y = _tile_xy(max(lats), max(lons), zoom)
        first_col, last_col = sorted((int(math.floor(west_x)), int(math.floor(east_x))))
        first_row, last_row = sorted((int(math.floor(north_y)), int(math.floor(south_y))))
        # One tile of margin on every side, so the crop in render_map can put
        # the points at the centre of the image instead of wherever they fall
        # inside their own tile (a single point near a tile corner used to end
        # up in the corner of the map).
        tiles_per_side = 2 ** zoom
        first_col, last_col = max(0, first_col - 1), min(tiles_per_side - 1, last_col + 1)
        first_row, last_row = max(0, first_row - 1), min(tiles_per_side - 1, last_row + 1)
        if (last_col - first_col + 1) * (last_row - first_row + 1) <= MAX_TILES:
            return zoom, first_col, last_col, first_row, last_row
    # Zoom 1 is four tiles for the whole world, which always fits.
    return 1, 0, 1, 0, 1


def render_map(points: list[tuple[float, float]], fetch_tile) -> bytes | None:
    """Stitch OSM tiles around `points` (at most MAX_TILES) and draw a dot per point.

    `fetch_tile(zoom, col, row)` returns the PNG bytes of one tile; it is a plain
    callable so tests can inject fake tiles. Returns None on any failure (no
    network, a bad tile): the caller keeps the places table and adds a note.
    """
    if not points:
        return None
    try:
        from PIL import Image as PILImage, ImageDraw

        zoom, first_col, last_col, first_row, last_row = _tile_bounds(points)
        cols, rows = last_col - first_col + 1, last_row - first_row + 1
        canvas = PILImage.new("RGB", (cols * TILE, rows * TILE), "white")
        for tile_col in range(first_col, last_col + 1):
            for tile_row in range(first_row, last_row + 1):
                tile = PILImage.open(io.BytesIO(fetch_tile(zoom, tile_col, tile_row))).convert("RGB")
                canvas.paste(tile, ((tile_col - first_col) * TILE, (tile_row - first_row) * TILE))
        draw = ImageDraw.Draw(canvas)
        for lat, lon in points:
            tile_x, tile_y = _tile_xy(lat, lon, zoom)
            pixel_x, pixel_y = (tile_x - first_col) * TILE, (tile_y - first_row) * TILE
            draw.ellipse(
                [pixel_x - DOT_RADIUS, pixel_y - DOT_RADIUS, pixel_x + DOT_RADIUS, pixel_y + DOT_RADIUS],
                fill="#d33", outline="white", width=2,
            )
        # Crop symmetrically around the points' centre so it lands in the middle
        # of the final image; the tile margin guarantees room on every side.
        centres = [_tile_xy(lat, lon, zoom) for lat, lon in points]
        centre_x = (sum(x for x, _y in centres) / len(centres) - first_col) * TILE
        centre_y = (sum(y for _x, y in centres) / len(centres) - first_row) * TILE
        half_w = min(centre_x, canvas.width - centre_x)
        half_h = min(centre_y, canvas.height - centre_y)
        if half_w >= TILE / 2 and half_h >= TILE / 2:
            canvas = canvas.crop((int(centre_x - half_w), int(centre_y - half_h),
                                  int(centre_x + half_w), int(centre_y + half_h)))
        out = io.BytesIO()
        canvas.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        logging.getLogger(__name__).debug("places map could not be rendered", exc_info=True)
        return None

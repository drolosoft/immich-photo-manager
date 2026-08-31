"""pdf_export.build composes a valid PDF from in-memory images; no Immich, no network."""

import io

import pytest
from pypdf import PdfReader

from immich_mcp_server import pdf_export
from immich_mcp_server.pdf_export import AssetEntry, Document


def _png(color):
    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (64, 40), color).save(buf, format="PNG")
    return buf.getvalue()


def _doc(layout="detail", photo_count=3, with_video=True):
    assets = [
        AssetEntry(
            id=f"a{i}",
            kind="IMAGE",
            filename=f"{i}.jpg",
            taken_at="2026-01-0%d" % (i + 1),
            place="Barcelona, Spain",
            camera="Apple iPhone",
            people=["Curie"],
            tags=["trip"],
            caption=f"Caption {i} ñ",
            images=[_png("red")],
            timestamps=[],
            lat=41.4,
            lon=2.2,
        )
        for i in range(photo_count)
    ]
    if with_video:
        assets.append(
            AssetEntry(
                id="v1",
                kind="VIDEO",
                filename="clip.mp4",
                taken_at="2026-01-09",
                place="",
                camera="",
                people=[],
                tags=[],
                caption="A video",
                images=[_png("blue")] * 6,
                timestamps=[0.5, 1.5, 2.5, 3.5, 4.5, 5.5],
                lat=None,
                lon=None,
            )
        )
    return Document(
        title="Lab Album",
        subtitle="4 assets",
        source_url="http://immich",
        version="1.7.0",
        layout=layout,
        assets=assets,
        places=[("Spain", "Barcelona", 3)],
        map_png=None,
    )


def test_build_detail_pages_and_text():
    pdf = pdf_export.build(_doc())
    assert pdf[:4] == b"%PDF"
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == 3 + 4  # cover, index, places, 4 assets
    assert "Lab Album" in reader.pages[0].extract_text()
    assert "clip.mp4" in reader.pages[1].extract_text()
    assert "Barcelona" in reader.pages[2].extract_text()
    assert "Caption 0" in reader.pages[3].extract_text()
    assert "0.5" in reader.pages[6].extract_text()  # video timestamps


def test_index_links_point_to_pages():
    reader = PdfReader(io.BytesIO(pdf_export.build(_doc())))
    annots = reader.pages[1].get("/Annots") or []
    assert len(annots) == 4


def test_build_grid_six_per_page():
    reader = PdfReader(io.BytesIO(pdf_export.build(_doc(layout="grid", photo_count=13, with_video=False))))
    assert len(reader.pages) == 3 + 3  # 13 assets → 6+6+1


def test_build_with_map_adds_image_on_places_page():
    doc = _doc()
    doc.map_png = _png("green")
    reader = PdfReader(io.BytesIO(pdf_export.build(doc)))
    assert len(reader.pages[2].images) >= 1


def _many_places_doc(with_map: bool) -> Document:
    """60 distinct places push the Places table past one page via fpdf2's auto
    page break, leaving little or no room for the map on whichever page the
    table ends up on."""
    assets = [
        AssetEntry(
            id=f"a{i}", kind="IMAGE", filename=f"{i}.jpg", taken_at="2026-01-01",
            place=f"City{i}, Country{i}", camera="", people=[], tags=[], caption="",
            images=[], timestamps=[], lat=None, lon=None,
        )
        for i in range(60)
    ]
    return Document(
        title="Many places", subtitle="60 assets", source_url="http://immich", version="1.7.0",
        layout="detail", assets=assets, places=pdf_export.places_table(assets),
        map_png=_png("green") if with_map else None,
    )


def test_places_map_with_many_rows_still_lands_on_a_page():
    pages_without_map = len(PdfReader(io.BytesIO(pdf_export.build(_many_places_doc(False)))).pages)
    r_with_map = PdfReader(io.BytesIO(pdf_export.build(_many_places_doc(True))))
    pages_with_map = len(r_with_map.pages)
    assert pages_with_map >= pages_without_map + 1 or any(page.images for page in r_with_map.pages)


def test_unique_path(tmp_path):
    path = tmp_path / "x.pdf"
    path.write_bytes(b"1")
    assert pdf_export.unique_path(str(path)) == str(tmp_path / "x-2.pdf")
    (tmp_path / "x-2.pdf").write_bytes(b"1")
    assert pdf_export.unique_path(str(path)) == str(tmp_path / "x-3.pdf")


def test_slugify_and_places():
    assert pdf_export.slugify("Hypercars 2026 / Ronald's") == "hypercars-2026-ronalds"
    assets = _doc().assets
    assert pdf_export.places_table(assets) == [("Spain", "Barcelona", 3)]


def test_no_backend_message(monkeypatch):
    monkeypatch.setattr(pdf_export, "_fpdf_available", lambda: False)
    with pytest.raises(pdf_export.NoPdfBackend) as exc:
        pdf_export.build(_doc())
    assert "fpdf2" in str(exc.value)


def test_render_map_uses_at_most_16_tiles_and_draws_points():
    from PIL import Image as PILImage

    calls = []
    def fetch(zoom, tile_x, tile_y):
        calls.append((zoom, tile_x, tile_y))
        return _png("white")
    png = pdf_export.render_map([(41.4, 2.2), (40.4, -3.7)], fetch)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and 1 <= len(calls) <= 16
    assert len({call[0] for call in calls}) == 1   # single zoom level

    # Verify a dot was drawn at the first point
    zoom = calls[0][0]
    min_tx = min(call[1] for call in calls)
    min_ty = min(call[2] for call in calls)
    lat, lon = 41.4, 2.2
    tile_x, tile_y = pdf_export._tile_xy(lat, lon, zoom)
    pixel_x, pixel_y = (tile_x - min_tx) * pdf_export.TILE, (tile_y - min_ty) * pdf_export.TILE
    img = PILImage.open(io.BytesIO(png))
    pixel = img.getpixel((int(pixel_x), int(pixel_y)))
    # "#d33" is (221, 51, 51) or similar red; white is (255, 255, 255)
    assert pixel[0] > 150 and pixel[1] < 120  # red channel high, green low


def test_render_map_returns_none_when_tiles_fail():
    def fetch(zoom, tile_x, tile_y): raise RuntimeError("offline")
    assert pdf_export.render_map([(41.4, 2.2)], fetch) is None
    assert pdf_export.render_map([], fetch) is None


# ── v1.8.0: photobook layout ────────────────────────────────


def test_photobook_layout_one_full_page_per_asset():
    """Photobook: one page per photo — and one page per frame for a multi-frame video."""
    doc = _doc(layout="photobook")
    reader = PdfReader(io.BytesIO(pdf_export.build(doc)))
    # 3 front-matter pages, 3 photo pages, and the 6-frame video unfolds into 6 pages.
    assert len(reader.pages) == 3 + 3 + 6
    page_text = reader.pages[3].extract_text()
    assert "Caption 0" in page_text
    # The metadata block shrinks to one line in a photobook; no field labels.
    assert "Camera:" not in page_text


def test_photobook_image_larger_than_detail_image():
    """A portrait image must be drawn taller on a photobook page than on a detail page.

    Landscape images are width-bound on both layouts; the photobook's gain is
    the vertical room (detail caps the image at 150 mm for the metadata block).
    """
    import re

    from PIL import Image as PILImage

    buffer = io.BytesIO()
    PILImage.new("RGB", (40, 64), "red").save(buffer, format="PNG")
    portrait = AssetEntry(
        id="p1", kind="IMAGE", filename="p.jpg", taken_at="2026-01-01", place="", camera="",
        caption="tall one", images=[buffer.getvalue()], timestamps=[], lat=None, lon=None,
    )

    def drawn_height(layout):
        document = Document(
            title="T", subtitle="s", source_url="http://immich", version="1.8.0",
            layout=layout, assets=[portrait], places=[], map_png=None,
        )
        reader = PdfReader(io.BytesIO(pdf_export.build(document)))
        content = reader.pages[3].get_contents().get_data().decode("latin-1")
        heights = [float(match.group(2)) for match in
                   re.finditer(r"([\d.]+) 0 0 ([\d.]+) [\d.-]+ [\d.-]+ cm", content)]
        assert heights, "no image transform on the asset page"
        return max(heights)

    assert drawn_height("photobook") > drawn_height("detail")


# ── v1.11.0: PDF labels in the user's language; centered photobook images ──


def test_spanish_labels_reach_the_page():
    doc = _doc()
    doc.language = "es"
    reader = PdfReader(io.BytesIO(pdf_export.build(doc)))
    assert "Índice" in reader.pages[1].extract_text()
    assert "Lugares" in reader.pages[2].extract_text()
    assert "Cámara:" in reader.pages[3].extract_text()
    assert "página 4/7" in reader.pages[3].extract_text()


def test_unknown_language_falls_back_to_english():
    doc = _doc()
    doc.language = "de"
    reader = PdfReader(io.BytesIO(pdf_export.build(doc)))
    assert "Index" in reader.pages[1].extract_text()


def test_photobook_centers_a_landscape_image_vertically():
    """A width-bound image sits in the middle of the image area, not glued to the top."""
    import re

    doc = _doc(layout="photobook", photo_count=1, with_video=False)  # 64x40 landscape fixture
    reader = PdfReader(io.BytesIO(pdf_export.build(doc)))
    content = reader.pages[3].get_contents().get_data().decode("latin-1")
    match = re.search(r"([\d.]+) 0 0 ([\d.]+) ([\d.-]+) ([\d.-]+) cm", content)
    assert match, "no image transform on the photobook page"
    drawn_h, bottom = float(match.group(2)), float(match.group(4))
    points_per_mm = 72 / 25.4
    page_h = pdf_export.A4_H * points_per_mm
    area_top = page_h - pdf_export.MARGIN * points_per_mm
    area_bottom = page_h - (pdf_export.A4_H - 2 * pdf_export.MARGIN - 34.0 + pdf_export.MARGIN) * points_per_mm
    image_center = bottom + drawn_h / 2
    area_center = (area_top + area_bottom) / 2
    assert abs(image_center - area_center) < 15  # within ~5 mm of the area's middle


# ── v1.12.0: photobook explodes a video into one page per chosen frame ──


def _video_doc(frame_count, frame_captions=None):
    from PIL import Image as PILImage
    frames = []
    for position in range(frame_count):
        buffer = io.BytesIO()
        PILImage.new("RGB", (64, 40), "navy").save(buffer, format="PNG")
        frames.append(buffer.getvalue())
    video = AssetEntry(
        id="v1", kind="VIDEO", filename="clip.mp4", taken_at="2026-01-09", place="", camera="",
        caption="The whole story.", images=frames, timestamps=[float(position * 10) for position in range(frame_count)],
        frame_captions=frame_captions or [],
    )
    return Document(title="T", subtitle="s", source_url="http://immich", version="1.12.0",
                    layout="photobook", assets=[video], places=[], map_png=None)


def test_photobook_gives_each_video_frame_its_own_page():
    reader = PdfReader(io.BytesIO(pdf_export.build(_video_doc(3))))
    assert len(reader.pages) == 3 + 3  # cover, index, places, one page per frame
    assert "The whole story." in reader.pages[3].extract_text()  # asset caption on the first frame page
    assert "20.0 s" in reader.pages[5].extract_text()  # each page carries its timestamp


def test_photobook_frame_captions_go_one_per_page():
    captions = ["Sunset over the sea.", "Dusk lights.", "The moon leaves."]
    reader = PdfReader(io.BytesIO(pdf_export.build(_video_doc(3, captions))))
    assert "Dusk lights." in reader.pages[4].extract_text()
    assert "The moon leaves." in reader.pages[5].extract_text()
    assert "Dusk lights." not in reader.pages[3].extract_text()


# ── v1.12.0: cover, index and places pages are optional ─────


def test_front_matter_pages_can_be_turned_off():
    doc = _doc(layout="photobook", photo_count=1, with_video=False)
    doc.with_cover = False
    doc.with_index = False
    doc.with_places = False
    reader = PdfReader(io.BytesIO(pdf_export.build(doc)))
    assert len(reader.pages) == 1  # just the photo page, nothing else
    assert "Caption 0" in reader.pages[0].extract_text()


def test_index_off_keeps_cover_and_places():
    doc = _doc(photo_count=2, with_video=False)
    doc.with_index = False
    reader = PdfReader(io.BytesIO(pdf_export.build(doc)))
    assert len(reader.pages) == 2 + 2  # cover, places, two detail pages
    assert "Lab Album" in reader.pages[0].extract_text()
    assert "Barcelona" in reader.pages[1].extract_text()

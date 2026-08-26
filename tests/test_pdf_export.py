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


def _doc(layout="detail", n=3, with_video=True):
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
        for i in range(n)
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
    r = PdfReader(io.BytesIO(pdf))
    assert len(r.pages) == 3 + 4  # cover, index, places, 4 assets
    assert "Lab Album" in r.pages[0].extract_text()
    assert "clip.mp4" in r.pages[1].extract_text()
    assert "Barcelona" in r.pages[2].extract_text()
    assert "Caption 0" in r.pages[3].extract_text()
    assert "0.5" in r.pages[6].extract_text()  # video timestamps


def test_index_links_point_to_pages():
    r = PdfReader(io.BytesIO(pdf_export.build(_doc())))
    annots = r.pages[1].get("/Annots") or []
    assert len(annots) == 4


def test_build_grid_six_per_page():
    r = PdfReader(io.BytesIO(pdf_export.build(_doc(layout="grid", n=13, with_video=False))))
    assert len(r.pages) == 3 + 3  # 13 assets → 6+6+1


def test_build_with_map_adds_image_on_places_page():
    d = _doc()
    d.map_png = _png("green")
    r = PdfReader(io.BytesIO(pdf_export.build(d)))
    assert len(r.pages[2].images) >= 1


def test_unique_path(tmp_path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"1")
    assert pdf_export.unique_path(str(p)) == str(tmp_path / "x-2.pdf")
    (tmp_path / "x-2.pdf").write_bytes(b"1")
    assert pdf_export.unique_path(str(p)) == str(tmp_path / "x-3.pdf")


def test_slugify_and_places():
    assert pdf_export.slugify("Hypercars 2026 / Ronald's") == "hypercars-2026-ronalds"
    assets = _doc().assets
    assert pdf_export.places_table(assets) == [("Spain", "Barcelona", 3)]


def test_no_backend_message(monkeypatch):
    monkeypatch.setattr(pdf_export, "_fpdf_available", lambda: False)
    with pytest.raises(pdf_export.NoPdfBackend) as exc:
        pdf_export.build(_doc())
    assert "immich-photo-manager[pdf]" in str(exc.value)


def test_render_map_uses_at_most_16_tiles_and_draws_points():
    calls = []
    def fetch(z, x, y):
        calls.append((z, x, y))
        return _png("white")
    png = pdf_export.render_map([(41.4, 2.2), (40.4, -3.7)], fetch)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and 1 <= len(calls) <= 16
    assert len({c[0] for c in calls}) == 1   # single zoom level


def test_render_map_returns_none_when_tiles_fail():
    def fetch(z, x, y): raise RuntimeError("offline")
    assert pdf_export.render_map([(41.4, 2.2)], fetch) is None
    assert pdf_export.render_map([], fetch) is None

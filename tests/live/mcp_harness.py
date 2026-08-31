"""Exercise every MCP tool of immich-photo-manager (PyPI install) over real stdio MCP against a live Immich."""

import sys
import os
import json
import asyncio
import base64
import shutil
import tempfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

creds = json.load(open(sys.argv[1]))
TAG = sys.argv[2]
BIN = sys.argv[3]
MEDIA = sys.argv[4]
ALB = creds["album_id"]
IDS = creds["asset_ids"]
EXTRA = creds["extra"]
VIDEO = IDS[0]
PHOTO1, PHOTO2, PHOTO3, PHOTO4 = IDS[1:5]
cache = tempfile.mkdtemp(prefix=f"immich-cache-{TAG}-")
env = {
    **os.environ,
    "IMMICH_BASE_URL": creds["base"],
    "IMMICH_API_KEY": creds["key"],
    "IMMICH_CACHE_DIR": cache,
    "MCP_TRANSPORT": "stdio",
}
results = []


def rec(tool, ok, note=""):
    """Record one check and print its line; the summary at the end counts these."""
    results.append({"tool": tool, "ok": bool(ok), "note": str(note)[:220]})
    print(("✅" if ok else "❌"), f"{tool:26s}", str(note)[:160], flush=True)


class LiveHarness:
    """Drives every tool over one MCP session, one method per area, recording results with `rec`.

    Two things cross area boundaries and live on the instance: the library
    statistics read first (`stats`, later counts are checked against them) and
    the id of the album the harness creates (`new_album`, reused by the album,
    tag, upload and shared-link checks). Everything else is local to its method.
    """

    def __init__(self, session):
        self.session = session

    async def call(self, tool, **kwargs):
        """Call one tool; returns (parsed JSON or text, image blocks, failed?, raw text)."""
        res = await self.session.call_tool(tool, kwargs)
        txt = "".join(content.text for content in res.content if getattr(content, "type", "") == "text")
        imgs = [content for content in res.content if getattr(content, "type", "") == "image"]
        data = None
        try:
            data = json.loads(txt) if txt else None
        except Exception:
            data = txt
        err = res.isError or (isinstance(data, dict) and "error" in data)
        return data, imgs, err, txt

    @staticmethod
    def okj(data, failed):
        """A successful call that returned something."""
        return (not failed) and data is not None

    async def check_health(self):
        """Health."""
        data, _, failed, _ = await self.call("ping")
        rec("ping", self.okj(data, failed), data)
        data, _, failed, _ = await self.call("get_server_version")
        rec("get_server_version", self.okj(data, failed), data)
        data, _, failed, _ = await self.call("get_statistics")
        self.stats = data or {}
        rec(
            "get_statistics",
            self.okj(data, failed) and self.stats.get("photos") is not None,
            {key: value for key, value in self.stats.items() if isinstance(value, (int, float))},
        )
        data, _, failed, _ = await self.call("get_connection_info")
        rec("get_connection_info", self.okj(data, failed), data)

    async def check_assets_read(self):
        """Assets read."""
        data, _, failed, _ = await self.call("get_asset_info", asset_id=PHOTO2)
        city = ((data or {}).get("exifInfo") or {}).get("city") or (data or {}).get("city")
        rec(
            "get_asset_info",
            self.okj(data, failed) and data.get("id") == PHOTO2,
            f"file={data.get('originalFileName')} city={city}",
        )
        data, _, failed, _ = await self.call("list_assets", asset_type="VIDEO")
        total = data.get("total") if isinstance(data, dict) else None
        rec("list_assets(type=VIDEO)", self.okj(data, failed) and total == 1, f"total={total}")
        data, _, failed, _ = await self.call("list_assets", page=1, size=100)
        rec(
            "list_assets(all)",
            self.okj(data, failed) and data.get("total") == self.stats.get("photos", 0) + self.stats.get("videos", 0),
            f"total={data.get('total')} (statistics say {self.stats.get('photos', 0) + self.stats.get('videos', 0)})",
        )
        data, _, failed, _ = await self.call("search_metadata", make="LabCam")
        rec(
            "search_metadata(make)",
            self.okj(data, failed) and data.get("total") == 4,
            f"total={data.get('total')} (expected 4)",
        )
        data, _, failed, _ = await self.call("search_metadata", city="Lisbon")
        rec(
            "search_metadata(city)",
            self.okj(data, failed) and data.get("total") == 2,
            f"total={data.get('total')} (expected 2)",
        )
        data, _, failed, _ = await self.call(
            "search_metadata",
            taken_after="2026-03-02T00:00:00Z",
            taken_before="2026-03-03T23:59:59Z",
        )
        rec(
            "search_metadata(dates)",
            self.okj(data, failed) and data.get("total") == 2,
            f"total={data.get('total')} (expected 2: 03-02, 03-03)",
        )
        data, _, failed, _ = await self.call("get_map_markers")
        total = len(data) if isinstance(data, list) else (data or {}).get("count", data)
        rec("get_map_markers", self.okj(data, failed), f"{total}")

    async def check_metadata_write_verify(self):
        """Metadata write + verify."""
        data, _, failed, _ = await self.call(
            "update_asset_metadata",
            asset_id=PHOTO3,
            description="Tree in Sintra",
            is_favorite=True,
            rating=4,
            latitude=38.8,
            longitude=-9.39,
            date_time_original="2026-03-03T15:00:00.000Z",
        )
        asset, _, _, _ = await self.call("get_asset_info", asset_id=PHOTO3)
        exif = asset.get("exifInfo") or {}
        rec(
            "update_asset_metadata",
            (not failed)
            and exif.get("description") == "Tree in Sintra"
            and asset.get("isFavorite") is True
            and exif.get("rating") == 4
            and abs((exif.get("latitude") or 0) - 38.8) < 0.01
            and str(exif.get("dateTimeOriginal", "")).startswith("2026-03-03T15:00"),
            f"desc={exif.get('description')!r} fav={asset.get('isFavorite')} rating={exif.get('rating')} lat={exif.get('latitude')} dto={exif.get('dateTimeOriginal')}",
        )
        data, _, failed, _ = await self.call("list_assets", is_favorite=True)
        rec(
            "list_assets(favorite)",
            self.okj(data, failed) and data.get("total") == 1,
            f"total={data.get('total')}",
        )

    async def check_albums(self):
        """Albums."""
        data, _, failed, _ = await self.call("list_albums")
        rec(
            "list_albums",
            self.okj(data, failed)
            and any(
                asset.get("albumName") == "Lab Album"
                for asset in (data if isinstance(data, list) else data.get("albums", []))
            ),
            f"{len(data) if isinstance(data, list) else data.get('count', data.get('total'))} albums",
        )
        data, _, failed, _ = await self.call("get_album", album_id=ALB)
        rec(
            "get_album",
            self.okj(data, failed) and sorted(data.get("asset_ids", [])) == sorted(IDS),
            f"{len(data.get('asset_ids', []))} asset_ids, assetCount={data.get('assetCount')}",
        )
        data, _, failed, _ = await self.call(
            "create_album", name="Harness Album", description="tmp", asset_ids=[PHOTO1]
        )
        self.new_album = (data or {}).get("id")
        rec("create_album", self.okj(data, failed) and self.new_album, f"id={self.new_album}")
        data, _, failed, _ = await self.call(
            "update_album", album_id=self.new_album, name="Harness Album 2", description="updated"
        )
        album, _, _, _ = await self.call("get_album", album_id=self.new_album)
        rec(
            "update_album",
            (not failed)
            and album.get("albumName") == "Harness Album 2"
            and album.get("description") == "updated",
            f"name={album.get('albumName')} desc={album.get('description')}",
        )
        data, _, failed, _ = await self.call("add_assets_to_album", album_id=self.new_album, asset_ids=[PHOTO2, PHOTO3])
        album, _, _, _ = await self.call("get_album", album_id=self.new_album)
        rec(
            "add_assets_to_album",
            (not failed) and sorted(album["asset_ids"]) == sorted([PHOTO1, PHOTO2, PHOTO3]),
            f"{len(album['asset_ids'])} assets",
        )
        data, _, failed, _ = await self.call("remove_assets_from_album", album_id=self.new_album, asset_ids=[PHOTO2])
        album, _, _, _ = await self.call("get_album", album_id=self.new_album)
        rec(
            "remove_assets_from_album",
            (not failed) and sorted(album["asset_ids"]) == sorted([PHOTO1, PHOTO3]),
            f"{len(album['asset_ids'])} assets",
        )

    async def check_thumbnails_json(self):
        """Thumbnails JSON."""
        data, _, failed, _ = await self.call("get_asset_thumbnail", asset_id=PHOTO1, size="thumbnail")
        thumb_b64 = data.get("data") or data.get("thumbnail", {}).get("data") if isinstance(data, dict) else None
        rec(
            "get_asset_thumbnail",
            self.okj(data, failed) and thumb_b64 and base64.b64decode(thumb_b64)[:4] == b"RIFF",
            f"type={data.get('type')} b64={len(thumb_b64 or '')}",
        )
        data, _, failed, _ = await self.call("get_asset_thumbnail", asset_id=VIDEO, size="preview")
        thumb_b64 = data.get("data") if isinstance(data, dict) else None
        rec(
            "get_asset_thumbnail(video,preview)",
            self.okj(data, failed) and thumb_b64 and base64.b64decode(thumb_b64)[:2] == b"\xff\xd8",
            f"type={data.get('type')} b64={len(thumb_b64 or '')}",
        )
        data, _, failed, _ = await self.call(
            "get_album_thumbnails", album_id=ALB, size="thumbnail", limit=50
        )
        rec(
            "get_album_thumbnails",
            self.okj(data, failed) and data.get("fetchedCount") == 5,
            f"fetched={data.get('fetchedCount')}/{data.get('totalAssets')}",
        )
        data, _, failed, _ = await self.call(
            "get_thumbnails_batch", asset_ids=[PHOTO1, VIDEO, EXTRA["einstein.jpg"]], size="thumbnail"
        )
        rec(
            "get_thumbnails_batch",
            self.okj(data, failed)
            and data.get("fetchedCount") == 3
            and data["thumbnails"][0].get("originalFileName"),
            f"fetched={data.get('fetchedCount')} names={[tag.get('originalFileName') for tag in data.get('thumbnails', [])]}",
        )

    async def check_image_blocks(self):
        """Image blocks."""
        data, imgs, failed, _ = await self.call("get_asset_image", asset_id=PHOTO1, size="thumbnail")
        rec(
            "get_asset_image",
            (not failed) and len(imgs) == 1 and imgs[0].mimeType.startswith("image/"),
            f"{len(imgs)} image block mime={imgs[0].mimeType if imgs else None} bytes={len(base64.b64decode(imgs[0].data)) if imgs else 0}",
        )
        data, imgs, failed, _ = await self.call("get_album_images", album_id=ALB, size="preview", limit=50)
        rec(
            "get_album_images",
            (not failed) and len(imgs) == 5,
            f"{len(imgs)} image blocks mimes={sorted(set(i.mimeType for i in imgs))}",
        )
        data, imgs, failed, _ = await self.call(
            "get_images_batch", asset_ids=[PHOTO1, PHOTO2, VIDEO], size="thumbnail"
        )
        rec("get_images_batch", (not failed) and len(imgs) == 3, f"{len(imgs)} image blocks")

    async def check_video_frames(self):
        """Video frames (clip.mp4 is 3 s; frames land at 0.5/1.5/2.5 s)."""
        data, imgs, failed, _ = await self.call("get_video_frames", asset_id=VIDEO, count=3)
        rec(
            "get_video_frames",
            (not failed) and len(imgs) == 3
            and all(base64.b64decode(i.data)[:2] == b"\xff\xd8" for i in imgs),
            f"{len(imgs)} jpeg frames bytes={[len(base64.b64decode(i.data)) for i in imgs]}",
        )
        data, imgs, failed, _ = await self.call("get_video_frames", asset_id=VIDEO, count=50, size="preview")
        rec(
            "get_video_frames(cap)",
            isinstance(data, dict) and data.get("confirm_required") and data.get("frames_planned") == 50,
            f"plan={data if isinstance(data, dict) else data}",
        )
        data, _, failed, _ = await self.call("get_video_frames_json", asset_id=VIDEO, count=4)
        timestamps = [face["timestamp"] for face in data.get("frames", [])] if isinstance(data, dict) else []
        rec(
            "get_video_frames_json",
            self.okj(data, failed) and data.get("count") == 4 and 2.5 <= data.get("duration", 0) <= 3.5
            and timestamps == sorted(timestamps) and all(face["type"] == "image/jpeg" for face in data["frames"]),
            f"duration={data.get('duration') if isinstance(data, dict) else data} backend={data.get('backend') if isinstance(data, dict) else None} ts={timestamps}",
        )

    async def check_video_granularity(self):
        """Video granularity."""
        data, imgs, failed, _ = await self.call("get_video_frames", asset_id=VIDEO, count=20)
        rec("get_video_frames(gate)", isinstance(data, dict) and data.get("confirm_required") and data.get("frames_planned") == 20,
            f"plan={data if isinstance(data, dict) else data}")
        data, imgs, failed, _ = await self.call("get_video_frames", asset_id=VIDEO, count=20, confirm=True)
        rec("get_video_frames(confirm)", (not failed) and len(imgs) == 20, f"{len(imgs)} frames")
        data, imgs, failed, _ = await self.call("get_video_frames", asset_id=VIDEO, interval=1.0)
        rec("get_video_frames(interval)", (not failed) and len(imgs) == 3, f"{len(imgs)} frames at 1 s")
        data, imgs, failed, _ = await self.call("get_video_frames", asset_id=VIDEO, count=2, start=1.0, end=2.0)
        rec("get_video_frames(segment)", (not failed) and len(imgs) == 2, f"{len(imgs)} frames in 1-2 s")

    async def check_pdf_export(self):
        """PDF export."""
        data, _, failed, _ = await self.call("get_export_preview", album_id=ALB)
        rec("get_export_preview", self.okj(data, failed) and data.get("count") == 5, f"count={data.get('count') if isinstance(data, dict) else data}")
        options = data.get("options") if isinstance(data, dict) else {}
        rec("get_export_preview(options)", isinstance(options, dict) and "layout" in options and "cover" in options,
            f"{len(options or {})} export choices listed")
        out = os.path.join(cache, f"lab-{TAG}.pdf")
        data, _, failed, _ = await self.call("export_pdf", album_id=ALB, output_path=out, frames_per_video=3,
                                captions={PHOTO1: "harness caption"})
        pages = 0
        if isinstance(data, dict) and data.get("path") and os.path.exists(data["path"]):
            import subprocess
            info = subprocess.run(["pdfinfo", data["path"]], capture_output=True, text=True).stdout if shutil.which("pdfinfo") else ""
            pages = int(next((line.split()[-1] for line in info.splitlines() if line.startswith("Pages:")), data.get("pages", 0)))
        rec("export_pdf", self.okj(data, failed) and pages >= 8 and data.get("assets_included") == 5,
            f"path={data.get('path') if isinstance(data, dict) else data} pages={pages} bytes={data.get('bytes') if isinstance(data, dict) else 0}")
        data, _, failed, _ = await self.call("export_pdf", asset_ids=[PHOTO1, VIDEO], output_path=out, layout="grid", return_base64=True)
        rec("export_pdf(ids,grid,b64)", self.okj(data, failed) and data["path"].endswith("-2.pdf") and base64.b64decode(data["pdf_base64"])[:4] == b"%PDF",
            f"path={data.get('path') if isinstance(data, dict) else data}")
        data, _, failed, _ = await self.call(
            "export_pdf", asset_ids=[PHOTO1, VIDEO], output_path=out,
            layout="photobook", frames_per_video=1,
        )
        rec(
            "export_pdf(photobook)",
            self.okj(data, failed) and data.get("assets_included") == 2 and not data.get("warnings"),
            f"path={data.get('path') if isinstance(data, dict) else data} pages={data.get('pages') if isinstance(data, dict) else 0}",
        )
        data, _, failed, _ = await self.call(
            "export_pdf", asset_ids=[PHOTO1], output_path=out, image_size="original",
        )
        rec(
            "export_pdf(original)",
            self.okj(data, failed) and data.get("assets_included") == 1 and not data.get("warnings"),
            f"bytes={data.get('bytes') if isinstance(data, dict) else 0} warnings={data.get('warnings') if isinstance(data, dict) else '?'}",
        )
        data, _, failed, _ = await self.call(
            "export_pdf", asset_ids=[VIDEO], output_path=out,
            layout="photobook", frame_times={VIDEO: [1.0]},
        )
        rec(
            "export_pdf(frame_times)",
            self.okj(data, failed) and data.get("assets_included") == 1 and not data.get("warnings"),
            f"pages={data.get('pages') if isinstance(data, dict) else 0} warnings={data.get('warnings') if isinstance(data, dict) else '?'}",
        )
        data, _, failed, _ = await self.call(
            "export_pdf", asset_ids=[VIDEO], output_path=out,
            layout="photobook", frame_times={VIDEO: [0.5, 1.5, 2.5]},
            frame_captions={VIDEO: ["one", "two", "three"]},
            cover=False, index=False, places=False,
        )
        rec(
            "export_pdf(frame pages, no front matter)",
            self.okj(data, failed) and data.get("pages") == 3 and not data.get("warnings"),
            f"pages={data.get('pages') if isinstance(data, dict) else 0} (3 chosen frames, front matter off)",
        )
        data, images, failed, _ = await self.call(
            "get_video_frames", asset_id=VIDEO, interval=1.0, sheet=True,
        )
        rec(
            "get_video_frames(sheet)",
            (not failed) and len(images) == 1,
            f"{len(images)} sheet(s) for a 3 s clip at 1 fps",
        )
        data, _, failed, _ = await self.call(
            "export_pdf", asset_ids=[PHOTO1], output_path=out, language="es",
        )
        rec(
            "export_pdf(language=es)",
            self.okj(data, failed) and data.get("assets_included") == 1 and not data.get("warnings"),
            f"pages={data.get('pages') if isinstance(data, dict) else 0}",
        )

    async def check_shared_links(self):
        """Shared links."""
        data, _, failed, _ = await self.call(
            "create_shared_link",
            album_id=ALB,
            allow_download=True,
            show_metadata=True,
            description="lab share",
        )
        LINK = (data or {}).get("id")
        KEY = (data or {}).get("key")
        URL = (data or {}).get("url")
        rec("create_shared_link", self.okj(data, failed) and LINK and KEY, f"url={URL}")
        import httpx

        try:
            pub = httpx.get(
                f"{creds['base']}/api/shared-links/me", params={"key": KEY}, timeout=30
            )
            rec(
                "  shared link public GET /shared-links/me?key",
                pub.status_code == 200
                and pub.json().get("album", {}).get("albumName") == "Lab Album",
                f"HTTP {pub.status_code} album={pub.json().get('album', {}).get('albumName') if pub.status_code == 200 else pub.text[:80]}",
            )
        except Exception as exif:
            rec("  shared link public GET", False, repr(exif)[:100])
        data, _, failed, _ = await self.call("list_shared_links")
        rec(
            "list_shared_links",
            self.okj(data, failed)
            and any(
                lnk.get("id") == LINK
                for lnk in (
                    data if isinstance(data, list) else data.get("links", data.get("shared_links", []))
                )
            ),
            f"{len(data) if isinstance(data, list) else data}",
        )
        data, _, failed, _ = await self.call("get_shared_link", link_id=LINK)
        rec(
            "get_shared_link", self.okj(data, failed) and data.get("id") == LINK, f"desc={data.get('description')}"
        )
        data, _, failed, _ = await self.call(
            "update_shared_link",
            link_id=LINK,
            allow_download=False,
            description="lab share 2",
            expiry_at="2027-01-01T00:00:00.000Z",
        )
        album, _, _, _ = await self.call("get_shared_link", link_id=LINK)
        rec(
            "update_shared_link",
            (not failed)
            and album.get("allowDownload") is False
            and album.get("description") == "lab share 2"
            and str(album.get("expiresAt", "")).startswith("2027"),
            f"allowDownload={album.get('allowDownload')} desc={album.get('description')} expires={album.get('expiresAt')}",
        )
        data, _, failed, _ = await self.call("delete_shared_link", link_id=LINK)
        album, _, failed_again, _ = await self.call("get_shared_link", link_id=LINK)
        rec("delete_shared_link", (not failed) and failed_again, f"after delete: get -> error={failed_again}")

    async def check_tags(self):
        """Tags (clean leftovers from earlier runs first)."""
        tag_list, _, _, _ = await self.call("list_tags")
        for tag in tag_list if isinstance(tag_list, list) else tag_list.get("tags", []):
            if tag.get("name") == "harness-tag":
                await self.call("delete_tag", tag_id=tag["id"])
        data, _, failed, _ = await self.call("create_tag", name="harness-tag", color="#ff0000")
        TID = (data or {}).get("id")
        rec("create_tag", self.okj(data, failed) and TID, f"id={TID} {str(data)[:100] if not TID else ''}")
        if not TID:
            tag_list, _, _, _ = await self.call("list_tags")
            TID = next(
                (
                    tag["id"]
                    for tag in (tag_list if isinstance(tag_list, list) else tag_list.get("tags", []))
                    if tag.get("name") == "harness-tag"
                ),
                None,
            )
        data, _, failed, _ = await self.call("list_tags")
        rec(
            "list_tags",
            self.okj(data, failed)
            and any(
                tag.get("name") == "harness-tag"
                for tag in (data if isinstance(data, list) else data.get("tags", []))
            ),
            f"{len(data) if isinstance(data, list) else data.get('count')} tags",
        )
        data, _, failed, _ = await self.call("get_tag", tag_id=TID)
        rec("get_tag", self.okj(data, failed) and data.get("name") == "harness-tag", f"color={data.get('color')}")
        data, _, failed, _ = await self.call("update_tag", tag_id=TID, name="harness-tag-2")
        rec("update_tag(name -> clear error)", failed and "rename" in str(data).lower(), str(data)[:120])
        data, _, failed, _ = await self.call("update_tag", tag_id=TID, color="#00ff00")
        album, _, _, _ = await self.call("get_tag", tag_id=TID)
        rec(
            "update_tag(color)",
            (not failed) and str(album.get("color", "")).lower() == "#00ff00",
            f"color={album.get('color')}",
        )
        data, _, failed, _ = await self.call("tag_assets", tag_id=TID, asset_ids=[PHOTO1, PHOTO2])
        asset, _, _, _ = await self.call("get_asset_info", asset_id=PHOTO1)
        tag_names = [tag.get("name") for tag in asset.get("tags", [])]
        rec("tag_assets", (not failed) and "harness-tag" in tag_names, f"asset tags={tag_names}")
        data, _, failed, _ = await self.call("untag_assets", tag_id=TID, asset_ids=[PHOTO1])
        asset, _, _, _ = await self.call("get_asset_info", asset_id=PHOTO1)
        tag_names = [tag.get("name") for tag in asset.get("tags", [])]
        rec("untag_assets", (not failed) and "harness-tag" not in tag_names, f"asset tags={tag_names}")
        data, _, failed, _ = await self.call("delete_tag", tag_id=TID)
        album, _, failed_again, _ = await self.call("get_tag", tag_id=TID)
        rec("delete_tag", (not failed) and failed_again, f"after delete: error={failed_again}")

    async def check_upload_trash_lifecycle(self):
        """Upload / trash lifecycle."""
        data, _, failed, _ = await self.call(
            "upload_asset", file_path=os.path.join(MEDIA, "upload_test.jpg"), album_id=self.new_album
        )
        UPLOADED = (data or {}).get("id") or (data or {}).get("asset_id")
        rec(
            "upload_asset",
            self.okj(data, failed) and UPLOADED and (data or {}).get("status") == "created",
            f"{ {key: value for key, value in (data or {}).items() if key != 'raw'} }",
        )
        album, _, _, _ = await self.call("get_album", album_id=self.new_album)
        rec(
            "  upload landed in album",
            UPLOADED in album.get("asset_ids", []),
            f"album has {len(album.get('asset_ids', []))}",
        )
        data, _, failed, _ = await self.call("delete_assets", asset_ids=[UPLOADED])
        tag, _, _, _ = await self.call("list_assets", is_trashed=True)
        trashed = (
            [asset.get("id") for asset in tag.get("assets", tag.get("items", []))]
            if isinstance(tag, dict)
            else []
        )
        rec(
            "delete_assets(soft) + list_assets(is_trashed)",
            (not failed) and UPLOADED in trashed and tag.get("total") == 1,
            f"trashed total={tag.get('total')} contains={UPLOADED in trashed}",
        )
        data, _, failed, _ = await self.call("restore_assets", asset_ids=[UPLOADED])
        asset, _, failed_again, _ = await self.call("get_asset_info", asset_id=UPLOADED)
        rec(
            "restore_assets",
            (not failed) and (not failed_again) and not asset.get("isTrashed"),
            f"isTrashed={asset.get('isTrashed')}",
        )
        data, _, failed, _ = await self.call("delete_assets", asset_ids=[UPLOADED])
        restored, _, failed_again, _ = await self.call("restore_trash")
        asset, _, _, _ = await self.call("get_asset_info", asset_id=UPLOADED)
        rec(
            "restore_trash",
            (not failed) and (not failed_again) and not asset.get("isTrashed"),
            f"isTrashed={asset.get('isTrashed')}",
        )
        data, _, failed, _ = await self.call("delete_assets", asset_ids=[UPLOADED])
        restored, _, failed_again, _ = await self.call("empty_trash")
        await asyncio.sleep(3)
        asset, _, failed_third, _ = await self.call("get_asset_info", asset_id=UPLOADED)
        rec(
            "empty_trash",
            (not failed) and (not failed_again) and (failed_third or asset.get("isTrashed") or not asset.get("id")),
            f"asset after empty_trash: error={failed_third} isTrashed={asset.get('isTrashed') if isinstance(asset, dict) else asset}",
        )
        upload_again, _, _, _ = await self.call(
            "upload_asset", file_path=os.path.join(MEDIA, "upload_test2.jpg")
        )
        UPLOADED_AGAIN = (upload_again or {}).get("id")
        data, _, failed, _ = await self.call("delete_assets", asset_ids=[UPLOADED_AGAIN], force=True)
        await asyncio.sleep(2)
        asset, _, failed_again, _ = await self.call("get_asset_info", asset_id=UPLOADED_AGAIN)
        rec(
            "delete_assets(force)",
            (not failed) and failed_again,
            f"uploaded {str(UPLOADED_AGAIN)[:8]} then force-deleted: get -> error={failed_again}",
        )
        data, _, failed, _ = await self.call("delete_album", album_id=self.new_album)
        album, _, failed_again, _ = await self.call("get_album", album_id=self.new_album)
        rec("delete_album", (not failed) and failed_again, f"after delete error={failed_again}")

    async def check_edits(self):
        """Edits."""
        data, _, failed, _ = await self.call("rotate_assets", angle=90, asset_ids=[PHOTO1])
        rec("rotate_assets(ids)", self.okj(data, failed) and data.get("rotated") == 1, data)
        data, _, failed, _ = await self.call("rotate_assets", angle=90, album_id=ALB)
        rec(
            "rotate_assets(album)",
            self.okj(data, failed) and data.get("rotated") == 4 and data.get("failed") == 1,
            f"rotated={data.get('rotated')} failed={data.get('failed')} (video expected to fail: Immich 'Only images can be edited')",
        )
        data, _, failed, _ = await self.call("revert_asset_edits", asset_ids=[PHOTO1])
        rec("revert_asset_edits(ids)", self.okj(data, failed), data)
        data, _, failed, _ = await self.call("revert_asset_edits", album_id=ALB)
        rec("revert_asset_edits(album)", self.okj(data, failed), data)

    async def check_ml_smart_search_people(self):
        """ML: smart search, people, duplicates."""
        data, _, failed, _ = await self.call("search_smart", query="portrait of a man with a beard", size=5)
        items = data.get("assets", data.get("results", [])) if isinstance(data, dict) else []
        top = [asset.get("originalFileName") for asset in items[:3]]
        rec(
            "search_smart",
            self.okj(data, failed) and any("lincoln" in (total or "") or "einstein" in (total or "") for total in top),
            f"top3={top}",
        )
        data, _, failed, _ = await self.call("search_smart", query="boat", city="Senhora do Porto", size=5)
        rec(
            "search_smart(+city filter)",
            self.okj(data, failed),
            f"total={data.get('total') if isinstance(data, dict) else data}",
        )
        data, _, failed, _ = await self.call("list_people", with_hidden=True)
        people = data.get("people", data) if isinstance(data, dict) else data
        ppl = people if isinstance(people, list) else []
        rec(
            "list_people",
            self.okj(data, failed) and len(ppl) >= 1,
            f"{len(ppl)} people total={data.get('total') if isinstance(data, dict) else ''}",
        )
        PID = ppl[0]["id"] if ppl else None
        if PID:
            data, _, failed, _ = await self.call("get_person", person_id=PID)
            rec("get_person", self.okj(data, failed) and data.get("id") == PID, f"name={data.get('name')!r}")
            data, _, failed, _ = await self.call(
                "update_person",
                person_id=PID,
                name="Abe",
                birth_date="1809-02-12",
                is_favorite=True,
            )
            album, _, _, _ = await self.call("get_person", person_id=PID)
            rec(
                "update_person",
                (not failed)
                and album.get("name") == "Abe"
                and str(album.get("birthDate", "")).startswith("1809-02-12"),
                f"name={album.get('name')} birth={album.get('birthDate')} fav={album.get('isFavorite')}",
            )
            data, _, failed, _ = await self.call("search_people", name="Abe")
            people_list = data if isinstance(data, list) else data.get("people", [])
            rec(
                "search_people",
                self.okj(data, failed) and any(pong.get("id") == PID for pong in people_list),
                f"{len(people_list)} hits",
            )
            data, _, failed, _ = await self.call("get_person_thumbnail", person_id=PID)
            thumb_b64 = data.get("data") if isinstance(data, dict) else None
            rec("get_person_thumbnail", self.okj(data, failed) and thumb_b64, f"b64={len(thumb_b64 or '')}")
            data, _, failed, _ = await self.call("get_asset_faces", asset_id=EXTRA["lincoln1.jpg"])
            faces = data if isinstance(data, list) else data.get("faces", [])
            rec(
                "get_asset_faces",
                self.okj(data, failed) and len(faces) >= 1,
                f"{len(faces)} faces on lincoln1, person={faces[0].get('person', {}).get('id') if faces and faces[0].get('person') else None}",
            )
            FID = faces[0].get("id") if faces else None
            others = [pong["id"] for pong in ppl if pong["id"] != PID]
            for filename in (
                "einstein.jpg",
                "roosevelt.jpg",
                "curie.jpg",
            ):  # Immich 3.x hides 1-face people from /people; find them via faces
                if filename not in EXTRA:
                    continue
                faces, _, _, _ = await self.call("get_asset_faces", asset_id=EXTRA[filename])
                faces = faces if isinstance(faces, list) else faces.get("faces", [])
                for face in faces:
                    pid2 = (face.get("person") or {}).get("id")
                    if pid2 and pid2 != PID and pid2 not in others:
                        others.append(pid2)
            if FID and others:
                data, _, failed, _ = await self.call("reassign_face", face_id=FID, person_id=others[0])
                faces_after, _, _, _ = await self.call("get_asset_faces", asset_id=EXTRA["lincoln1.jpg"])
                faces_after = faces_after if isinstance(faces_after, list) else faces_after.get("faces", [])
                now = (faces_after[0].get("person") or {}).get("id") if faces_after else None
                rec(
                    "reassign_face",
                    (not failed) and now == others[0],
                    f"face {FID[:8]} -> person {others[0][:8]}; now belongs to {str(now)[:8]}",
                )
                data, _, failed, _ = await self.call("reassign_face", face_id=FID, person_id=PID)
                rec("reassign_face(back)", self.okj(data, failed), "restored")
            else:
                rec(
                    "reassign_face",
                    False,
                    f"SKIPPED: faces={bool(FID)} other_people={len(others)}",
                )
            if len(others) >= 1:
                data, _, failed, _ = await self.call("merge_people", person_id=PID, merge_ids=[others[-1]])
                album, _, failed_again, _ = await self.call("get_person", person_id=others[-1])
                rec(
                    "merge_people",
                    (not failed) and failed_again,
                    f"merged {others[-1][:8]} into {PID[:8]}; merged person gone={failed_again}",
                )
            else:
                rec("merge_people", False, "SKIPPED: only one person detected")
        else:
            for tag in (
                "get_person",
                "update_person",
                "search_people",
                "get_person_thumbnail",
                "get_asset_faces",
                "merge_people",
                "reassign_face",
            ):
                rec(tag, False, "SKIPPED: no people detected (ML)")
        data, _, failed, _ = await self.call("get_duplicates")
        groups = data if isinstance(data, list) else data.get("groups", data.get("duplicates", []))
        rec(
            "get_duplicates",
            self.okj(data, failed) and len(groups) >= 1,
            f"{len(groups)} groups: {[[asset.get('originalFileName') for asset in album.get('assets', [])] for album in groups][:2]}",
        )
        if groups:
            first_group = groups[0]
            aids = [asset["id"] for asset in first_group.get("assets", [])]
            data, _, failed, _ = await self.call(
                "resolve_duplicates",
                groups=[
                    {
                        "duplicateId": first_group.get("duplicateId"),
                        "assetIds": aids[:1],
                        "trashIds": aids[1:],
                    }
                ],
            )
            await asyncio.sleep(2)
            asset, _, _, _ = await self.call("get_asset_info", asset_id=aids[1])
            rec(
                "resolve_duplicates",
                (not failed) and asset.get("isTrashed") is True,
                f"kept {aids[0][:8]}, trashed {aids[1][:8]} isTrashed={asset.get('isTrashed')}",
            )
        else:
            rec("resolve_duplicates", False, "SKIPPED: no duplicate groups")

    async def check_credentials(self):
        """Credentials (same creds, must keep working)."""
        data, _, failed, _ = await self.call(
            "update_credentials", base_url=creds["base"], api_key=creds["key"]
        )
        pong, _, failed_again, _ = await self.call("ping")
        rec("update_credentials", (not failed) and (not failed_again), f"{data} then ping={pong}")
        data, _, failed, _ = await self.call(
            "update_credentials", base_url=creds["base"], api_key="bogus-key"
        )
        rec("update_credentials(bad key rejected)", failed, f"bad key -> error={failed} {str(data)[:80]}")
        pong, _, failed_again, _ = await self.call("ping")
        rec("  ping still works after rejected creds", not failed_again, pong)


async def main():
    async with stdio_client(
        StdioServerParameters(command=BIN, args=["--transport", "stdio"], env=env)
    ) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            rec("list_tools", len(names) == 57, f"{len(names)} tools")
            harness = LiveHarness(session)
            await harness.check_health()
            await harness.check_assets_read()
            await harness.check_metadata_write_verify()
            await harness.check_albums()
            await harness.check_thumbnails_json()
            await harness.check_image_blocks()
            await harness.check_video_frames()
            await harness.check_video_granularity()
            await harness.check_pdf_export()
            await harness.check_shared_links()
            await harness.check_tags()
            await harness.check_upload_trash_lifecycle()
            await harness.check_edits()
            await harness.check_ml_smart_search_people()
            await harness.check_credentials()

    covered = {reader["tool"].split("(")[0].strip() for reader in results}
    missing = sorted(set(names) - covered)
    print(
        f"\nSUMMARY {TAG}: {sum(reader['ok'] for reader in results)}/{len(results)} checks passed; tools not covered: {missing}"
    )
    json.dump(
        {"tag": TAG, "results": results, "missing": missing},
        open(f"{os.path.dirname(sys.argv[1])}/harness_{TAG}.json", "w"),
        indent=1,
    )


asyncio.run(main())

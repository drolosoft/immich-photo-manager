"""Exercise every MCP tool of immich-photo-manager (PyPI install) over real stdio MCP against a live Immich."""

import sys
import os
import json
import asyncio
import base64
import tempfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

creds = json.load(open(sys.argv[1]))
TAG = sys.argv[2]
BIN = sys.argv[3]
MEDIA = sys.argv[4]
ALB = creds["album_id"]
IDS = creds["asset_ids"]
X = creds["extra"]
VIDEO = IDS[0]
P1, P2, P3, P4 = IDS[1:5]
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
    results.append({"tool": tool, "ok": bool(ok), "note": str(note)[:220]})
    print(("✅" if ok else "❌"), f"{tool:26s}", str(note)[:160], flush=True)


async def main():
    async with stdio_client(
        StdioServerParameters(command=BIN, args=["--transport", "stdio"], env=env)
    ) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            names = sorted(t.name for t in tools.tools)
            rec("list_tools", len(names) == 53, f"{len(names)} tools")

            async def call(tool, **kw):
                res = await s.call_tool(tool, kw)
                txt = "".join(c.text for c in res.content if getattr(c, "type", "") == "text")
                imgs = [c for c in res.content if getattr(c, "type", "") == "image"]
                data = None
                try:
                    data = json.loads(txt) if txt else None
                except Exception:
                    data = txt
                err = res.isError or (isinstance(data, dict) and "error" in data)
                return data, imgs, err, txt

            def okj(d, e):
                return (not e) and d is not None

            # ── health
            d, _, e, _ = await call("ping")
            rec("ping", okj(d, e), d)
            d, _, e, _ = await call("get_server_version")
            rec("get_server_version", okj(d, e), d)
            d, _, e, _ = await call("get_statistics")
            STATS = d or {}
            rec(
                "get_statistics",
                okj(d, e) and STATS.get("photos") is not None,
                {k: v for k, v in STATS.items() if isinstance(v, (int, float))},
            )
            d, _, e, _ = await call("get_connection_info")
            rec("get_connection_info", okj(d, e), d)

            # ── assets read
            d, _, e, _ = await call("get_asset_info", asset_id=P2)
            city = ((d or {}).get("exifInfo") or {}).get("city") or (d or {}).get("city")
            rec(
                "get_asset_info",
                okj(d, e) and d.get("id") == P2,
                f"file={d.get('originalFileName')} city={city}",
            )
            d, _, e, _ = await call("list_assets", asset_type="VIDEO")
            n = d.get("total") if isinstance(d, dict) else None
            rec("list_assets(type=VIDEO)", okj(d, e) and n == 1, f"total={n}")
            d, _, e, _ = await call("list_assets", page=1, size=100)
            rec(
                "list_assets(all)",
                okj(d, e) and d.get("total") == STATS.get("photos", 0) + STATS.get("videos", 0),
                f"total={d.get('total')} (statistics say {STATS.get('photos', 0) + STATS.get('videos', 0)})",
            )
            d, _, e, _ = await call("search_metadata", make="LabCam")
            rec(
                "search_metadata(make)",
                okj(d, e) and d.get("total") == 4,
                f"total={d.get('total')} (expected 4)",
            )
            d, _, e, _ = await call("search_metadata", city="Lisbon")
            rec(
                "search_metadata(city)",
                okj(d, e) and d.get("total") == 2,
                f"total={d.get('total')} (expected 2)",
            )
            d, _, e, _ = await call(
                "search_metadata",
                taken_after="2026-03-02T00:00:00Z",
                taken_before="2026-03-03T23:59:59Z",
            )
            rec(
                "search_metadata(dates)",
                okj(d, e) and d.get("total") == 2,
                f"total={d.get('total')} (expected 2: 03-02, 03-03)",
            )
            d, _, e, _ = await call("get_map_markers")
            n = len(d) if isinstance(d, list) else (d or {}).get("count", d)
            rec("get_map_markers", okj(d, e), f"{n}")

            # ── metadata write + verify
            d, _, e, _ = await call(
                "update_asset_metadata",
                asset_id=P3,
                description="Tree in Sintra",
                is_favorite=True,
                rating=4,
                latitude=38.8,
                longitude=-9.39,
                date_time_original="2026-03-03T15:00:00.000Z",
            )
            a, _, _, _ = await call("get_asset_info", asset_id=P3)
            ex = a.get("exifInfo") or {}
            rec(
                "update_asset_metadata",
                (not e)
                and ex.get("description") == "Tree in Sintra"
                and a.get("isFavorite") is True
                and ex.get("rating") == 4
                and abs((ex.get("latitude") or 0) - 38.8) < 0.01
                and str(ex.get("dateTimeOriginal", "")).startswith("2026-03-03T15:00"),
                f"desc={ex.get('description')!r} fav={a.get('isFavorite')} rating={ex.get('rating')} lat={ex.get('latitude')} dto={ex.get('dateTimeOriginal')}",
            )
            d, _, e, _ = await call("list_assets", is_favorite=True)
            rec(
                "list_assets(favorite)",
                okj(d, e) and d.get("total") == 1,
                f"total={d.get('total')}",
            )

            # ── albums
            d, _, e, _ = await call("list_albums")
            rec(
                "list_albums",
                okj(d, e)
                and any(
                    a.get("albumName") == "Lab Album"
                    for a in (d if isinstance(d, list) else d.get("albums", []))
                ),
                f"{len(d) if isinstance(d, list) else d.get('count', d.get('total'))} albums",
            )
            d, _, e, _ = await call("get_album", album_id=ALB)
            rec(
                "get_album",
                okj(d, e) and sorted(d.get("asset_ids", [])) == sorted(IDS),
                f"{len(d.get('asset_ids', []))} asset_ids, assetCount={d.get('assetCount')}",
            )
            d, _, e, _ = await call(
                "create_album", name="Harness Album", description="tmp", asset_ids=[P1]
            )
            NEW = (d or {}).get("id")
            rec("create_album", okj(d, e) and NEW, f"id={NEW}")
            d, _, e, _ = await call(
                "update_album", album_id=NEW, name="Harness Album 2", description="updated"
            )
            g, _, _, _ = await call("get_album", album_id=NEW)
            rec(
                "update_album",
                (not e)
                and g.get("albumName") == "Harness Album 2"
                and g.get("description") == "updated",
                f"name={g.get('albumName')} desc={g.get('description')}",
            )
            d, _, e, _ = await call("add_assets_to_album", album_id=NEW, asset_ids=[P2, P3])
            g, _, _, _ = await call("get_album", album_id=NEW)
            rec(
                "add_assets_to_album",
                (not e) and sorted(g["asset_ids"]) == sorted([P1, P2, P3]),
                f"{len(g['asset_ids'])} assets",
            )
            d, _, e, _ = await call("remove_assets_from_album", album_id=NEW, asset_ids=[P2])
            g, _, _, _ = await call("get_album", album_id=NEW)
            rec(
                "remove_assets_from_album",
                (not e) and sorted(g["asset_ids"]) == sorted([P1, P3]),
                f"{len(g['asset_ids'])} assets",
            )

            # ── thumbnails JSON
            d, _, e, _ = await call("get_asset_thumbnail", asset_id=P1, size="thumbnail")
            b = d.get("data") or d.get("thumbnail", {}).get("data") if isinstance(d, dict) else None
            rec(
                "get_asset_thumbnail",
                okj(d, e) and b and base64.b64decode(b)[:4] == b"RIFF",
                f"type={d.get('type')} b64={len(b or '')}",
            )
            d, _, e, _ = await call("get_asset_thumbnail", asset_id=VIDEO, size="preview")
            b = d.get("data") if isinstance(d, dict) else None
            rec(
                "get_asset_thumbnail(video,preview)",
                okj(d, e) and b and base64.b64decode(b)[:2] == b"\xff\xd8",
                f"type={d.get('type')} b64={len(b or '')}",
            )
            d, _, e, _ = await call(
                "get_album_thumbnails", album_id=ALB, size="thumbnail", limit=50
            )
            rec(
                "get_album_thumbnails",
                okj(d, e) and d.get("fetchedCount") == 5,
                f"fetched={d.get('fetchedCount')}/{d.get('totalAssets')}",
            )
            d, _, e, _ = await call(
                "get_thumbnails_batch", asset_ids=[P1, VIDEO, X["einstein.jpg"]], size="thumbnail"
            )
            rec(
                "get_thumbnails_batch",
                okj(d, e)
                and d.get("fetchedCount") == 3
                and d["thumbnails"][0].get("originalFileName"),
                f"fetched={d.get('fetchedCount')} names={[t.get('originalFileName') for t in d.get('thumbnails', [])]}",
            )
            # ── image blocks
            d, imgs, e, _ = await call("get_asset_image", asset_id=P1, size="thumbnail")
            rec(
                "get_asset_image",
                (not e) and len(imgs) == 1 and imgs[0].mimeType.startswith("image/"),
                f"{len(imgs)} image block mime={imgs[0].mimeType if imgs else None} bytes={len(base64.b64decode(imgs[0].data)) if imgs else 0}",
            )
            d, imgs, e, _ = await call("get_album_images", album_id=ALB, size="preview", limit=50)
            rec(
                "get_album_images",
                (not e) and len(imgs) == 5,
                f"{len(imgs)} image blocks mimes={sorted(set(i.mimeType for i in imgs))}",
            )
            d, imgs, e, _ = await call(
                "get_images_batch", asset_ids=[P1, P2, VIDEO], size="thumbnail"
            )
            rec("get_images_batch", (not e) and len(imgs) == 3, f"{len(imgs)} image blocks")

            # ── shared links
            d, _, e, _ = await call(
                "create_shared_link",
                album_id=ALB,
                allow_download=True,
                show_metadata=True,
                description="lab share",
            )
            LINK = (d or {}).get("id")
            KEY = (d or {}).get("key")
            URL = (d or {}).get("url")
            rec("create_shared_link", okj(d, e) and LINK and KEY, f"url={URL}")
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
            except Exception as ex:
                rec("  shared link public GET", False, repr(ex)[:100])
            d, _, e, _ = await call("list_shared_links")
            rec(
                "list_shared_links",
                okj(d, e)
                and any(
                    lnk.get("id") == LINK
                    for lnk in (
                        d if isinstance(d, list) else d.get("links", d.get("shared_links", []))
                    )
                ),
                f"{len(d) if isinstance(d, list) else d}",
            )
            d, _, e, _ = await call("get_shared_link", link_id=LINK)
            rec(
                "get_shared_link", okj(d, e) and d.get("id") == LINK, f"desc={d.get('description')}"
            )
            d, _, e, _ = await call(
                "update_shared_link",
                link_id=LINK,
                allow_download=False,
                description="lab share 2",
                expiry_at="2027-01-01T00:00:00.000Z",
            )
            g, _, _, _ = await call("get_shared_link", link_id=LINK)
            rec(
                "update_shared_link",
                (not e)
                and g.get("allowDownload") is False
                and g.get("description") == "lab share 2"
                and str(g.get("expiresAt", "")).startswith("2027"),
                f"allowDownload={g.get('allowDownload')} desc={g.get('description')} expires={g.get('expiresAt')}",
            )
            d, _, e, _ = await call("delete_shared_link", link_id=LINK)
            g, _, e2, _ = await call("get_shared_link", link_id=LINK)
            rec("delete_shared_link", (not e) and e2, f"after delete: get -> error={e2}")

            # ── tags (clean leftovers from earlier runs first)
            lt, _, _, _ = await call("list_tags")
            for t in lt if isinstance(lt, list) else lt.get("tags", []):
                if t.get("name") == "harness-tag":
                    await call("delete_tag", tag_id=t["id"])
            d, _, e, _ = await call("create_tag", name="harness-tag", color="#ff0000")
            TID = (d or {}).get("id")
            rec("create_tag", okj(d, e) and TID, f"id={TID} {str(d)[:100] if not TID else ''}")
            if not TID:
                lt, _, _, _ = await call("list_tags")
                TID = next(
                    (
                        t["id"]
                        for t in (lt if isinstance(lt, list) else lt.get("tags", []))
                        if t.get("name") == "harness-tag"
                    ),
                    None,
                )
            d, _, e, _ = await call("list_tags")
            rec(
                "list_tags",
                okj(d, e)
                and any(
                    t.get("name") == "harness-tag"
                    for t in (d if isinstance(d, list) else d.get("tags", []))
                ),
                f"{len(d) if isinstance(d, list) else d.get('count')} tags",
            )
            d, _, e, _ = await call("get_tag", tag_id=TID)
            rec("get_tag", okj(d, e) and d.get("name") == "harness-tag", f"color={d.get('color')}")
            d, _, e, _ = await call("update_tag", tag_id=TID, name="harness-tag-2")
            rec("update_tag(name -> clear error)", e and "rename" in str(d).lower(), str(d)[:120])
            d, _, e, _ = await call("update_tag", tag_id=TID, color="#00ff00")
            g, _, _, _ = await call("get_tag", tag_id=TID)
            rec(
                "update_tag(color)",
                (not e) and str(g.get("color", "")).lower() == "#00ff00",
                f"color={g.get('color')}",
            )
            d, _, e, _ = await call("tag_assets", tag_id=TID, asset_ids=[P1, P2])
            a, _, _, _ = await call("get_asset_info", asset_id=P1)
            tn = [t.get("name") for t in a.get("tags", [])]
            rec("tag_assets", (not e) and "harness-tag" in tn, f"asset tags={tn}")
            d, _, e, _ = await call("untag_assets", tag_id=TID, asset_ids=[P1])
            a, _, _, _ = await call("get_asset_info", asset_id=P1)
            tn = [t.get("name") for t in a.get("tags", [])]
            rec("untag_assets", (not e) and "harness-tag" not in tn, f"asset tags={tn}")
            d, _, e, _ = await call("delete_tag", tag_id=TID)
            g, _, e2, _ = await call("get_tag", tag_id=TID)
            rec("delete_tag", (not e) and e2, f"after delete: error={e2}")

            # ── upload / trash lifecycle
            d, _, e, _ = await call(
                "upload_asset", file_path=os.path.join(MEDIA, "upload_test.jpg"), album_id=NEW
            )
            UP = (d or {}).get("id") or (d or {}).get("asset_id")
            rec(
                "upload_asset",
                okj(d, e) and UP and (d or {}).get("status") == "created",
                f"{ {k: v for k, v in (d or {}).items() if k != 'raw'} }",
            )
            g, _, _, _ = await call("get_album", album_id=NEW)
            rec(
                "  upload landed in album",
                UP in g.get("asset_ids", []),
                f"album has {len(g.get('asset_ids', []))}",
            )
            d, _, e, _ = await call("delete_assets", asset_ids=[UP])
            t, _, _, _ = await call("list_assets", is_trashed=True)
            tr = (
                [a.get("id") for a in t.get("assets", t.get("items", []))]
                if isinstance(t, dict)
                else []
            )
            rec(
                "delete_assets(soft) + list_assets(is_trashed)",
                (not e) and UP in tr and t.get("total") == 1,
                f"trashed total={t.get('total')} contains={UP in tr}",
            )
            d, _, e, _ = await call("restore_assets", asset_ids=[UP])
            a, _, e2, _ = await call("get_asset_info", asset_id=UP)
            rec(
                "restore_assets",
                (not e) and (not e2) and not a.get("isTrashed"),
                f"isTrashed={a.get('isTrashed')}",
            )
            d, _, e, _ = await call("delete_assets", asset_ids=[UP])
            d2, _, e2, _ = await call("restore_trash")
            a, _, _, _ = await call("get_asset_info", asset_id=UP)
            rec(
                "restore_trash",
                (not e) and (not e2) and not a.get("isTrashed"),
                f"isTrashed={a.get('isTrashed')}",
            )
            d, _, e, _ = await call("delete_assets", asset_ids=[UP])
            d2, _, e2, _ = await call("empty_trash")
            await asyncio.sleep(3)
            a, _, e3, _ = await call("get_asset_info", asset_id=UP)
            rec(
                "empty_trash",
                (not e) and (not e2) and (e3 or a.get("isTrashed") or not a.get("id")),
                f"asset after empty_trash: error={e3} isTrashed={a.get('isTrashed') if isinstance(a, dict) else a}",
            )
            u2, _, _, _ = await call(
                "upload_asset", file_path=os.path.join(MEDIA, "upload_test2.jpg")
            )
            U2 = (u2 or {}).get("id")
            d, _, e, _ = await call("delete_assets", asset_ids=[U2], force=True)
            await asyncio.sleep(2)
            a, _, e2, _ = await call("get_asset_info", asset_id=U2)
            rec(
                "delete_assets(force)",
                (not e) and e2,
                f"uploaded {str(U2)[:8]} then force-deleted: get -> error={e2}",
            )
            d, _, e, _ = await call("delete_album", album_id=NEW)
            g, _, e2, _ = await call("get_album", album_id=NEW)
            rec("delete_album", (not e) and e2, f"after delete error={e2}")

            # ── edits
            d, _, e, _ = await call("rotate_assets", angle=90, asset_ids=[P1])
            rec("rotate_assets(ids)", okj(d, e) and d.get("rotated") == 1, d)
            d, _, e, _ = await call("rotate_assets", angle=90, album_id=ALB)
            rec(
                "rotate_assets(album)",
                okj(d, e) and d.get("rotated") == 4 and d.get("failed") == 1,
                f"rotated={d.get('rotated')} failed={d.get('failed')} (video expected to fail: Immich 'Only images can be edited')",
            )
            d, _, e, _ = await call("revert_asset_edits", asset_ids=[P1])
            rec("revert_asset_edits(ids)", okj(d, e), d)
            d, _, e, _ = await call("revert_asset_edits", album_id=ALB)
            rec("revert_asset_edits(album)", okj(d, e), d)

            # ── ML: smart search, people, duplicates
            d, _, e, _ = await call("search_smart", query="portrait of a man with a beard", size=5)
            items = d.get("assets", d.get("results", [])) if isinstance(d, dict) else []
            top = [a.get("originalFileName") for a in items[:3]]
            rec(
                "search_smart",
                okj(d, e) and any("lincoln" in (n or "") or "einstein" in (n or "") for n in top),
                f"top3={top}",
            )
            d, _, e, _ = await call("search_smart", query="boat", city="Senhora do Porto", size=5)
            rec(
                "search_smart(+city filter)",
                okj(d, e),
                f"total={d.get('total') if isinstance(d, dict) else d}",
            )
            d, _, e, _ = await call("list_people", with_hidden=True)
            people = d.get("people", d) if isinstance(d, dict) else d
            ppl = people if isinstance(people, list) else []
            rec(
                "list_people",
                okj(d, e) and len(ppl) >= 1,
                f"{len(ppl)} people total={d.get('total') if isinstance(d, dict) else ''}",
            )
            PID = ppl[0]["id"] if ppl else None
            if PID:
                d, _, e, _ = await call("get_person", person_id=PID)
                rec("get_person", okj(d, e) and d.get("id") == PID, f"name={d.get('name')!r}")
                d, _, e, _ = await call(
                    "update_person",
                    person_id=PID,
                    name="Abe",
                    birth_date="1809-02-12",
                    is_favorite=True,
                )
                g, _, _, _ = await call("get_person", person_id=PID)
                rec(
                    "update_person",
                    (not e)
                    and g.get("name") == "Abe"
                    and str(g.get("birthDate", "")).startswith("1809-02-12"),
                    f"name={g.get('name')} birth={g.get('birthDate')} fav={g.get('isFavorite')}",
                )
                d, _, e, _ = await call("search_people", name="Abe")
                sp = d if isinstance(d, list) else d.get("people", [])
                rec(
                    "search_people",
                    okj(d, e) and any(p.get("id") == PID for p in sp),
                    f"{len(sp)} hits",
                )
                d, _, e, _ = await call("get_person_thumbnail", person_id=PID)
                b = d.get("data") if isinstance(d, dict) else None
                rec("get_person_thumbnail", okj(d, e) and b, f"b64={len(b or '')}")
                d, _, e, _ = await call("get_asset_faces", asset_id=X["lincoln1.jpg"])
                faces = d if isinstance(d, list) else d.get("faces", [])
                rec(
                    "get_asset_faces",
                    okj(d, e) and len(faces) >= 1,
                    f"{len(faces)} faces on lincoln1, person={faces[0].get('person', {}).get('id') if faces and faces[0].get('person') else None}",
                )
                FID = faces[0].get("id") if faces else None
                others = [p["id"] for p in ppl if p["id"] != PID]
                for fn in (
                    "einstein.jpg",
                    "obama.jpg",
                    "curie.jpg",
                ):  # Immich 3.x hides 1-face people from /people; find them via faces
                    fz, _, _, _ = await call("get_asset_faces", asset_id=X[fn])
                    fz = fz if isinstance(fz, list) else fz.get("faces", [])
                    for f in fz:
                        pid2 = (f.get("person") or {}).get("id")
                        if pid2 and pid2 != PID and pid2 not in others:
                            others.append(pid2)
                if FID and others:
                    d, _, e, _ = await call("reassign_face", face_id=FID, person_id=others[0])
                    f2, _, _, _ = await call("get_asset_faces", asset_id=X["lincoln1.jpg"])
                    f2 = f2 if isinstance(f2, list) else f2.get("faces", [])
                    now = (f2[0].get("person") or {}).get("id") if f2 else None
                    rec(
                        "reassign_face",
                        (not e) and now == others[0],
                        f"face {FID[:8]} -> person {others[0][:8]}; now belongs to {str(now)[:8]}",
                    )
                    d, _, e, _ = await call("reassign_face", face_id=FID, person_id=PID)
                    rec("reassign_face(back)", okj(d, e), "restored")
                else:
                    rec(
                        "reassign_face",
                        False,
                        f"SKIPPED: faces={bool(FID)} other_people={len(others)}",
                    )
                if len(others) >= 1:
                    d, _, e, _ = await call("merge_people", person_id=PID, merge_ids=[others[-1]])
                    g, _, e2, _ = await call("get_person", person_id=others[-1])
                    rec(
                        "merge_people",
                        (not e) and e2,
                        f"merged {others[-1][:8]} into {PID[:8]}; merged person gone={e2}",
                    )
                else:
                    rec("merge_people", False, "SKIPPED: only one person detected")
            else:
                for t in (
                    "get_person",
                    "update_person",
                    "search_people",
                    "get_person_thumbnail",
                    "get_asset_faces",
                    "merge_people",
                    "reassign_face",
                ):
                    rec(t, False, "SKIPPED: no people detected (ML)")
            d, _, e, _ = await call("get_duplicates")
            groups = d if isinstance(d, list) else d.get("groups", d.get("duplicates", []))
            rec(
                "get_duplicates",
                okj(d, e) and len(groups) >= 1,
                f"{len(groups)} groups: {[[a.get('originalFileName') for a in g.get('assets', [])] for g in groups][:2]}",
            )
            if groups:
                g0 = groups[0]
                aids = [a["id"] for a in g0.get("assets", [])]
                d, _, e, _ = await call(
                    "resolve_duplicates",
                    groups=[
                        {
                            "duplicateId": g0.get("duplicateId"),
                            "assetIds": aids[:1],
                            "trashIds": aids[1:],
                        }
                    ],
                )
                await asyncio.sleep(2)
                a, _, _, _ = await call("get_asset_info", asset_id=aids[1])
                rec(
                    "resolve_duplicates",
                    (not e) and a.get("isTrashed") is True,
                    f"kept {aids[0][:8]}, trashed {aids[1][:8]} isTrashed={a.get('isTrashed')}",
                )
            else:
                rec("resolve_duplicates", False, "SKIPPED: no duplicate groups")

            # ── credentials (same creds, must keep working)
            d, _, e, _ = await call(
                "update_credentials", base_url=creds["base"], api_key=creds["key"]
            )
            p, _, e2, _ = await call("ping")
            rec("update_credentials", (not e) and (not e2), f"{d} then ping={p}")
            d, _, e, _ = await call(
                "update_credentials", base_url=creds["base"], api_key="bogus-key"
            )
            rec("update_credentials(bad key rejected)", e, f"bad key -> error={e} {str(d)[:80]}")
            p, _, e2, _ = await call("ping")
            rec("  ping still works after rejected creds", not e2, p)

    covered = {r["tool"].split("(")[0].strip() for r in results}
    missing = sorted(set(names) - covered)
    print(
        f"\nSUMMARY {TAG}: {sum(r['ok'] for r in results)}/{len(results)} checks passed; tools not covered: {missing}"
    )
    json.dump(
        {"tag": TAG, "results": results, "missing": missing},
        open(f"{os.path.dirname(sys.argv[1])}/harness_{TAG}.json", "w"),
        indent=1,
    )


asyncio.run(main())

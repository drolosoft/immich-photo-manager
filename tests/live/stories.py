"""Record real MCP transcripts of the newer immich-photo-manager tools, story by story.

The live harness next door proves that every tool works. This script has a
different job: it drives the published binary over stdio MCP against a real
Immich and writes down what actually came back, so the public documentation can
quote transcripts instead of hand-written examples. Each story is a short
sequence of calls a person would really make, and each call lands in the
Markdown file for its story with its arguments, its (trimmed) answer and how
long it took.

Usage: stories.py <creds.json> <v2|v3> <path/to/immich-photo-manager> <output dir>
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

creds = json.load(open(sys.argv[1]))
TAG = sys.argv[2]
BIN = sys.argv[3]
OUT_DIR = sys.argv[4]
ALBUM = creds["album_id"]
IDS = creds["asset_ids"]
VIDEO = IDS[0]
PHOTO1, PHOTO2, PHOTO3, PHOTO4 = IDS[1:5]

# The plugin keeps its per-asset notes and its thumbnail cache under this
# directory. A throwaway one per run keeps story (e) honest: the notes it reads
# back are the ones it just wrote, never leftovers from an earlier run.
cache_dir = tempfile.mkdtemp(prefix=f"immich-stories-{TAG}-")

env = {
    **os.environ,
    "IMMICH_BASE_URL": creds["base"],
    "IMMICH_API_KEY": creds["key"],
    "IMMICH_CACHE_DIR": cache_dir,
    "MCP_TRANSPORT": "stdio",
}

# Long JSON answers are cut at this many characters in the transcript. It is
# enough to show the shape of a result and a few real rows without turning a
# demo page into a data dump.
RESULT_LIMIT = 1200

# The OCR job runs in the background after an upload, so the text search cannot
# hit immediately. These bound the polling: give up after roughly a minute.
OCR_POLL_ATTEMPTS = 12
OCR_POLL_SECONDS = 5


def api_headers() -> dict:
    """Return the admin headers for the few calls that bypass MCP on purpose."""
    return {"x-api-key": creds["key"]}


class StoryRecorder:
    """Runs the stories over one MCP session and remembers every recorded call.

    Calls made while setting a scene up (polling for an OCR result, putting a
    rating back) go through `call` with `record=False`, so the transcript keeps
    only the steps a reader is meant to follow.
    """

    def __init__(self, session):
        self.session = session
        self.stories = []
        self.current = None

    def start(self, name: str, blurb: str) -> None:
        """Open a new story; every later `call` is filed under it."""
        self.current = {"name": name, "blurb": blurb, "calls": []}
        self.stories.append(self.current)
        print(f"\n=== {name} ===", flush=True)

    async def call(self, tool: str, record: bool = True, **arguments):
        """Call one tool, time it, and file the transcript entry.

        Returns the parsed JSON (or raw text when the answer is not JSON) plus
        a flag saying whether the call failed, the same contract the live
        harness uses.
        """
        started = time.monotonic()
        failed = False
        raw = ""
        try:
            result = await self.session.call_tool(tool, arguments)
            raw = "".join(
                content.text for content in result.content if getattr(content, "type", "") == "text"
            )
            failed = bool(result.is_error)
        except Exception as exc:
            raw = f"EXCEPTION: {exc!r}"
            failed = True
        elapsed_ms = int((time.monotonic() - started) * 1000)

        data = raw
        try:
            data = json.loads(raw) if raw else None
        except ValueError:
            data = raw
        # The server reports tool-level problems as a JSON body with an "error"
        # key rather than as a protocol error, so both have to count as failure.
        if isinstance(data, dict) and "error" in data:
            failed = True

        if record:
            self.current["calls"].append(
                {
                    "tool": tool,
                    "arguments": arguments,
                    "result": data if data is not None else raw,
                    "elapsed_ms": elapsed_ms,
                    "ok": not failed,
                }
            )
            print(("ok  " if not failed else "FAIL"), f"{tool:26s} {elapsed_ms:6d} ms", flush=True)
        return data, failed

    async def know_your_library(self):
        """Story (a): the first questions anyone asks a library they just connected."""
        self.start(
            "know-your-library",
            "What is in here? The tools that answer before you know what to search for.",
        )
        await self.call("get_capabilities")
        await self.call("search_explore")
        await self.call("search_cities")
        await self.call("search_suggestions", type="city")
        await self.call("search_statistics", make="LabCam")
        await self.call("search_random", size=3)

        buckets, _ = await self.call("get_timeline_buckets")
        rows = buckets.get("buckets", []) if isinstance(buckets, dict) else []
        # The timeline is newest first, so the first bucket is the month the
        # library was last added to. That is the one worth opening in a demo.
        first_bucket = rows[0]["timeBucket"] if rows else ""
        await self.call("get_timeline_bucket", time_bucket=first_bucket)
        await self.call("get_calendar_heatmap", from_date="2026-01-01", to_date="2026-12-31")

    async def search_that_finds(self):
        """Story (b): the searches that go past filenames, ending with real OCR."""
        self.start(
            "search-that-finds",
            "Album, face, place, coordinates and the text printed inside a photo.",
        )
        await self.call("search_metadata", album_ids=[ALBUM])

        people, _ = await self.call("list_people")
        listed = people.get("people", []) if isinstance(people, dict) else []
        if listed:
            await self.call("search_metadata", person_ids=[listed[0]["id"]])
        else:
            print("no people detected, skipping the person search", flush=True)

        await self.call("search_places", name="Lisbon")
        await self.call("reverse_geocode", lat=38.7223, lon=-9.1393)
        await self.ocr_scene()

    async def ocr_scene(self):
        """Upload a photo with printed text, let Immich read it, then search for it."""
        ticket_path = os.path.join(cache_dir, "boarding-pass.jpg")
        make_text_image(ticket_path, ["BOARDING PASS", "GATE B42", "SEAT 17A"])
        asset_id = upload_asset(ticket_path)
        if not asset_id:
            print("upload of the OCR sample failed, skipping the OCR search", flush=True)
            return

        # Immich only reads text when the OCR job runs, and a fresh upload is
        # not enough on its own, so ask for a forced pass over the library.
        started = httpx.put(
            f"{creds['base']}/api/jobs/ocr",
            headers=api_headers(),
            json={"command": "start", "force": True},
            timeout=60,
        )
        print(f"ocr job start -> HTTP {started.status_code}", flush=True)

        # Poll off the record until the text shows up, then make the one call
        # that goes into the transcript.
        for _attempt in range(OCR_POLL_ATTEMPTS):
            await asyncio.sleep(OCR_POLL_SECONDS)
            probe, failed = await self.call(
                "search_metadata", record=False, ocr="boarding pass"
            )
            if not failed and isinstance(probe, dict) and probe.get("total", 0) > 0:
                break
        await self.call("search_metadata", ocr="boarding pass")

        delete_asset(asset_id)

    async def memories_and_stacks(self):
        """Story (c): the two grouping features Immich 1.x users keep asking for."""
        self.start(
            "memories-and-stacks",
            "Build a memory for a date, then stack two shots of the same thing.",
        )
        today = time.strftime("%Y-%m-%d")
        memory, _ = await self.call(
            "create_memory",
            memory_at=f"{today}T00:00:00Z",
            year=2020,
            asset_ids=[PHOTO1, PHOTO2],
        )
        memory_id = memory.get("id") if isinstance(memory, dict) else None
        await self.call("list_memories")
        if memory_id:
            await self.call("update_memory", memory_id=memory_id, is_saved=True)
            await self.call("delete_memory", memory_id=memory_id)

        stack, _ = await self.call("create_stack", asset_ids=[PHOTO1, PHOTO2])
        stack_id = stack.get("id") if isinstance(stack, dict) else None
        await self.call("list_stacks")
        if stack_id:
            await self.call("update_stack", stack_id=stack_id, primary_asset_id=PHOTO2)
            await self.call("delete_stack", stack_id=stack_id)
        # Dissolving a stack must not take the photos with it, and that is the
        # single most reassuring line of the whole story.
        await self.call("get_asset_info", asset_id=PHOTO2)

    async def family_and_sharing(self):
        """Story (d): the library seen by more than one person, and taken home as a zip."""
        self.start(
            "family-and-sharing",
            "Share with a partner, talk about an album, then download the whole thing.",
        )
        ensure_partner_user()

        users, _ = await self.call("list_users")
        listed = users.get("users", []) if isinstance(users, dict) else []
        partner = next(
            (user for user in listed if user.get("email") == "partner@example.com"), None
        )
        partner_id = (partner or {}).get("id")
        if partner_id:
            # A crashed run can leave the share in place, which would make
            # create_partner answer with a duplicate error instead of a story.
            httpx.delete(
                f"{creds['base']}/api/partners/{partner_id}", headers=api_headers(), timeout=30
            )
            await self.call("create_partner", user_id=partner_id)
            await self.call("list_partners")
            await self.call("remove_partner", user_id=partner_id)
        else:
            print("no partner user available, skipping the partner calls", flush=True)

        activity, _ = await self.call(
            "create_activity", album_id=ALBUM, comment="Let us print this one for the wall"
        )
        activity_id = activity.get("id") if isinstance(activity, dict) else None
        await self.call("list_activities", album_id=ALBUM)
        if activity_id:
            await self.call("delete_activity", activity_id=activity_id)

        await self.call("get_download_info", album_id=ALBUM)
        zip_path = os.path.join(cache_dir, f"lab-album-{TAG}.zip")
        archive, failed = await self.call(
            "download_archive", album_id=ALBUM, output_path=zip_path
        )
        if not failed and os.path.exists(zip_path):
            with zipfile.ZipFile(zip_path) as bundle:
                names = bundle.namelist()
            print(f"zip holds {len(names)} files: {names}", flush=True)
            self.current["calls"][-1]["note"] = (
                f"The saved zip opens with {len(names)} files inside: {', '.join(sorted(names))}."
            )
            os.remove(zip_path)

    async def the_plugin_remembers(self):
        """Story (e): the notes the plugin keeps for itself between conversations."""
        self.start(
            "the-plugin-remembers",
            "Verdicts and actions written down now, read back in the next session.",
        )
        await self.call(
            "review_assets",
            asset_ids=[PHOTO3, PHOTO4],
            verdict="delete_candidate",
            reason="near-identical framing, keep only the sharper one",
        )
        await self.call(
            "record_action",
            asset_ids=[PHOTO3],
            action="trashed",
            detail="moved to trash after the review above",
        )
        await self.call("get_assets_notes", asset_ids=IDS)
        await self.call("get_asset_info", asset_id=PHOTO3, with_notes=True)
        await self.call("clear_asset_notes", asset_ids=[PHOTO3, PHOTO4])

    async def bulk_and_gates(self):
        """Story (f): one call for many assets, and a destructive call that stops to ask."""
        self.start(
            "bulk-and-gates",
            "Rate a batch in one call; ask to merge two people and get a preview instead.",
        )
        await self.call("update_assets_metadata", asset_ids=[PHOTO1, PHOTO2], rating=4)
        await self.call("get_asset_info", asset_id=PHOTO1)

        pair = await self.find_two_people()
        if pair:
            await self.call("merge_people", person_id=pair[0], merge_ids=[pair[1]])
        else:
            print("fewer than two people detected, skipping the merge preview", flush=True)

        restore_rating(IDS[1:3])

    async def find_two_people(self) -> list[str]:
        """Find two person ids to show the merge gate with, off the record.

        Immich 3.x leaves people who own a single face out of the /people
        listing even though it still counts them in the total, so on that
        version the second person has to be reached through the faces of a
        photo instead. Both lookups stay out of the transcript: they are how
        the script finds real ids, not part of the story being told.
        """
        people, _ = await self.call("list_people", record=False, with_hidden=True)
        listed = people.get("people", []) if isinstance(people, dict) else []
        found = [person["id"] for person in listed]

        for filename in ("einstein.jpg", "curie.jpg", "roosevelt.jpg"):
            if len(found) >= 2:
                break
            if filename not in creds["extra"]:
                continue
            faces, _ = await self.call(
                "get_asset_faces", record=False, asset_id=creds["extra"][filename]
            )
            rows = faces if isinstance(faces, list) else (faces or {}).get("faces", [])
            for face in rows:
                person_id = (face.get("person") or {}).get("id")
                if person_id and person_id not in found:
                    found.append(person_id)
        return found[:2] if len(found) >= 2 else []


def make_text_image(path: str, lines: list[str]) -> None:
    """Write a JPEG carrying large printed text, the kind OCR is meant to read."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1400, 800), "white")
    canvas = ImageDraw.Draw(image)
    # Pillow's bundled default font is tiny; ask for a real face at a readable
    # size and fall back only if the machine has none of them.
    font = None
    for candidate in ("/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"):
        if os.path.exists(candidate):
            font = ImageFont.truetype(candidate, 110)
            break
    if font is None:
        font = ImageFont.load_default()

    top = 120
    for line in lines:
        canvas.text((100, top), line, fill="black", font=font)
        top += 180
    image.save(path, "JPEG", quality=92)


def upload_asset(path: str) -> str:
    """Upload one file straight to the API and return its asset id, or an empty string.

    The plugin has an upload tool, but this photo is scaffolding for the OCR
    story rather than part of it, so it goes over plain HTTP like the partner
    user does.
    """
    stamp = "2026-06-01T09:00:00.000Z"
    with open(path, "rb") as handle:
        response = httpx.post(
            f"{creds['base']}/api/assets",
            headers=api_headers(),
            files={"assetData": (os.path.basename(path), handle, "image/jpeg")},
            data={
                "deviceAssetId": f"stories-{TAG}-boarding-pass",
                "deviceId": "stories-script",
                "fileCreatedAt": stamp,
                "fileModifiedAt": stamp,
            },
            timeout=120,
        )
    if response.status_code not in (200, 201):
        print(f"upload failed: HTTP {response.status_code} {response.text[:200]}", flush=True)
        return ""
    return response.json().get("id", "")


def delete_asset(asset_id: str) -> None:
    """Remove an asset for good so the lab ends the run exactly as it started."""
    response = httpx.request(
        "DELETE",
        f"{creds['base']}/api/assets",
        headers=api_headers(),
        json={"ids": [asset_id], "force": True},
        timeout=60,
    )
    print(f"cleanup delete {asset_id[:8]} -> HTTP {response.status_code}", flush=True)


def restore_rating(asset_ids: list[str]) -> None:
    """Put the rated photos back to unrated so the next run starts from the same library.

    This one cannot go through `update_assets_metadata`: its rating parameter
    treats None as "leave alone", and Immich 3.x rejects a rating of 0 outright
    (only -1, 1 to 5 or null are valid), so clearing a rating has to be a null
    on the wire.
    """
    response = httpx.put(
        f"{creds['base']}/api/assets",
        headers=api_headers(),
        json={"ids": asset_ids, "rating": None},
        timeout=30,
    )
    print(f"cleanup rating reset -> HTTP {response.status_code}", flush=True)


def ensure_partner_user() -> None:
    """Make sure a second account exists, since a partner story needs somebody to share with."""
    response = httpx.post(
        f"{creds['base']}/api/admin/users",
        headers=api_headers(),
        json={
            "email": "partner@example.com",
            "name": "Lab Partner",
            "password": "labpartner1",
        },
        timeout=30,
    )
    # A 400 is the expected answer on every run after the first: the account is
    # already there, which is exactly what this function wanted.
    if response.status_code not in (200, 201, 400):
        print(f"partner user setup: HTTP {response.status_code} {response.text[:200]}", flush=True)


def as_block(value) -> str:
    """Render one argument set or result as the JSON that goes in a fenced block."""
    if isinstance(value, str):
        return value
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    if len(text) > RESULT_LIMIT:
        text = text[:RESULT_LIMIT].rstrip() + "\n... (trimmed)"
    return text


def write_story(story: dict, directory: str) -> None:
    """Write one story to its own Markdown file, one section per call."""
    lines = [f"# {story['name']} ({TAG})", "", story["blurb"], ""]
    lines += [
        f"Immich {creds['version']['major']}.{creds['version']['minor']}."
        f"{creds['version']['patch']} at `{creds['base']}`, "
        f"{len(story['calls'])} calls.",
        "",
    ]
    for number, entry in enumerate(story["calls"], start=1):
        status = "" if entry["ok"] else " (failed)"
        lines += [f"## {number}. `{entry['tool']}`{status}", ""]
        lines += ["Arguments:", "", "```json", as_block(entry["arguments"]), "```", ""]
        lines += ["Result:", "", "```json", as_block(entry["result"]), "```", ""]
        if entry.get("note"):
            lines += [entry["note"], ""]
        lines += [f"_{entry['elapsed_ms']} ms_", ""]
    path = os.path.join(directory, f"{story['name']}.md")
    with open(path, "w") as handle:
        handle.write("\n".join(lines))
    print(f"wrote {path}", flush=True)


async def main():
    """Drive every story over one MCP session, then write the transcripts out."""
    async with stdio_client(
        StdioServerParameters(command=BIN, args=["--transport", "stdio"], env=env)
    ) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            recorder = StoryRecorder(session)
            await recorder.know_your_library()
            await recorder.search_that_finds()
            await recorder.memories_and_stacks()
            await recorder.family_and_sharing()
            await recorder.the_plugin_remembers()
            await recorder.bulk_and_gates()

    directory = os.path.join(OUT_DIR, "stories", TAG)
    os.makedirs(directory, exist_ok=True)
    summary = {"tag": TAG, "base": creds["base"], "stories": []}
    passed = 0
    total = 0
    for story in recorder.stories:
        write_story(story, directory)
        summary["stories"].append(
            {
                "name": story["name"],
                "calls": [
                    {"tool": entry["tool"], "ok": entry["ok"], "elapsed_ms": entry["elapsed_ms"]}
                    for entry in story["calls"]
                ],
            }
        )
        passed += sum(entry["ok"] for entry in story["calls"])
        total += len(story["calls"])
    summary["passed"] = passed
    summary["total"] = total
    with open(os.path.join(directory, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=1)

    failures = [
        f"{story['name']}/{entry['tool']}"
        for story in recorder.stories
        for entry in story["calls"]
        if not entry["ok"]
    ]
    print(f"\nSUMMARY {TAG}: {passed}/{total} calls succeeded; failures: {failures}")
    shutil.rmtree(cache_dir, ignore_errors=True)


asyncio.run(main())

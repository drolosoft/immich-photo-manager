#!/usr/bin/env python3
"""Smoke-test the packaged server against a REAL Immich, on both MCP eras.

Boots `python -m immich_mcp_server --transport stdio` as a subprocess (the exact
thing Claude Desktop / Claude Code launch) and drives it twice: forcing the
legacy `initialize` handshake, and pinning the stateless 2026-07-28 revision.
Optionally also hits an already-running HTTP server (--http URL).

Read-only: it only calls ping / statistics / list_albums / search_metadata /
thumbnails. Nothing is created, edited, or deleted.

Usage:
    IMMICH_BASE_URL=https://fotos.example.com IMMICH_API_KEY=... \
        python scripts/smoke-both-eras.py [--http http://127.0.0.1:8626/mcp]

Exit code 0 = every check passed on every era/transport; 1 otherwise.
"""

import argparse
import asyncio
import base64
import json
import os
import sys

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters, stdio_client

MODES = ["legacy", "2026-07-28"]
EXPECTED_TOOLS = 57
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def _stdio():
    env = {**os.environ, "PYTHONPATH": SRC + os.pathsep + os.environ.get("PYTHONPATH", "")}
    return stdio_client(StdioServerParameters(
        command=sys.executable, args=["-m", "immich_mcp_server", "--transport", "stdio"], env=env))


async def _json(client, name, args=None):
    r = await client.call_tool(name, args or {})
    if r.is_error:
        raise RuntimeError(f"{name} returned is_error: {r.content}")
    return json.loads(next(b.text for b in r.content if b.type == "text"))


async def check(client, label):
    ok = True

    def report(name, passed, detail=""):
        nonlocal ok
        ok &= passed
        print(f"  [{label}] {'✅' if passed else '❌'} {name} {detail}")

    tools = await client.list_tools()
    report("tools/list", len(tools.tools) == EXPECTED_TOOLS, f"({len(tools.tools)} tools)")

    ping = await _json(client, "ping")
    report("ping", ping.get("res") == "pong", json.dumps(ping))

    stats = await _json(client, "get_statistics")
    report("get_statistics", "photos" in stats, f"photos={stats.get('photos')} videos={stats.get('videos')}")

    albums = await _json(client, "list_albums")
    report("list_albums", isinstance(albums.get("albums"), list), f"({albums.get('total')} albums)")

    # find a couple of real assets to pull thumbnails for
    found = await _json(client, "search_metadata", {"size": 2})
    ids = [a["id"] for a in found.get("assets", [])][:2]
    report("search_metadata", bool(ids), f"ids={ids}")
    if not ids:
        return ok

    batch = await _json(client, "get_thumbnails_batch", {"asset_ids": ids, "size": "thumbnail"})
    thumbs = batch.get("thumbnails", [])
    decodable = all(len(base64.b64decode(t["data"])) > 50 for t in thumbs)
    has_meta = all(t.get("id") and "originalFileName" in t and "fileCreatedAt" in t for t in thumbs)
    report("get_thumbnails_batch (base64 JSON, skills contract)", len(thumbs) == len(ids) and decodable and has_meta,
           f"({len(thumbs)} thumbs, types={sorted({t['type'] for t in thumbs})})")

    r = await client.call_tool("get_asset_image", {"asset_id": ids[0]})
    img = next((b for b in r.content if b.type == "image"), None)
    report("get_asset_image (image block)", img is not None and len(base64.b64decode(img.data)) > 50,
           f"(mime={getattr(img, 'mime_type', None)})")
    return ok


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", help="URL of an already-running HTTP server, e.g. http://127.0.0.1:8626/mcp")
    args = ap.parse_args()
    if not os.environ.get("IMMICH_BASE_URL") or not os.environ.get("IMMICH_API_KEY"):
        sys.exit("set IMMICH_BASE_URL and IMMICH_API_KEY")

    all_ok = True
    for mode in MODES:
        async with Client(_stdio(), mode=mode) as c:
            print(f"\nstdio  mode={mode!r} -> negotiated {c.protocol_version}")
            all_ok &= await check(c, f"stdio/{mode}")
    if args.http:
        for mode in MODES + ["auto"]:
            async with Client(args.http, mode=mode) as c:
                print(f"\nhttp   mode={mode!r} -> negotiated {c.protocol_version}")
                all_ok &= await check(c, f"http/{mode}")

    print("\nRESULT:", "ALL GREEN ✅" if all_ok else "FAILURES ❌")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())

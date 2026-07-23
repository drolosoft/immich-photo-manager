#!/usr/bin/env python3
"""
Create shared links for all geographic albums in Immich.

Shared links make albums publicly accessible for gallery viewing.

Usage:
    export IMMICH_BASE_URL="http://your-immich-server:2283"
    export IMMICH_API_KEY="YOUR-API-KEY-HERE"
    python3 create_shared_links.py
"""

import os
import requests
import sys

API_KEY = os.environ.get("IMMICH_API_KEY", "")
BASE_URL = os.environ.get("IMMICH_BASE_URL", "http://localhost:2283")
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

if not API_KEY:
    print("Error: IMMICH_API_KEY environment variable required")
    sys.exit(1)


def get_all_albums():
    """Fetch all albums."""
    url = f"{BASE_URL}/api/albums"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def get_existing_shared_links():
    """Fetch all existing shared links."""
    url = f"{BASE_URL}/api/shared-links"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def create_shared_link(album_id, album_name):
    """Create a shared link for an album."""
    url = f"{BASE_URL}/api/shared-links"
    data = {
        "type": "ALBUM",
        "albumId": album_id,
        "allowDownload": True,
        "showMetadata": True,
        "allowUpload": False,
    }
    resp = requests.post(url, headers=HEADERS, json=data)
    resp.raise_for_status()
    result = resp.json()
    key = result.get("key", "")
    share_url = f"{BASE_URL}/share/{key}"
    print(f"  Shared: {album_name} → {share_url}")
    return result


def main():
    print(f"Connecting to Immich at {BASE_URL}...")

    existing = get_existing_shared_links()
    shared_album_ids = set()
    for link in existing:
        album = link.get("album", {})
        if album:
            shared_album_ids.add(album.get("id", ""))
    print(f"Found {len(existing)} existing shared links")

    albums = get_all_albums()
    print(f"Found {len(albums)} albums\n")

    created = 0
    skipped = 0
    for album in albums:
        album_id = album["id"]
        name = album.get("albumName", "Untitled")
        count = album.get("assetCount", 0)

        if album_id in shared_album_ids:
            skipped += 1
            continue

        if count == 0:
            continue

        create_shared_link(album_id, name)
        created += 1

    print(f"\nDone! Created {created} new shared links, skipped {skipped} already shared.")


if __name__ == "__main__":
    main()

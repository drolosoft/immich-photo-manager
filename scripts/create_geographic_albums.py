#!/usr/bin/env python3
"""
Create geographic albums in Immich from GPS-tagged photos.

Uses the /api/map/markers endpoint to fetch all geotagged assets,
matches them to predefined album definitions based on city/country,
then creates albums and adds the matched assets.

Usage:
    export IMMICH_BASE_URL="http://your-immich-server:2283"
    export IMMICH_API_KEY="YOUR-API-KEY-HERE"
    python3 create_geographic_albums.py
"""

import os
import requests
import sys
import time
from math import radians, cos, sin, asin, sqrt

API_KEY = os.environ.get("IMMICH_API_KEY", "")
BASE_URL = os.environ.get("IMMICH_BASE_URL", "http://localhost:2283")
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

if not API_KEY:
    print("Error: IMMICH_API_KEY environment variable required")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Album definitions: each album maps to a set of matching rules.
# Customize this list for your own travel destinations.
#
# Rules:
#   - "country": match photos in this country
#   - "state": match photos in this state/region
#   - "cities": list of city names to match
# ---------------------------------------------------------------------------

ALBUMS = [
    # Example: Italy trips
    {
        "name": "Roma, Italia",
        "description": "The Eternal City — ancient ruins, art, and cuisine",
        "match": {"country": "Italy", "cities": [
            "Rome", "Roma", "Vatican City"
        ]}
    },
    {
        "name": "Cinque Terre, Italia",
        "description": "Colorful coastal villages on the Italian Riviera",
        "match": {"country": "Italy", "cities": [
            "Riomaggiore", "Manarola", "Corniglia", "Vernazza", "Monterosso al Mare"
        ]}
    },
    # Example: Egypt trip
    {
        "name": "Cairo & Luxor, Egypt",
        "description": "Pyramids, temples, and the Nile",
        "match": {"country": "Egypt", "cities": [
            "Cairo", "Giza", "Luxor", "Karnak"
        ]}
    },
    # Add your own destinations here...
]


def haversine(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance in km between two GPS points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def api_get(path):
    """GET request to Immich API."""
    resp = requests.get(f"{BASE_URL}/api{path}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def api_post(path, data):
    """POST request to Immich API."""
    resp = requests.post(f"{BASE_URL}/api{path}", headers=HEADERS, json=data)
    resp.raise_for_status()
    return resp.json()


def api_put(path, data):
    """PUT request to Immich API."""
    resp = requests.put(f"{BASE_URL}/api{path}", headers=HEADERS, json=data)
    resp.raise_for_status()
    return resp.json()


def get_map_markers():
    """Fetch all GPS markers from the library."""
    return api_get("/map/markers?isArchived=false")


def search_by_city(city, country):
    """Search for photos matching a city and country."""
    result = api_post("/search/metadata", {
        "city": city,
        "country": country,
        "size": 200,
        "page": 1,
    })
    assets = result.get("assets", {})
    return [a["id"] for a in assets.get("items", [])]


def create_album(name, description, asset_ids):
    """Create an album and add assets."""
    album = api_post("/albums", {
        "albumName": name,
        "description": description,
    })
    album_id = album["id"]
    print(f"  Created album: {name} (id: {album_id})")

    if asset_ids:
        # Add in batches of 100
        for i in range(0, len(asset_ids), 100):
            batch = asset_ids[i:i + 100]
            api_put(f"/albums/{album_id}/assets", {"ids": batch})
            print(f"  Added {len(batch)} assets (batch {i // 100 + 1})")
            time.sleep(0.5)

    print(f"  Total: {len(asset_ids)} photos in '{name}'")
    return album_id


def main():
    print(f"Connecting to Immich at {BASE_URL}...")
    markers = get_map_markers()
    print(f"Found {len(markers)} geotagged assets\n")

    for album_def in ALBUMS:
        name = album_def["name"]
        desc = album_def["description"]
        match = album_def["match"]
        country = match.get("country", "")
        cities = match.get("cities", [])

        print(f"Processing: {name}")
        asset_ids = set()

        for city in cities:
            ids = search_by_city(city, country)
            asset_ids.update(ids)
            if ids:
                print(f"  {city}: {len(ids)} photos")

        if asset_ids:
            create_album(name, desc, list(asset_ids))
        else:
            print("  No photos found, skipping")
        print()

    print("Done!")


if __name__ == "__main__":
    main()

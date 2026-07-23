#!/usr/bin/env python3
"""
Discover geographic locations from Immich photo library.
Uses /api/map/markers for efficient GPS data retrieval.
Groups photos by GPS proximity and outputs a location inventory.

Usage:
    export IMMICH_BASE_URL="http://your-immich-server:2283"
    export IMMICH_API_KEY="YOUR-API-KEY-HERE"
    python3 discover_locations.py
"""

import json
import os
import sys
import urllib.request
from math import radians, cos, sin, asin, sqrt

API_KEY = os.environ.get("IMMICH_API_KEY", "")
BASE_URL = os.environ.get("IMMICH_BASE_URL", "http://localhost:2283")

if not API_KEY:
    print("Error: IMMICH_API_KEY environment variable required")
    sys.exit(1)


def api_get(path):
    """Make a GET request to Immich API."""
    url = f"{BASE_URL}/api{path}"
    req = urllib.request.Request(url, headers={"x-api-key": API_KEY})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def haversine(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance in km between two GPS points."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def cluster_markers(markers, radius_km=30):
    """Group GPS markers into clusters within radius_km of each other."""
    clusters = []
    for marker in markers:
        lat = marker.get("lat", 0)
        lon = marker.get("lon", 0)
        if lat == 0 and lon == 0:
            continue

        placed = False
        for cluster in clusters:
            clat, clon = cluster["center"]
            if haversine(lat, lon, clat, clon) < radius_km:
                cluster["markers"].append(marker)
                n = len(cluster["markers"])
                cluster["center"] = (
                    (clat * (n - 1) + lat) / n,
                    (clon * (n - 1) + lon) / n,
                )
                placed = True
                break

        if not placed:
            clusters.append({
                "center": (lat, lon),
                "markers": [marker],
            })

    return clusters


def main():
    print(f"Fetching GPS markers from {BASE_URL}...")
    markers = api_get("/map/markers?isArchived=false")
    print(f"Found {len(markers)} geotagged assets")

    print("Clustering by location (30km radius)...")
    clusters = cluster_markers(markers, radius_km=30)
    clusters.sort(key=lambda c: len(c["markers"]), reverse=True)

    print(f"\nDiscovered {len(clusters)} distinct locations:\n")
    for i, cluster in enumerate(clusters[:50]):
        lat, lon = cluster["center"]
        count = len(cluster["markers"])
        print(f"  {i + 1:3d}. ({lat:8.4f}, {lon:9.4f}) — {count:5d} photos")

    output = []
    for cluster in clusters:
        lat, lon = cluster["center"]
        output.append({
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "photo_count": len(cluster["markers"]),
            "asset_ids": [m.get("id", "") for m in cluster["markers"]],
        })

    outfile = "location_inventory.json"
    with open(outfile, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved {len(output)} locations to {outfile}")


if __name__ == "__main__":
    main()

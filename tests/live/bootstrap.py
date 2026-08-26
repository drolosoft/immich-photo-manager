"""Bootstrap a fresh Immich for the live harness: admin user, API key (all permissions), media upload, album.

Usage: python bootstrap.py http://127.0.0.1:13283 ./media > creds.json
"""

import glob
import json
import os
import sys

import httpx

LAB = [
    "clip.mp4",
    "photo1.jpg",
    "photo2.jpg",
    "photo3.jpg",
    "photo4.jpg",
]  # order matters: harness expects video first

base, media = sys.argv[1], sys.argv[2]
c = httpx.Client(base_url=base + "/api", timeout=120)
c.post(
    "/auth/admin-sign-up",
    json={"email": "lab@example.com", "password": "labpassword1", "name": "Lab"},
)
tok = c.post("/auth/login", json={"email": "lab@example.com", "password": "labpassword1"}).json()[
    "accessToken"
]
c.headers["Authorization"] = f"Bearer {tok}"
key = c.post("/api-keys", json={"name": "lab", "permissions": ["all"]}).json()["secret"]
c.headers.pop("Authorization")
c.headers["x-api-key"] = key
c.put("/users/me/preferences", json={"tags": {"enabled": True, "sidebarWeb": True}})


def upload(path):
    mt = "2026-03-01T12:00:00.000Z"
    r = c.post(
        "/assets",
        data={
            "deviceAssetId": os.path.basename(path),
            "deviceId": "lab",
            "fileCreatedAt": mt,
            "fileModifiedAt": mt,
        },
        files={"assetData": (os.path.basename(path), open(path, "rb"))},
    )
    r.raise_for_status()
    return r.json()["id"]


ids = [upload(os.path.join(media, f)) for f in LAB]
extra = {
    os.path.basename(f): upload(f)
    for f in sorted(glob.glob(os.path.join(media, "*")))
    if os.path.basename(f) not in LAB and not os.path.basename(f).startswith("upload_test")
}
album = c.post("/albums", json={"albumName": "Lab Album", "assetIds": ids}).json()
print(
    json.dumps(
        {
            "base": base,
            "key": key,
            "album_id": album["id"],
            "asset_ids": ids,
            "extra": extra,
            "version": c.get("/server/version").json(),
        }
    )
)

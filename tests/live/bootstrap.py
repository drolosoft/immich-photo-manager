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
client = httpx.Client(base_url=base + "/api", timeout=120)
client.post(
    "/auth/admin-sign-up",
    json={"email": "lab@example.com", "password": "labpassword1", "name": "Lab"},
)
tok = client.post("/auth/login", json={"email": "lab@example.com", "password": "labpassword1"}).json()[
    "accessToken"
]
client.headers["Authorization"] = f"Bearer {tok}"
key = client.post("/api-keys", json={"name": "lab", "permissions": ["all"]}).json()["secret"]
client.headers.pop("Authorization")
client.headers["x-api-key"] = key
client.put("/users/me/preferences", json={"tags": {"enabled": True, "sidebarWeb": True}})


def upload(path):
    modified_at = "2026-03-01T12:00:00.000Z"
    response = client.post(
        "/assets",
        data={
            "deviceAssetId": os.path.basename(path),
            "deviceId": "lab",
            "fileCreatedAt": modified_at,
            "fileModifiedAt": modified_at,
        },
        files={"assetData": (os.path.basename(path), open(path, "rb"))},
    )
    response.raise_for_status()
    return response.json()["id"]


ids = [upload(os.path.join(media, filename)) for filename in LAB]
extra = {
    os.path.basename(filename): upload(filename)
    for filename in sorted(glob.glob(os.path.join(media, "*")))
    if os.path.basename(filename) not in LAB and not os.path.basename(filename).startswith("upload_test")
}
album = client.post("/albums", json={"albumName": "Lab Album", "assetIds": ids}).json()
print(
    json.dumps(
        {
            "base": base,
            "key": key,
            "album_id": album["id"],
            "asset_ids": ids,
            "extra": extra,
            "version": client.get("/server/version").json(),
        }
    )
)

"""A tiny stand-in for the Immich REST API, for end-to-end contract tests.

Serves just enough of /api for the tools the skills depend on: ping, stats,
asset info, a real PNG thumbnail (any size), one album with two assets, and
metadata search. Runs in a background thread on a free localhost port so a
real MCP server subprocess can talk to it over HTTP.
"""

import base64
import socket
import threading

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

# 1x1 transparent PNG (67 bytes) — a real image, decodable by any viewer.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
API_KEY = "fake-immich-key-0123456789abcdef"

ASSETS = {
    "a1": {"id": "a1", "originalFileName": "beach.png", "fileCreatedAt": "2026-06-01T10:00:00.000Z",
           "type": "IMAGE", "exifInfo": {"city": "Lanzarote", "country": "Spain"}},
    "a2": {"id": "a2", "originalFileName": "sunset.png", "fileCreatedAt": "2026-06-02T19:30:00.000Z",
           "type": "IMAGE", "exifInfo": {"city": "Lanzarote", "country": "Spain"}},
}
ALBUM = {"id": "alb1", "albumName": "Lanzarote 2026", "description": "Trip", "assetCount": 2,
         "shared": False, "assets": list(ASSETS.values())}


def _auth(request: Request):
    if request.headers.get("x-api-key") != API_KEY:
        return JSONResponse({"message": "Invalid API key"}, status_code=401)
    return None


async def ping(request):
    return _auth(request) or JSONResponse({"res": "pong"})


async def statistics(request):
    return _auth(request) or JSONResponse({"photos": 2, "videos": 0, "usage": 12345})


async def version(request):
    return _auth(request) or JSONResponse({"major": 3, "minor": 0, "patch": 1})


async def asset(request):
    a = ASSETS.get(request.path_params["asset_id"])
    return _auth(request) or (JSONResponse(a) if a else JSONResponse({}, status_code=404))


async def thumbnail(request):
    if request.path_params["asset_id"] not in ASSETS:
        return Response(status_code=404)
    return _auth(request) or Response(PNG, media_type="image/png")


async def albums(request):
    return _auth(request) or JSONResponse([{k: v for k, v in ALBUM.items() if k != "assets"}])


async def album(request):
    if request.path_params["album_id"] != ALBUM["id"]:
        return JSONResponse({}, status_code=404)
    return _auth(request) or JSONResponse(ALBUM)


async def search_metadata(request):
    items = list(ASSETS.values())
    return _auth(request) or JSONResponse(
        {"assets": {"items": items, "total": len(items), "count": len(items), "nextPage": None}}
    )


app = Starlette(routes=[
    Route("/api/server/ping", ping),
    Route("/api/server/statistics", statistics),
    Route("/api/server/version", version),
    Route("/api/assets/{asset_id}", asset),
    Route("/api/assets/{asset_id}/thumbnail", thumbnail),
    Route("/api/albums", albums),
    Route("/api/albums/{album_id}", album),
    Route("/api/search/metadata", search_metadata, methods=["POST"]),
])


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeImmich:
    """Context manager: start the fake API in a thread, expose .base_url."""

    def __init__(self):
        self.port = free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error"))
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def __enter__(self):
        self._thread.start()
        import time
        for _ in range(100):
            if self._server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("fake immich did not start")

    def __exit__(self, *exc):
        self._server.should_exit = True
        self._thread.join(timeout=5)

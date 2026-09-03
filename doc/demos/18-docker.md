# 🐳 Run it as a container

The usual setup runs the server on your machine through `uvx`, one process per client. The other way is a container: one long-lived server on the box that already runs Immich, reachable over HTTP by whatever clients you point at it. The image is published multi-arch (amd64 and arm64) as `ghcr.io/drolosoft/immich-photo-manager`, it serves MCP on port 8626, and it holds the same 94 tools.

## 1. One command

```sh
docker run -d -p 8626:8626 \
  -e IMMICH_BASE_URL=https://your-immich-server.com \
  -e IMMICH_API_KEY=your-api-key \
  -v ./exports:/data \
  ghcr.io/drolosoft/immich-photo-manager
```

Point any Streamable HTTP client at `http://localhost:8626/mcp`. That one path serves both MCP protocol eras, the legacy handshake and the stateless 2026-07-28 spec, so an old client and a new one can talk to the same container without either knowing about the other.

## 2. Is it up

```sh
curl http://localhost:8626/health
```

```json
{"status": "ok", "version": "..."}
```

`/health` answers without credentials and without touching Immich, which is deliberate: a missing or wrong API key is a configuration problem, not a dead container, and it should not flap the process. The same check is wired into the image as its `HEALTHCHECK`, so `docker ps` reports healthy or unhealthy on its own.

## 3. First run without credentials

The two environment variables are optional. A container started without them still serves: the handshake works, the tool list is complete, and every tool that needs Immich answers "No Immich credentials configured" together with the fix. One `update_credentials` call with a base URL and an API key connects it, which means the setup can happen in the conversation:

```
Connect to my Immich at https://photos.example.com with this API key: <key>
```

The credentials are written to `/data/.immich-config/config.json`. With a volume mounted on `/data` they survive a restart and a re-created container, so this is a one-time step and not something to repeat after every `docker compose pull`.

That volume matters for a second reason: the tools that write files, `export_pdf` and `download_archive`, resolve relative paths against the working directory, and the working directory in the image is `/data`. A PDF built inside a container with no volume disappears with the container.

## 4. As a Compose service

Next to an Immich stack, or on its own:

```yaml
services:
  immich-mcp:
    image: ghcr.io/drolosoft/immich-photo-manager
    ports:
      - "8626:8626"
    environment:
      IMMICH_BASE_URL: https://your-immich-server.com
      IMMICH_API_KEY: your-api-key
      # MCP_ALLOWED_HOSTS: photos-mcp.example.com   # only behind a proxy / other hostname
    volumes:
      - ./exports:/data
    restart: unless-stopped
```

## 5. Reaching it under another name

DNS-rebinding protection is on, with a localhost default that already covers the common `-p 8626:8626` plus `http://localhost:8626` case. Reach the container under any other name, a reverse proxy or another container on the same Compose network, and that name has to be in `MCP_ALLOWED_HOSTS`:

```sh
-e MCP_ALLOWED_HOSTS=photos-mcp.example.com
```

When a request behind a proxy is rejected while `/health` answers fine, this setting is the first thing to check.

## 6. What is inside

The base is `python:3.13-slim` with no compiler and no system ffmpeg: PyAV, Pillow and fpdf2 all ship manylinux wheels for both architectures, so the image installs the package and stops there. The server binds `0.0.0.0` inside the container, because a container is only reachable from outside when it does, while the CLI default of `127.0.0.1` stays for non-Docker runs. The process runs as a non-root user, `server`, which owns `/data`.

## What leaves your network

The container talks to your Immich server and to whichever MCP client you point at it. Both are yours. Files the tools write stay in the volume you mounted, and `/health` never contacts Immich at all.

---

*Everything above comes from the image's `Dockerfile`, its build workflow, and the "Run as a Docker container" section of the [README](../../README.md).*

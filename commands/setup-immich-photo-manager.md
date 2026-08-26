---
name: setup-immich-photo-manager
description: First-time setup or credential update — configure your Immich MCP server connection and verify everything works
---

# Immich Photo Manager — Setup

Guide the user through connecting their Immich instance to this plugin.
This skill handles both **first-time setup** and **credential updates** (e.g. API key rotation).

## Prerequisites Check

Before starting, verify these are available:

1. **Immich instance** — Ask the user for their Immich server URL (e.g., `http://192.168.1.100:2283` or `https://photos.example.com`)
2. **Immich API key** — The user needs to generate one from Immich → User Settings → API Keys. Link: https://immich.app/docs/features/command-line-interface#obtain-the-api-key

## Setup Workflow

### Step 1: Check if MCP server is already running

Call `ping` to test if the MCP server is already up.

- **If ping succeeds** → the MCP server is running. Proceed to Step 2 to verify the API key works.
- **If ping fails** → the MCP server is not running or not configured. Ask the user to check their plugin installation.

### Step 2: Test if credentials are valid

Call `get_statistics` or `search_metadata` (any authenticated endpoint).

- **If it succeeds** → credentials are valid. Jump to Step 5 (show summary).
- **If it returns 401 Unauthorized** → the API key is invalid or expired. Go to Step 3.

### Step 3: Get new credentials from the user

Ask the user:
- What is your Immich server URL? (e.g., `https://photos.example.com`)
- What is your new API key? (guide them to create one if needed: Immich → User Settings → API Keys)

### Step 4: Update credentials via MCP tool

**Use the `update_credentials` tool** to update the connection in-place:

```
update_credentials(base_url="https://photos.example.com", api_key=<user-provided-key>)
```

This tool will:
1. Validate the new credentials against Immich (an authenticated call, a wrong key is rejected)
2. Persist them to `.mcpb-cache/config.json` (survives session restarts)
3. Hot-swap the live connection (no restart required)

**If `update_credentials` succeeds** → proceed to Step 5.
**If it fails** → tell the user the credentials didn't work, ask them to double-check.

**IMPORTANT:** Do NOT try to edit `mcp.json` directly — it's read-only for remote plugins.
The `update_credentials` tool is the correct way to change credentials.

### Step 5: Verify connection

Run these checks:
1. `ping` — Should return "pong"
2. `get_statistics` — Should show photo count, video count, storage
3. `get_server_version` — Should return Immich version

### Step 6: Show summary

```
Connected to Immich vX.XX.X
Photos: XX,XXX | Videos: X,XXX | Storage: XXX GB
Server: https://photos.example.com

You're all set! Try these to get started:
  - "Which of my photos have no location?" — metadata gaps, with fixes
  - "Go through my '<album>' album and tell me what's in each photo" — per-photo analysis
  - "Do I have duplicates?" — Immich's duplicate groups, ready to resolve
  - "Find photos of sunsets" — visual search
  - /my-travels — every place you have photos from
```

## Credential Rotation (Key Change)

When a user needs to update their API key (expired, rotated, etc.), the flow is simple:

1. User provides the new API key
2. Call `update_credentials(base_url, api_key)`
3. Done — no restart, no reinstall, no manual file editing

The `update_credentials` tool validates the key before committing it, so the user
gets immediate feedback if the key is wrong.

---

## Post-Install: CORS Configuration (Recommended)

After the basic setup is complete, recommend this optional but highly beneficial step.

### Why CORS matters

The plugin generates HTML gallery viewers that display photo thumbnails. By default, thumbnails are embedded as base64 data inside the HTML file, which works everywhere but limits galleries to ~50 photos and produces large files.

If the user enables CORS on their Immich server, galleries can load thumbnails directly from the server via URL. This enables true pagination, instant loading, and galleries with hundreds or thousands of photos — all in a tiny HTML file.

### How to check if CORS is already enabled

Ask the user: "Do you access Immich through a reverse proxy like Nginx, Caddy, or Traefik?" Most self-hosted Immich setups use one.

### Configuration by reverse proxy

#### Nginx

Add these lines inside the `location` block that proxies to Immich:

```nginx
# CORS for immich-photo-manager gallery viewer
add_header 'Access-Control-Allow-Origin' '*' always;
add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
add_header 'Access-Control-Allow-Headers' 'x-api-key, Content-Type' always;

if ($request_method = 'OPTIONS') {
    add_header 'Access-Control-Allow-Origin' '*';
    add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS';
    add_header 'Access-Control-Allow-Headers' 'x-api-key, Content-Type';
    add_header 'Access-Control-Max-Age' 86400;
    return 204;
}
```

Then reload: `sudo nginx -s reload`

#### Caddy

Add a `header` block to the Immich site:

```caddy
photos.example.com {
    header {
        Access-Control-Allow-Origin *
        Access-Control-Allow-Methods "GET, OPTIONS"
        Access-Control-Allow-Headers "x-api-key, Content-Type"
    }
    reverse_proxy localhost:2283
}
```

Then reload: `caddy reload`

#### Traefik

Add CORS middleware via labels (Docker) or file provider:

```yaml
# Docker labels
- "traefik.http.middlewares.immich-cors.headers.accessControlAllowOriginList=*"
- "traefik.http.middlewares.immich-cors.headers.accessControlAllowMethods=GET,OPTIONS"
- "traefik.http.middlewares.immich-cors.headers.accessControlAllowHeaders=x-api-key,Content-Type"
```

#### Direct access (no reverse proxy)

If the user accesses Immich directly on its port (e.g., `http://192.168.1.100:2283`), CORS headers would need to be set in Immich itself. As of Immich v1.x, there is no built-in CORS configuration. In this case, the user should either set up a lightweight reverse proxy or rely on base64-embedded thumbnails (the default, which works everywhere).

### Security note

Using `Access-Control-Allow-Origin: *` allows any website to make requests to the Immich API. For a self-hosted instance on a private network, this is generally acceptable. For a publicly exposed instance, the user may prefer to restrict the origin to specific domains or use `null` (which allows `file://` and `about:` origins used by local HTML viewers).

### After enabling CORS

Tell the user: "CORS is now enabled. Photo galleries will load much faster and support unlimited photos. No plugin changes needed — the gallery viewer automatically uses URL-based loading when the server supports it."

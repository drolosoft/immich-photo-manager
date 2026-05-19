# Getting Started

Step-by-step guide to installing, configuring, and running the Immich Photo Manager plugin.

---

## Prerequisites

### Required

- **Immich instance** — Self-hosted, any recent version (v1.90+). [Installation guide](https://immich.app/docs/install/docker-compose)
- **Immich API key** — Generated from Immich web UI → User Settings → API Keys. [How to create one](https://immich.app/docs/features/command-line-interface#obtain-the-api-key)
- **Python 3.10+** — To run the MCP server. [Download Python](https://www.python.org/downloads/)
- **Claude** — Desktop app with Cowork mode, or Claude Code CLI
- **uv** — Required only for the `uvx` install path. [Installation guide](https://docs.astral.sh/uv/getting-started/installation/)

### Optional (for advanced skills)

- **Python 3.10+** — Required for `duplicate-report` and `metadata-fixer` skills
- **PostgreSQL client** — Required for database-level analysis skills (`library-health-report`, `timeline-gaps`, `people-report`, `storage-optimizer`)
- **Python packages** (for `duplicate-report`):
  ```bash
  pip3 install Pillow imagehash pillow-heif
  ```

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/drolosoft/immich-photo-manager.git
cd immich-photo-manager
```

### 2. Run the interactive setup

```bash
./scripts/setup-mcp.sh
```

This will:
- Install Python dependencies (`mcp`, `httpx`)
- Ask for your Immich server URL and API key
- Generate `.mcp.json` with the correct configuration
- Optionally configure global access for Cowork mode

### 3. Install the Claude plugin

```bash
claude plugin marketplace add ~/immich-photo-manager
claude plugin install immich-photo-manager
```

### 4. Verify

**Restart Claude Code** or start a new Cowork session (MCP connections are established at startup), then:

```bash
claude -p "use the immich ping tool"
```

### Install with uvx

For MCP clients that can run package entry points, use `uvx`:

```json
{
  "mcpServers": {
    "immich": {
      "command": "uvx",
      "args": ["immich-photo-manager"],
      "env": {
        "IMMICH_BASE_URL": "https://your-immich-server.com",
        "IMMICH_API_KEY": "your-api-key"
      }
    }
  }
}
```

The `immich-photo-manager` command defaults to MCP stdio transport. For a local checkout before publishing, use:

```json
{
  "mcpServers": {
    "immich": {
      "command": "uvx",
      "args": ["--from", "/path/to/immich-photo-manager", "immich-photo-manager"],
      "env": {
        "IMMICH_BASE_URL": "https://your-immich-server.com",
        "IMMICH_API_KEY": "your-api-key"
      }
    }
  }
}
```

---

## First Run

After installation, verify everything works:

### Check connection

```
/immich-status
```

You should see your library statistics: photo count, video count, storage used.

### Explore your library

```
/my-travels
```

This discovers all geotagged locations in your library and shows countries and cities.

### Run a health check

```
"How healthy is my library?"
```

This triggers the `library-health-report` skill and gives you a comprehensive overview with recommendations for what to do next.

---

## Configuration Reference

### Environment Variables

These are set automatically by `setup-mcp.sh` inside `.mcp.json`:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `IMMICH_BASE_URL` | Yes | — | Your Immich server URL (e.g., `https://photos.example.com`) |
| `IMMICH_API_KEY` | Yes | — | API key from Immich user settings |
| `PYTHONPATH` | Local checkout only | — | Path to `src/` directory in the cloned repo |
| `MCP_TRANSPORT` | No | `stdio` | Use `stdio` for MCP clients; set `http` for Streamable HTTP |

### Database Access (for advanced skills)

Skills that query Immich's PostgreSQL directly need these credentials (typically the same database that Immich uses):

| Variable | Description |
|----------|-------------|
| `DB_HOST` | PostgreSQL host (usually `127.0.0.1`) |
| `DB_PORT` | PostgreSQL port (usually `5432`) |
| `DB_USER` | Database user (usually `immich`) |
| `DB_PASS` | Database password |
| `DB_NAME` | Database name (usually `immich`) |

These are only needed for: `library-health-report`, `timeline-gaps`, `metadata-fixer`, `duplicate-report`, `storage-optimizer`, `people-report`, `travel-map`.

---

## Deployment Options

### Local development

The MCP server runs automatically as a child process of Claude Code — no manual server startup needed. The configuration in `.mcp.json` tells Claude Code how to launch it.

To test the server manually:

```bash
PYTHONPATH=./src MCP_TRANSPORT=stdio IMMICH_BASE_URL=https://your-server IMMICH_API_KEY=your-key python3 -m immich_mcp_server
```

To test the packaged console script from a checkout:

```bash
IMMICH_BASE_URL=https://your-server IMMICH_API_KEY=your-key uvx --from . immich-photo-manager
```

### macOS (launchd)

For persistent background service on macOS:

```bash
cp deploy/com.immich-mcp.plist.example ~/Library/LaunchAgents/com.immich-mcp.plist
# Edit the plist: set paths and environment variables
launchctl load ~/Library/LaunchAgents/com.immich-mcp.plist
```

### Linux (systemd)

Create a systemd unit file:

```ini
[Unit]
Description=Immich MCP Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 -m immich_mcp_server
Environment=IMMICH_BASE_URL=http://localhost:2283
Environment=IMMICH_API_KEY=your-key-here
Environment=MCP_TRANSPORT=http
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Behind nginx

See `deploy/nginx-immich-mcp.conf.example` for a reverse proxy configuration with HTTPS.

---

## Recommended First Steps

After installation, we recommend this sequence:

1. **`/immich-status`** — Verify connection
2. **`library-health-report`** — Understand your library's current state
3. **`duplicate-report`** — If you have multiple import sources (Apple + Google)
4. **`photo-cleanup`** — Remove screenshots and junk
5. **`/my-travels`** — See all your geotagged destinations
6. **`album-manager`** — Start organizing photos into geographic albums

See [SKILLS.md](./SKILLS.md) for detailed documentation of every skill.

---

## Troubleshooting

### "Connection refused" on startup

- Verify your Immich server is running: `curl http://your-server:2283/api/server/ping`
- Check that the API key is valid: `curl -H "x-api-key: YOUR_KEY" http://your-server:2283/api/server/version`

### Server pings OK but API key is rejected

The `/api/server/ping` endpoint is **public** — it returns `{"res":"pong"}` without authentication. This means a successful ping does NOT confirm your API key works. To verify the key, test a protected endpoint:

```bash
curl -H "x-api-key: YOUR_KEY" https://your-server/api/users/me
```

If you get `{"message":"Invalid API key","error":"Unauthorized","statusCode":401}`, the key is wrong. Common causes:
- Key was copied incompletely (missing trailing characters)
- Key was revoked or expired in Immich → User Settings → API Keys
- Key belongs to a different Immich instance

### Skills that need PostgreSQL report errors

- Ensure PostgreSQL is accessible from where the MCP server runs
- Check credentials with: `psql -h HOST -U immich -d immich -c "SELECT count(*) FROM asset"`
- If using Docker, the PostgreSQL port may not be exposed — add `ports: ["5432:5432"]` to your docker-compose

### HEIC files not processed (duplicate-report)

- Install `pillow-heif`: `pip3 install pillow-heif`
- Without it, Apple Photos HEIC files (40%+ of typical libraries) can't be hashed
- Error shows as thousands of "cannot identify image file" messages

### Perceptual hashing hangs (duplicate-report)

- Don't use `ProcessPoolExecutor` — native HEIF libraries deadlock on fork on macOS
- Use `ThreadPoolExecutor(max_workers=4)` instead

---

## Further Reading

- [ARCHITECTURE.md](./ARCHITECTURE.md) — How base64-embedded thumbnails solve the Cowork sandbox restriction, with full data flow diagrams
- [MCP-TOOLS.md](./MCP-TOOLS.md) — Complete reference for all 36 MCP tools
- [SKILLS.md](./SKILLS.md) — Detailed documentation for all 11 skills

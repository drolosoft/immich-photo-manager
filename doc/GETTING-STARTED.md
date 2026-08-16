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
| `MCP_ALLOWED_HOSTS` | No | — | HTTP mode only: comma-separated extra `Host` header values to accept (e.g. `immich-mcp.example.com`). Required behind a reverse proxy, which otherwise gets `421 Misdirected Request`. Localhost stays allowed and DNS-rebinding protection stays on |

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

When proxying, the forwarded `Host` header is your public domain rather than `localhost`, so the server answers `421 Misdirected Request` unless that host is allowed explicitly. Add it to the systemd unit (or your service manager of choice):

```ini
Environment=MCP_ALLOWED_HOSTS=immich-mcp.example.com
```

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

## Environment Setup (Detailed)

This section covers the full local environment setup: installing git, Python, and a
virtual environment, then running the server in HTTP or stdio mode.

### Install git

**Ubuntu / Debian (APT):**
```bash
sudo apt update
sudo apt install -y git
git --version
```

**Fedora / RHEL (DNF):**
```bash
sudo dnf install -y git
```

**macOS (Homebrew):**
```bash
brew install git
```

Set your commit identity (optional but recommended):

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

### Install Python 3.10+

#### Option A — Ubuntu / Debian via `deadsnakes` (recommended for a newer version)

The system `python3` on some distributions may be older than 3.10. For a reliable
install, use the `deadsnakes` repository:

```bash
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update

# Install Python 3.12 (or any desired version >= 3.10)
sudo apt install -y python3.12 python3.12-venv
```

Then use `python3.12` explicitly:

```bash
python3.12 --version
```

#### Option B — Ubuntu / Debian with the system Python

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
python3 --version
```

> If it reports **3.10 or newer**, you're ready. If it's older, use Option A.

#### Fedora / RHEL

```bash
sudo dnf install -y python3 python3-pip
```

#### macOS

```bash
brew install python@3.12
```

### Create and activate a virtual environment (venv)

A virtual environment isolates the project's dependencies from the rest of the system.
The recommended name in this repository is `ipm`.

```bash
cd ~/Documents/immich-photo-manager

# Create the venv (use python3.12 if you installed it via deadsnakes)
python3 -m venv ipm
# or explicitly: python3.12 -m venv ipm

# Activate it
source ipm/bin/activate

# Upgrade pip inside the venv
python3 -m pip install --upgrade pip
```

A successful activation is indicated by `(ipm)` at the start of your prompt.

**Deactivation** (when you want to leave the venv):

```bash
deactivate
```

### Install `uv` (alternative for `uvx` launch)

`uv` is only needed if you want to run the server via `uvx` without cloning manually:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify:

```bash
uv --version
```

### Get the project code

```bash
cd ~/Documents
git clone https://github.com/drolosoft/immich-photo-manager.git
cd immich-photo-manager
```

Important file structure:

```
immich-photo-manager/
├── src/immich_mcp_server/   # Python server code
│   ├── server.py            #   MCP tools + HTTP app
│   ├── immich_client.py     #   Immich REST API client
│   └── __main__.py          #   entry point (stdio/http)
├── scripts/setup-mcp.sh     # interactive setup script
├── start-mcp.sh             # manual launch (HTTP / stdio)
├── .env.example             # environment variable template
├── pyproject.toml           # package declaration and dependencies
└── doc/                     # documentation
```

### Install dependencies

Dependencies are declared in `pyproject.toml` and `src/requirements.txt`.

#### Method A — editable (development) install, recommended for this repository

```bash
source ipm/bin/activate
pip install -e .
```

This installs the package in "editable" mode, so changes in `src/` take effect
immediately without reinstalling.

#### Method B — minimal dependencies only

```bash
source ipm/bin/activate
pip install -r src/requirements.txt
```

#### Method C — development dependencies (tests, lint)

```bash
source ipm/bin/activate
pip install -e ".[dev]"
```

### Environment variable configuration

The server needs at least **`IMMICH_BASE_URL`** and **`IMMICH_API_KEY`**. The remaining
variables control the transport and port.

#### Variable reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `IMMICH_BASE_URL` | Yes | — | Immich instance URL (e.g. `http://your-immich-server:2283`) |
| `IMMICH_API_KEY` | Yes | — | Immich API key |
| `MCP_TRANSPORT` | No | `http` (with `python -m`) | `stdio` or `http` |
| `MCP_HOST` | No | `127.0.0.1` | Address the HTTP server listens on (`0.0.0.0` = all interfaces) |
| `MCP_PORT` | No | `8626` | HTTP port |
| `MCP_ALLOWED_HOSTS` | No | — | In HTTP mode: extra comma-separated `Host` header values (see §8) |

> Important: when you launch the server with `python3 -m immich_mcp_server`, the default
> transport is **`http`**. When an MCP client launches it via the `immich-photo-manager`
> entry point, the default transport is **`stdio`**.

#### `.env` template

Copy the template and edit it:

```bash
cp .env.example .env
```

Contents of `.env`:

```bash
IMMICH_BASE_URL=http://your-immich-server:2283
IMMICH_API_KEY=your-api-key-here
MCP_PORT=8626
# MCP_ALLOWED_HOSTS=immich-mcp.example.com
```

> `.env` is not loaded automatically unless you export it (e.g. via `start-mcp.sh`).
> The simplest approach is to set the variables directly in `start-mcp.sh`.

### Running the server

#### HTTP mode (for Open WebUI)

```bash
cd ~/Documents/immich-photo-manager
source ipm/bin/activate

export IMMICH_BASE_URL="http://your-immich-server:2283"
export IMMICH_API_KEY="your-api-key"
export MCP_TRANSPORT=http
export MCP_HOST="0.0.0.0"
export MCP_PORT=8626
export MCP_ALLOWED_HOSTS="192.168.1.10"

python3 -m immich_mcp_server
```

On a successful start you'll see:

```
Immich MCP Server starting on 0.0.0.0:8626
...
Uvicorn running on http://0.0.0.0:8626 (Press CTRL+C to quit)
```

The MCP endpoint is: **`http://<IP>:8626/mcp`**

#### stdio mode (for Claude Code / LM Studio)

```bash
cd ~/Documents/immich-photo-manager
source ipm/bin/activate

export IMMICH_BASE_URL="http://your-immich-server:2283"
export IMMICH_API_KEY="your-api-key"
export MCP_TRANSPORT=stdio
export PYTHONPATH="$PWD/src"

python3 -m immich_mcp_server
```

Instead of `export MCP_TRANSPORT=stdio` you can also use the CLI argument:

```bash
python3 -m immich_mcp_server --transport stdio
```

> With the stdio transport, **stdout must stay clean** (JSON-RPC), so all diagnostic
> output goes to stderr.

#### Launch via the `start-mcp.sh` script

The `start-mcp.sh` script combines all the steps above. Edit it and then run:

```bash
chmod +x start-mcp.sh
./start-mcp.sh
```

Example `start-mcp.sh` contents:

```bash
cd /path/to/immich-photo-manager/
export IMMICH_BASE_URL="http://your-immich-server:2283"
export IMMICH_API_KEY="your-api-key"
export MCP_TRANSPORT=http
export MCP_HOST="0.0.0.0"
export MCP_PORT=8626
export MCP_ALLOWED_HOSTS="192.168.1.10"
source ipm/bin/activate
python3 -m immich_mcp_server
```

### `MCP_ALLOWED_HOSTS` — why it matters

The MCP SDK automatically enables **DNS-rebinding protection**, which in HTTP mode only
accepts a `Host` header of `127.0.0.1` / `localhost` / `::1`. If Open WebUI targets the
server via another address (e.g. `192.168.1.10:8626`), the SDK returns:

```
Invalid Host header: 192.168.1.10:8626
421 Misdirected Request
```

Solution:

1. Set `MCP_ALLOWED_HOSTS` to the address **the client actually uses** (as seen in the
   `Host` header in the log), not the client's IP.
2. The value can be:
   - a bare domain/IP: `immich-mcp.example.com` or `192.168.1.10` → the server itself
     adds a match for any port (`192.168.1.10:*`),
   - with a port: `192.168.1.10:8626`,
   - multiple comma-separated values: `192.168.1.10,immich-mcp.example.com`.

Example:

```bash
export MCP_ALLOWED_HOSTS="192.168.1.10"
```

### Connecting Open WebUI

1. Open Open WebUI → **Workspace / Tools / MCP** (or the equivalent place for MCP
   servers).
2. Add a new MCP server with type **Streamable HTTP**.
3. URL: `http://192.168.1.10:8626/mcp`
4. Save and wait for the connection to establish (the server log should show
   `POST /mcp HTTP/1.1 200 OK`).

> If the server listens on `0.0.0.0`, you can reach it via any network interface of the
> host (e.g. `192.168.1.10`). If it only listens on `127.0.0.1`, it's only reachable
> locally on the same machine.

### Connecting Claude Code / LM Studio (stdio)

In the MCP client configuration, use the stdio entry point:

```json
{
  "mcpServers": {
    "immich": {
      "command": "python3",
      "args": ["-m", "immich_mcp_server"],
      "env": {
        "PYTHONPATH": "/path/to/immich-photo-manager/src",
        "MCP_TRANSPORT": "stdio",
        "IMMICH_BASE_URL": "http://your-immich-server:2283",
        "IMMICH_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Verifying it works

#### Check the Immich connection

```bash
# Ping (public endpoint, does not verify the API key)
curl http://your-immich-server:2283/api/server/ping

# Verify the API key (protected endpoint)
curl -H "x-api-key: your-api-key" http://your-immich-server:2283/api/users/me

# Immich version
curl -H "x-api-key: your-api-key" http://your-immich-server:2283/api/server/version
```

#### Check the HTTP MCP server

```bash
# POST to /mcp should return 200 (not 421)
curl -i -X POST http://192.168.1.10:8626/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'
```

#### Check preview loading (Immich 3.x)

In Immich 3.x the `/preview` path no longer exists; the preview is fetched via
`thumbnail?size=preview`:

```bash
curl -H "x-api-key: your-api-key" \
  "http://your-immich-server:2283/api/assets/ASSET_ID/thumbnail?size=preview&edited=true"
```

### Common issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| `421 Misdirected Request` | Wrong/unconfigured `MCP_ALLOWED_HOSTS` | Set `MCP_ALLOWED_HOSTS` to the target address (see §8) |
| `404` at `/preview` | Immich 3.x removed `/preview` | Use `thumbnail?size=preview` (fixed in code) |
| `Invalid API key` / `401` | Wrong or revoked key | Check with `/api/users/me`, create a new key |
| `Connection refused` | Immich not running / wrong URL | `curl http://.../api/server/ping` |
| `ModuleNotFoundError: immich_mcp_server` | `PYTHONPATH` not set (stdio) | Add `export PYTHONPATH="$PWD/src"` or `pip install -e .` |
| Open WebUI won't connect | Server listens on `127.0.0.1` | Set `MCP_HOST=0.0.0.0` |

### Development work (tests and lint)

```bash
source ipm/bin/activate

# Run the test suite (not connected to Immich)
pytest

# Check style / static analysis
ruff check src tests
```

The tests live in `tests/` and do not require a running Immich instance.

### Quick setup summary

```bash
# 1) Clone and enter the directory
cd ~/Documents
git clone https://github.com/drolosoft/immich-photo-manager.git
cd immich-photo-manager

# 2) Create and activate the venv
python3 -m venv ipm
source ipm/bin/activate
pip install --upgrade pip
pip install -e .

# 3) Edit start-mcp.sh (URL, API key, MCP_ALLOWED_HOSTS)
nano start-mcp.sh

# 4) Run the HTTP server
./start-mcp.sh

# 5) Add the MCP server in Open WebUI: http://192.168.1.10:8626/mcp
```

---

## TrueNAS SCALE Deployment

The project ships a `Dockerfile` and `docker-compose.yml` so you can run the server
as a container. No image registry (GHCR) is needed — the image is built locally.

### Option A — docker compose (simplest on a SCALE box with a Shell)

1. Clone your fork and enter the directory:
   ```bash
   cd /mnt/tank/apps
   git clone https://github.com/<your-username>/immich-photo-manager.git
   cd immich-photo-manager
   ```

2. Create a `.env` file with your values (see `.env.example`):
   ```bash
   cp .env.example .env
   # edit .env: IMMICH_BASE_URL, IMMICH_API_KEY, MCP_ALLOWED_HOSTS
   ```

3. Build and start:
   ```bash
   docker compose up --build -d
   ```

4. Check the logs:
   ```bash
   docker compose logs -f
   ```

The MCP endpoint is `http://<truenas-ip>:8626/mcp`.

### Option B — Custom App (ix-apps)

TrueNAS SCALE's "Custom App" UI only accepts an `image:` (it does not run `build:`
directly), so build the image once in a Shell, then reference it by its local tag.

1. Build the image:
   ```bash
   cd /mnt/tank/apps/immich-photo-manager
   docker build -t immich-photo-manager:latest .
   ```

2. In TrueNAS SCALE, go to **Apps → Discover Apps → Custom App** (or
   **Launch Docker Image**) and configure:

   | Field | Value |
   |-------|-------|
   | Image repository | `immich-photo-manager` |
   | Image tag | `latest` |
   | Port forward | Container `8626` → Host `8626` |

3. Add environment variables:
   - `IMMICH_BASE_URL` = `http://<truenas-ip>:30041`
   - `IMMICH_API_KEY` = your Immich API key
   - `MCP_HOST` = `0.0.0.0`
   - `MCP_PORT` = `8626`
   - `MCP_ALLOWED_HOSTS` = the host/IP Open WebUI actually uses (e.g. `192.168.1.10`)

4. Start the app, then add the MCP server in Open WebUI:
   `http://<truenas-ip>:8626/mcp`

> **`MCP_ALLOWED_HOSTS` is required.** The MCP SDK's DNS-rebinding protection
> returns `421 Misdirected Request` unless the `Host` header the client sends is
> explicitly allowed (see the `MCP_ALLOWED_HOSTS` section above).

> **Note on networking:** if Immich runs as another SCALE app, point
> `IMMICH_BASE_URL` at the address reachable from the container (the TrueNAS IP or
> the app's internal DNS name), not `localhost`.

---

## Further Reading

- [ARCHITECTURE.md](./ARCHITECTURE.md) — How base64-embedded thumbnails solve the Cowork sandbox restriction, with full data flow diagrams
- [MCP-TOOLS.md](./MCP-TOOLS.md) — Complete reference for all 50 MCP tools
- [SKILLS.md](./SKILLS.md) — Detailed documentation for all 12 skills

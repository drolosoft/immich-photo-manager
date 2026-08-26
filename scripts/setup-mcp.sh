#!/bin/bash
# setup-mcp.sh - Interactive setup for the Immich MCP server
# Configures: project .mcp.json, Claude Code user scope (claude mcp add-json), claude_desktop_config.json (Desktop app)
set -e

echo ""
echo "=== Immich Photo Manager - MCP Setup ==="
echo ""

# Detect repo directory
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$SCRIPT_DIR/src"

echo "Detected project directory: $SCRIPT_DIR"
echo "Python source directory:    $SRC_DIR"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Please install Python 3.10+."
  exit 1
fi
PYTHON_PATH="$(which python3)"
echo "Python: $(python3 --version) ($PYTHON_PATH)"

# Install dependencies
echo ""
echo "Installing Python dependencies..."
if [ -f "$SRC_DIR/requirements.txt" ]; then
  pip3 install -r "$SRC_DIR/requirements.txt" --break-system-packages 2>/dev/null \
    || pip3 install -r "$SRC_DIR/requirements.txt" 2>/dev/null \
    || echo "WARNING: pip install failed. Please install dependencies manually: pip3 install mcp httpx"
else
  pip3 install mcp httpx --break-system-packages 2>/dev/null \
    || pip3 install mcp httpx 2>/dev/null \
    || echo "WARNING: pip install failed. Please install manually: pip3 install mcp httpx"
fi
echo ""

# Ask for Immich details (the key is read without echo)
read -p "Enter your Immich server URL (e.g. https://photos.example.com): " IMMICH_URL
read -r -s -p "Enter your Immich API key: " IMMICH_KEY
echo ""

if [ -z "$IMMICH_URL" ] || [ -z "$IMMICH_KEY" ]; then
  echo "ERROR: Both URL and API key are required."
  exit 1
fi

# Write/merge the immich entry into a JSON config. All user-supplied
# values reach Python as environment variables — never interpolated
# into code or JSON, so quotes in a key or URL are just data.
write_immich_config() {
  local CONFIG_FILE="$1"
  local MODE="${2:-merge}"   # merge = keep other entries; create = fresh file
  TARGET_FILE="$CONFIG_FILE" WRITE_MODE="$MODE" \
  IMMICH_URL="$IMMICH_URL" IMMICH_KEY="$IMMICH_KEY" \
  PYTHON_PATH="$PYTHON_PATH" SRC_DIR="$SRC_DIR" \
  python3 - <<'PYEOF'
import json, os

target = os.environ["TARGET_FILE"]
entry = {
    "command": os.environ["PYTHON_PATH"],
    "args": ["-m", "immich_mcp_server"],
    "env": {
        "PYTHONPATH": os.environ["SRC_DIR"],
        "MCP_TRANSPORT": "stdio",
        "IMMICH_BASE_URL": os.environ["IMMICH_URL"],
        "IMMICH_API_KEY": os.environ["IMMICH_KEY"],
    },
}
config = {"mcpServers": {}}
if os.environ.get("WRITE_MODE") == "merge":
    try:
        with open(target) as f:
            config = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        config = {"mcpServers": {}}
config.setdefault("mcpServers", {})["immich"] = entry
with open(target, "w") as f:
    json.dump(config, f, indent=2)
    f.write("\n")
print(f"  Wrote {target}")
PYEOF
}

# ---- 1. Project-level .mcp.json ----
write_immich_config "$SCRIPT_DIR/.mcp.json" create

# ---- 2. Global configs (auto-merge into all Claude config locations) ----
echo ""
read -p "Install globally for Claude Desktop + Cowork + Claude Code? (y/N): " GLOBAL
if [ "$GLOBAL" = "y" ] || [ "$GLOBAL" = "Y" ]; then

  # 2a. Claude Code, user scope (every folder). Claude Code does not read
  # ~/.claude/mcp.json; the supported way is `claude mcp add-json`.
  if command -v claude &>/dev/null; then
    ENTRY_JSON=$(PYTHON_PATH="$PYTHON_PATH" SRC_DIR="$SRC_DIR" IMMICH_URL="$IMMICH_URL" IMMICH_KEY="$IMMICH_KEY" python3 -c '
import json, os
print(json.dumps({"command": os.environ["PYTHON_PATH"], "args": ["-m", "immich_mcp_server"], "env": {"PYTHONPATH": os.environ["SRC_DIR"], "MCP_TRANSPORT": "stdio", "IMMICH_BASE_URL": os.environ["IMMICH_URL"], "IMMICH_API_KEY": os.environ["IMMICH_KEY"]}}))')
    claude mcp remove immich -s user >/dev/null 2>&1 || true
    claude mcp add-json immich "$ENTRY_JSON" -s user && echo "  Registered 'immich' in Claude Code (user scope)"
  else
    echo "  claude CLI not found (skipping Claude Code user-scope registration)"
  fi

  # 2b. Claude Desktop config (macOS)
  DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
  if [ -f "$DESKTOP_CONFIG" ]; then
    write_immich_config "$DESKTOP_CONFIG" merge
  else
    echo "  Claude Desktop config not found (skipping): $DESKTOP_CONFIG"
  fi

  # 2c. Claude Desktop config (Linux)
  LINUX_DESKTOP="$HOME/.config/Claude/claude_desktop_config.json"
  if [ -f "$LINUX_DESKTOP" ]; then
    write_immich_config "$LINUX_DESKTOP" merge
  fi

  # 2d. Auto-allow immich MCP tools in ~/.claude/settings.json
  SETTINGS_FILE=~/.claude/settings.json
  if [ -f "$SETTINGS_FILE" ]; then
    SETTINGS_FILE="$SETTINGS_FILE" python3 - <<'PYEOF'
import json, os

sf = os.environ["SETTINGS_FILE"]
with open(sf) as f:
    settings = json.load(f)

allow = settings.setdefault("permissions", {}).setdefault("allow", [])
if "mcp__immich__*" not in allow:
    allow.append("mcp__immich__*")
    with open(sf, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print("  Added mcp__immich__* to permissions.allow in " + sf)
else:
    print("  mcp__immich__* already in permissions.allow")
PYEOF
  else
    echo "  ~/.claude/settings.json not found (skipping auto-allow)"
  fi

  echo ""
  echo "Global installation complete."
fi

# ---- 3. Quick test (never aborts the setup) ----
echo ""
echo "Testing connection to $IMMICH_URL..."
IMMICH_URL="$IMMICH_URL" IMMICH_KEY="$IMMICH_KEY" PYTHONPATH="$SRC_DIR" \
"$PYTHON_PATH" - <<'PYEOF' || true
import os

try:
    import httpx

    # /users/me needs a valid key; /server/ping would answer 200 to anything.
    r = httpx.get(
        os.environ["IMMICH_URL"].rstrip("/") + "/api/users/me",
        headers={"x-api-key": os.environ["IMMICH_KEY"]},
        timeout=10,
    )
    if r.status_code == 200:
        print(f"  Connection OK! Logged in as {r.json().get('email', '?')}.")
    elif r.status_code in (401, 403):
        print("  WARNING: the server answered but rejected the API key (HTTP "
              f"{r.status_code}). Check the key.")
    else:
        print(f"  WARNING: Server returned HTTP {r.status_code}")
except Exception as e:
    print(f"  WARNING: Could not reach server: {e}")
PYEOF

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Restart Claude Desktop (Cmd+Q then reopen) or start a new Claude Code session"
echo "  2. Ask: 'What Immich version am I connected to?'"
echo ""

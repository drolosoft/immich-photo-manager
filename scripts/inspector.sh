#!/bin/bash
# Launch the official MCP Inspector (web UI) against this server.
#
# The Inspector is an independent, interactive MCP client: it lists the tools,
# shows their schemas, and calls them from the browser — a hands-on check that
# any MCP harness, not just Claude, can drive this server.
#
# Usage:
#   scripts/inspector.sh                    # credentials from the environment
#   scripts/inspector.sh path/to/creds.json # lab-style {base, key} file
#
# The server binary is resolved in this order: $IMMICH_MCP_BIN, the repo venv,
# a system-wide install, then uvx from PyPI.
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"

if [ $# -ge 1 ] && [ -f "$1" ]; then
  IMMICH_BASE_URL=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['base'])" "$1")
  IMMICH_API_KEY=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['key'])" "$1")
fi

if [ -z "${IMMICH_BASE_URL:-}" ] || [ -z "${IMMICH_API_KEY:-}" ]; then
  echo "ERROR: set IMMICH_BASE_URL and IMMICH_API_KEY, or pass a creds.json with {base, key}." >&2
  exit 1
fi

# Prefer a local build so the Inspector tests what is being worked on.
if [ -n "${IMMICH_MCP_BIN:-}" ]; then
  SERVER_BIN="$IMMICH_MCP_BIN"
elif [ -x "$REPO/.venv/bin/immich-photo-manager" ]; then
  SERVER_BIN="$REPO/.venv/bin/immich-photo-manager"
elif command -v immich-photo-manager >/dev/null 2>&1; then
  SERVER_BIN=$(command -v immich-photo-manager)
else
  SERVER_BIN="uvx"
  SERVER_ARGS="immich-photo-manager"
fi

echo "Inspector -> ${SERVER_BIN} ${SERVER_ARGS:-} (Immich: ${IMMICH_BASE_URL})"
exec npx -y @modelcontextprotocol/inspector \
  -e IMMICH_BASE_URL="$IMMICH_BASE_URL" \
  -e IMMICH_API_KEY="$IMMICH_API_KEY" \
  -e MCP_TRANSPORT=stdio \
  "$SERVER_BIN" ${SERVER_ARGS:-}

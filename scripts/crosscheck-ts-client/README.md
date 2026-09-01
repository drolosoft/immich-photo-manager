# Cross-implementation check (TypeScript MCP SDK v2 client)

Proves the Python server speaks both MCP eras to a client written by someone
else. Runs the official TypeScript client (`@modelcontextprotocol/client@2.0.0`)
against this server over **stdio** and **Streamable HTTP**, in `legacy`,
`auto`, and `{pin: "2026-07-28"}` negotiation modes, and checks tool count,
a base64 thumbnail batch (byte-exact against `PNG_B64` when given), and an
image block.

```bash
cd scripts/crosscheck-ts-client && npm install

# 1) start the fake Immich (from repo root, in another shell)
PYTHONPATH=tests python -c "from fake_immich import FakeImmich,PNG; import base64,time; f=FakeImmich().__enter__(); print(f.base_url); print(base64.b64encode(PNG).decode()); time.sleep(3600)"

# 2) start the HTTP server (repo root, another shell)
PYTHONPATH=src IMMICH_BASE_URL=<fake url> IMMICH_API_KEY=fake-immich-key-0123456789abcdef MCP_PORT=8798 python -m immich_mcp_server --transport http

# 3) run the check
IMMICH_BASE_URL=<fake url> PNG_B64=<b64 from step 1> MCP_URL=http://127.0.0.1:8798/mcp node run.mjs
```

Against a real Immich, set `IMMICH_BASE_URL` / `IMMICH_API_KEY` and omit
`PNG_B64` (the batch check then only verifies structure). Expected output:
six lines, all `ok`, negotiating `2025-11-25` for `legacy` and `2026-07-28`
for `auto` and the pin.

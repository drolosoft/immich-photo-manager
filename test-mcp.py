#!/usr/bin/env python3
"""Test the Immich MCP server: initialize + list tools + call ping"""
import subprocess, json, os, sys

env = {
    **os.environ,
    "PYTHONPATH": os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"),
    "MCP_TRANSPORT": "stdio",
    "IMMICH_BASE_URL": os.environ.get("IMMICH_BASE_URL", "https://your-immich-server.com"),
    "IMMICH_API_KEY": os.environ.get("IMMICH_API_KEY", "your-api-key-here"),
}

requests = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "ping", "arguments": {}
    }},
]

stdin_data = "\n".join(json.dumps(r) for r in requests) + "\n"

proc = subprocess.run(
    [sys.executable, "-m", "immich_mcp_server"],
    input=stdin_data.encode(),
    capture_output=True,
    env=env,
)

print("=== IMMICH MCP SERVER TEST ===\n")

if proc.returncode != 0:
    print(f"ERROR: Server exited with code {proc.returncode}")
    print(f"Stderr: {proc.stderr.decode()}")
else:
    responses = []
    for line in proc.stdout.decode().strip().split("\n"):
        if line.strip():
            try:
                responses.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # Response 1: initialize
    if len(responses) >= 1:
        info = responses[0].get("result", {}).get("serverInfo", {})
        print(f"Server: {info.get('name')} v{info.get('version')}")
        print(f"Protocol: {responses[0].get('result', {}).get('protocolVersion')}")

    # Response 2: tools/list
    if len(responses) >= 2:
        tools = responses[1].get("result", {}).get("tools", [])
        print(f"\nTotal MCP tools: {len(tools)}")
        for i, t in enumerate(tools):
            print(f"  {i+1:2d}. {t['name']}")

    # Response 3: ping
    if len(responses) >= 3:
        ping_result = responses[2].get("result", {})
        content = ping_result.get("content", [{}])
        print(f"\nPing result: {content[0].get('text', 'N/A')}")

    print(f"\nStderr (server log):")
    for line in proc.stderr.decode().strip().split("\n"):
        print(f"  {line}")

print("\n=== TEST COMPLETE ===")

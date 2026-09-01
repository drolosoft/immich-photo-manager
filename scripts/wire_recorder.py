"""A minimal MCP server that records what a client sends it, verbatim.

Point any MCP client at this instead of a real server and read the log to
learn which protocol era it speaks: a first frame with method `initialize`
is a legacy client; one whose `params._meta` carries
`io.modelcontextprotocol/protocolVersion` is a modern (2026-07-28) client.

It answers the handshake and `tools/list` just well enough for the client to
consider the connection healthy, and appends every incoming frame as one JSON
line to the file named by WIRE_RECORDER_LOG.

Usage (any client config):

    {"command": "python3", "args": ["scripts/wire_recorder.py"],
     "env": {"WIRE_RECORDER_LOG": "/tmp/wire.jsonl"}}

Then read the first line of the log.
"""

import json
import os
import sys

log_path = os.environ["WIRE_RECORDER_LOG"]


def reply(payload):
    """Write one JSON-RPC frame to the client; stdout carries nothing else."""
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


with open(log_path, "a") as log:
    for line in sys.stdin:
        log.write(line)
        log.flush()
        try:
            frame = json.loads(line)
        except ValueError:
            continue

        method = frame.get("method")
        frame_id = frame.get("id")
        if method == "initialize":
            # Echo whatever version the client offered: the point is to keep
            # it talking, not to negotiate for real.
            offered = frame.get("params", {}).get("protocolVersion", "?")
            reply({
                "jsonrpc": "2.0",
                "id": frame_id,
                "result": {
                    "protocolVersion": offered,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "wire-recorder", "version": "0"},
                },
            })
        elif method == "tools/list":
            reply({"jsonrpc": "2.0", "id": frame_id, "result": {"tools": []}})
        elif frame_id is not None:
            reply({"jsonrpc": "2.0", "id": frame_id, "result": {}})

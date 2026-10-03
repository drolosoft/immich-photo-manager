"""
The file Claude Code runs when the plugin starts its MCP server.

The plugin manifest used to start the server as `python3 -m immich_mcp_server`
with `PYTHONPATH` pointing at this folder. The Claude directory reads a server
command only when it is a file inside the plugin called with plain arguments,
so this launcher is that file: it puts its own folder on `sys.path`, which is
what the PYTHONPATH did, and hands over to the package's console entry point,
which serves stdio by default. Nothing else lives here; every other route
(`uvx`, `python -m`, the Docker image) keeps its own entry point.
"""

import os
import sys

# This folder holds the `immich_mcp_server` package; putting it first means the
# plugin's own code wins over any other copy installed on the machine's python.
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))

if SOURCE_DIR not in sys.path:
    sys.path.insert(0, SOURCE_DIR)

from immich_mcp_server.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()

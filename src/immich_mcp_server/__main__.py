"""Entry point: python -m immich_mcp_server"""

import os


def _run(default_transport: str = "http"):
    """Run the MCP server with the given default transport.

    The MCP_TRANSPORT env var always takes precedence.
    """
    transport = os.environ.get("MCP_TRANSPORT", default_transport).lower()

    if transport == "stdio":
        from .server import mcp
        mcp.run(transport="stdio")
    else:
        import uvicorn
        port = int(os.environ.get("MCP_PORT", "8626"))
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        print(f"Immich MCP Server starting on {host}:{port}")
        uvicorn.run(
            "immich_mcp_server.server:app",
            host=host,
            port=port,
            log_level="info",
        )


def main():
    """Console script entry point (uvx). Defaults to stdio."""
    _run(default_transport="stdio")


if __name__ == "__main__":
    # python -m invocation. Defaults to http (backward compat).
    _run(default_transport="http")

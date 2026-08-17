"""Entry point: python -m immich_mcp_server"""

import argparse
import os


def _resolve_transport(cli_value: str | None, default_transport: str) -> str:
    """Resolve the transport with CLI flag > env var > default precedence."""
    return (cli_value or os.environ.get("MCP_TRANSPORT") or default_transport).lower()


def _run(default_transport: str = "http"):
    """Run the MCP server with the given default transport.

    Precedence: --transport CLI flag > MCP_TRANSPORT env var > default_transport.
    """
    parser = argparse.ArgumentParser(description="Immich MCP Server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default=None,
        help="Transport to use: 'stdio' or 'http'. Overrides MCP_TRANSPORT.",
    )
    args, _ = parser.parse_known_args()

    transport = _resolve_transport(args.transport, default_transport)

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

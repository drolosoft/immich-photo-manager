"""Entry point: python -m immich_mcp_server"""

import argparse
import os
import sys

from immich_mcp_server import __version__


def _check_sdk_version():
    """Fail with one clear message when the environment's mcp SDK cannot run us.

    The plugin route runs on whatever python the machine has; another install
    can silently downgrade or upgrade the shared `mcp` package there. Without
    this check the failure is a ModuleNotFoundError from deep inside the
    import chain, which tells the user nothing about the fix.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        sdk_version = version("mcp")
    except PackageNotFoundError:
        print(
            "immich-photo-manager: the 'mcp' package is not installed in this "
            "python. Install the server's dependencies: "
            "pip3 install -r src/requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1)

    major = int(sdk_version.split(".")[0])
    if not 2 <= major < 3:
        print(
            f"immich-photo-manager {__version__} needs mcp>=2.0.0,<3.0 but this "
            f"python has mcp {sdk_version}. Another install likely changed the "
            "shared environment. Fix: pip3 install -r src/requirements.txt "
            "(or run via 'uvx immich-photo-manager' for an isolated environment).",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _resolve_transport(cli_value: str | None, default_transport: str) -> str:
    """Resolve the transport with CLI flag > env var > default precedence."""
    return (cli_value or os.environ.get("MCP_TRANSPORT") or default_transport).lower()


def _run(default_transport: str = "http"):
    """Run the MCP server with the given default transport.

    Precedence: --transport CLI flag > MCP_TRANSPORT env var > default_transport.
    """
    parser = argparse.ArgumentParser(description="Immich MCP Server")
    # uvx keeps its environments under content-hashed paths, so "which version is
    # this?" cannot be answered from outside; this flag answers it in one call.
    parser.add_argument(
        "--version",
        action="version",
        version=f"immich-photo-manager {__version__}",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default=None,
        help="Transport to use: 'stdio' or 'http'. Overrides MCP_TRANSPORT.",
    )
    args, _ = parser.parse_known_args()

    _check_sdk_version()

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

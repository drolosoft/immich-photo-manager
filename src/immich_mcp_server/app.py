"""
Immich MCP app: FastMCP instance, lifespan and transport settings.

Part of the immich-photo-manager plugin.
License: MIT
"""

import os
import sys
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.transport_security import TransportSecuritySettings

from .immich_client import ImmichClient

# FastMCP's Settings model declares `lifespan` using a forward reference to the
# FastMCP class (defined later in the SDK), which pydantic-settings reports as an
# incomplete definition at startup. The field is never populated from environment
# variables, so this is harmless — silence it to keep startup logs clean.
try:
    from pydantic_settings.sources.utils import IncompleteFieldDefinitionWarning
except ImportError:  # pragma: no cover
    IncompleteFieldDefinitionWarning = None

if IncompleteFieldDefinitionWarning is not None:
    warnings.filterwarnings("ignore", category=IncompleteFieldDefinitionWarning)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialize the Immich client on server startup."""
    client = ImmichClient()
    # Verify connection at startup. Diagnostics go to stderr — under the
    # stdio transport stdout carries JSON-RPC and must stay pristine.
    try:
        await client.ping()
    except Exception as exc:
        print(
            f"Warning: Could not connect to Immich at {client.base_url}: {exc}",
            file=sys.stderr,
        )
    yield {"immich": client}


# When served over HTTP behind a reverse proxy, the proxied Host header (e.g.
# photos-mcp.example.com) must be allowed explicitly: FastMCP auto-enables DNS
# rebinding protection that accepts only 127.0.0.1/localhost Hosts, answering
# 421 Misdirected Request otherwise. MCP_ALLOWED_HOSTS is a comma-separated
# list of additional allowed Host values; localhost stays allowed and
# protection stays ON. Unset = SDK default behavior, unchanged.
_extra_hosts = [host.strip() for host in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if host.strip()]
_transport_security = None
if _extra_hosts:
    # A configured host may be a bare host/IP (allow any port via the SDK's
    # ":*" wildcard) or already include a port. The Host header always carries
    # the port, so a bare value like "192.168.1.10" would never match
    # "192.168.1.10:8626" — append a ":*" variant for portless entries.
    _allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    _allowed_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    for host in _extra_hosts:
        _allowed_hosts.append(host)
        if ":" not in host:
            _allowed_hosts.append(f"{host}:*")
        _allowed_origins.extend((f"http://{host}", f"https://{host}"))
    _transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_allowed_hosts,
        allowed_origins=_allowed_origins,
    )

mcp = FastMCP(
    "immich-photo-manager",
    instructions="Intelligent photo management for Immich. Search, curate albums, and publish galleries.",
    lifespan=app_lifespan,
    transport_security=_transport_security,
)


def _client(ctx: Context) -> ImmichClient:
    """Get the Immich client from the request context."""
    return ctx.request_context.lifespan_context["immich"]

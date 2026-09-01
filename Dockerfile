# Immich MCP Server as a container: HTTP transport on port 8626.
#
# Build:  docker build -t immich-photo-manager .
# Run:    docker run -p 8626:8626 \
#           -e IMMICH_BASE_URL=https://your-immich.example.com \
#           -e IMMICH_API_KEY=your-key \
#           ghcr.io/drolosoft/immich-photo-manager
#
# The server answers MCP on /mcp (both protocol eras) and liveness on /health.
# Mount a volume on /data to keep the PDFs and zips the tools write.

FROM python:3.13-slim

# PyAV, Pillow and fpdf2 all ship manylinux wheels for amd64 and arm64, so the
# image needs no compiler and no system ffmpeg.
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

# A container is reachable from outside only when the server binds beyond
# loopback; the CLI default of 127.0.0.1 stays for non-Docker runs.
ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8626 \
    MCP_TRANSPORT=http

# DNS-rebinding protection stays ON with its localhost default, which covers
# the common `-p 8626:8626` + http://localhost:8626 setup. Reaching the
# container under any other name (a reverse proxy, another container) needs
# that name in MCP_ALLOWED_HOSTS, e.g. -e MCP_ALLOWED_HOSTS=photos-mcp.example.com

RUN useradd --create-home server && mkdir /data && chown server /data
USER server

# The tools that write files (export_pdf, download_archive) resolve relative
# paths against the working directory, so /data is where a mounted volume
# catches them.
WORKDIR /data

EXPOSE 8626

# Liveness only: /health answers without credentials and without touching
# Immich, so a missing API key never flaps the container.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD \
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8626/health', timeout=4)"

ENTRYPOINT ["python", "-m", "immich_mcp_server"]

# Immich MCP Server — production image
#
# Build:
#   docker build -t immich-photo-manager:latest .
#
# Run (HTTP mode, the default for `python -m immich_mcp_server`):
#   docker run -d --name immich-mcp \
#     -e IMMICH_BASE_URL=http://your-server:2283 \
#     -e IMMICH_API_KEY=your-api-key \
#     -e MCP_ALLOWED_HOSTS=192.168.1.10 \
#     -p 8626:8626 \
#     immich-photo-manager:latest

FROM python:3.12-slim

WORKDIR /app

# Install the package (hatchling builds the wheel from src/immich_mcp_server).
# Only the files below are needed for the build; everything else is excluded
# via .dockerignore.
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

# Default HTTP listen address/port for `python -m immich_mcp_server`.
ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8626

EXPOSE 8626

# Run the server. `python -m immich_mcp_server` defaults to http transport.
CMD ["python", "-m", "immich_mcp_server"]
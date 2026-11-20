FROM python:3.13-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Run as an unprivileged user; the application files stay owned by root (read-only to it)
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin mcp

# Copy application files
COPY meraki_mcp_config.py meraki-mcp.py meraki-mcp-dynamic.py ./
COPY entrypoint.sh ./
RUN chmod 755 entrypoint.sh

# Cache directory is the only path the server writes to; owner-only because
# cached responses can contain sensitive configuration
RUN mkdir -p /app/.meraki_cache && chown mcp:mcp /app/.meraki_cache && chmod 700 /app/.meraki_cache

# Default configuration for Docker (HTTP mode, bind to all interfaces inside the container).
# Set MCP_AUTH_TOKEN to require "Authorization: Bearer <token>" on every request.
ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV MCP_SERVER=dynamic
ENV RESPONSE_CACHE_DIR=/app/.meraki_cache

USER mcp

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]

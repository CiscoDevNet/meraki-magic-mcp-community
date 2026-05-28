FROM python:3.13-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY meraki_mcp_config.py meraki-mcp.py meraki-mcp-dynamic.py .env-example ./
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Create cache directory
RUN mkdir -p /app/.meraki_cache

# Default configuration for Docker (HTTP mode, bind to all interfaces)
ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV MCP_SERVER=dynamic
ENV RESPONSE_CACHE_DIR=/app/.meraki_cache

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]

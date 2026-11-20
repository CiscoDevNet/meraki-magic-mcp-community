#!/bin/bash
set -e

# Select server file based on MCP_SERVER env var
if [ "${MCP_SERVER}" = "manual" ]; then
    SERVER_FILE="/app/meraki-mcp.py"
    echo "Starting Meraki Magic MCP (Manual - curated tools)" >&2
else
    SERVER_FILE="/app/meraki-mcp-dynamic.py"
    echo "Starting Meraki Magic MCP (Dynamic - full API)" >&2
fi

echo "Transport: ${MCP_TRANSPORT:-stdio}" >&2
echo "Host: ${MCP_HOST:-127.0.0.1}" >&2
echo "Port: ${MCP_PORT:-8000}" >&2

exec python "${SERVER_FILE}"

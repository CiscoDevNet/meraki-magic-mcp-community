# Meraki Magic MCP - Agent Guide

## Dev environment tips

- **Python version**: Use Python 3.13+.
- **Virtual env (recommended)**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install -U pip
  pip install -r requirements.txt
  ```

- **Dependencies**: `pyproject.toml` is the single source of truth for direct dependencies and their allowed ranges. `requirements.txt` is the lockfile generated from it and is what `pip`, Docker and CI install. Do not edit `requirements.txt` by hand; after changing `pyproject.toml`, or to pick up new releases, regenerate it with [uv](https://docs.astral.sh/uv/) and commit both files:
  ```bash
  uv pip compile pyproject.toml -o requirements.txt --universal            # apply pyproject.toml changes, keep other pins
  uv pip compile pyproject.toml -o requirements.txt --universal --upgrade  # also move every pin to the latest allowed version
  ```
  The unit tests fail if the two files disagree.

- **Environment setup**: Do not use a project `.env` file. Set `MERAKI_API_KEY` (required) and optional vars such as `MERAKI_ORG_ID` in the MCP client `env` block, or export them in the process environment:
  ```bash
  export MERAKI_API_KEY="your_api_key_here"
  export MERAKI_ORG_ID="your_org_id_here"
  ```

### Quick run examples

```bash
# Run the dynamic MCP server (recommended, ~804 endpoints)
python meraki-mcp-dynamic.py

# Run the manual MCP server (40 curated endpoints)
python meraki-mcp.py

# Run over HTTP transport
MCP_TRANSPORT=http python meraki-mcp-dynamic.py

# Run with Docker (requires MERAKI_API_KEY in the host environment)
docker compose up -d
```

## Testing instructions

- **Run the unit tests** (no Meraki credentials needed; CI runs the same command on every pull request):

  ```bash
  python -m unittest discover -s tests -v
  ```

- **MCP server links**

  This project is an MCP server built with [FastMCP](https://github.com/jlowin/fastmcp) and the [Meraki Python SDK](https://github.com/meraki/dashboard-api-python).

- **Test the code with the Cisco DevNet sandbox**

  Visit https://devnetsandbox.cisco.com/DevNet to book a Meraki sandbox.

- **Latest Cisco Meraki API documentation**:

  https://developer.cisco.com/meraki/api-v1/

- **Meraki OpenAPI spec**:

  https://github.com/meraki/openapi

## PR instructions

- **Security**: Do not commit real credentials or tokens. Use placeholders and document required env vars. Pass secrets through the MCP client `env` block or the process environment; never commit them.

## Contribution conventions

- **Backward compatibility**: Do not change existing sample behavior unless clearly improving or fixing a bug; document changes.

# Technology Stack

**Analysis Date:** 2026-03-27

## Languages

**Primary:**
- Python 3.13+ - application code lives in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `inspect_tools.py`; the minimum version is declared in `pyproject.toml` and pinned in `.python-version`.

**Secondary:**
- Bash - container startup logic lives in `entrypoint.sh`.
- YAML - container orchestration lives in `docker-compose.yml`.
- Markdown/JSON examples - operational setup and client config examples live in `README.md`, `README-DYNAMIC.md`, `INSTALL.md`, and `QUICKSTART.md`.

## Runtime

**Environment:**
- CPython 3.13 - required by `pyproject.toml` (`requires-python = ">=3.13"`) and by the Docker base image in `Dockerfile` (`python:3.13-slim`).
- The server runs in either `stdio`, `http`/StreamableHTTP, or `sse` mode based on environment variables read in `meraki-mcp.py` and `meraki-mcp-dynamic.py`.

**Package Manager:**
- `pip` with a virtualenv is the documented install path in `AGENTS.md`, `README.md`, `QUICKSTART.md`, and `INSTALL.md`.
- Dependency manifests:
  - `requirements.txt` is the practical install source for local setup and Docker builds because both docs and `Dockerfile` install from it.
  - `pyproject.toml` contains lightweight project metadata and a shorter dependency list.
- Lockfile: missing. `uv.lock` is ignored in `.gitignore` and is not present in the repository.

## Frameworks

**Core:**
- FastMCP 3.0.2 in `requirements.txt` - hosts the MCP server in `meraki-mcp.py` and `meraki-mcp-dynamic.py` via `from mcp.server.fastmcp import FastMCP`.
- MCP Python SDK 1.26.0 in `requirements.txt` - supplies MCP protocol support and CLI tooling used by the documented `fastmcp run -t ...` commands in `README.md`, `README-DYNAMIC.md`, `QUICKSTART.md`, and `INSTALL.md`.
- Cisco Meraki Python SDK 2.0.2 in `requirements.txt` and `pyproject.toml` - all network-management operations go through `meraki.DashboardAPI(...)` in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `inspect_tools.py`.
- Pydantic 2.12.5 in `requirements.txt` - request schemas and typed tool arguments are defined in `meraki-mcp.py`; `Field` metadata is also used in `meraki-mcp-dynamic.py`.

**Testing:**
- `pytest` 7.4.4 is present in `requirements.txt`, but no `tests/` directory, `pytest.ini`, or committed test suite was detected in the repository root.

**Build/Dev:**
- `python-dotenv` 1.1.0 in `requirements.txt` - `.env` loading is performed in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `inspect_tools.py`.
- Docker - image build is defined in `Dockerfile`, and local container orchestration is defined in `docker-compose.yml`.
- `uvicorn` 0.41.0 in `requirements.txt` - available for external ASGI hosting; both server modules expose `app = mcp.streamable_http_app()` for that use in `meraki-mcp.py` and `meraki-mcp-dynamic.py`.

## Key Dependencies

**Critical:**
- `meraki==2.0.2` in `requirements.txt` - primary API client for all Meraki dashboard operations invoked by both MCP variants.
- `fastmcp==3.0.2` in `requirements.txt` - MCP server framework used to register tools/resources and run transports in both server entry points.
- `mcp==1.26.0` in `requirements.txt` - protocol/CLI dependency behind the documented `fastmcp` launcher flow.
- `pydantic==2.12.5` in `requirements.txt` - validates complex tool inputs like SSID, firewall, and action-batch payloads in `meraki-mcp.py`.

**Infrastructure:**
- `python-dotenv==1.1.0` in `requirements.txt` - loads local environment configuration from the repo-root `.env`.
- `uvicorn==0.41.0` in `requirements.txt` - optional ASGI serving for the exported `app` object.
- `requests==2.32.3` and transitive HTTP stack packages in `requirements.txt` - HTTP transport for the Meraki SDK.
- `sse-starlette==2.3.4`, `starlette==0.46.2`, and `websockets==15.0.1` in `requirements.txt` - support MCP HTTP/SSE serving through the FastMCP stack.

## Configuration

**Environment:**
- Local configuration is loaded from the repo-root `.env` by `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `inspect_tools.py`. The committed shape is documented in `.env-example`; the real `.env` file exists and is ignored by `.gitignore`.
- Required config:
  - `MERAKI_API_KEY` - required by both server variants before `meraki.DashboardAPI(...)` is created.
  - `MERAKI_ORG_ID` - optional default organization ID used when tools omit an org identifier.
- Runtime config exposed in `.env-example` and consumed in `meraki-mcp-dynamic.py`:
  - `ENABLE_CACHING`
  - `CACHE_TTL_SECONDS`
  - `READ_ONLY_MODE`
  - `ENABLE_FILE_CACHING`
  - `MAX_RESPONSE_TOKENS`
  - `MAX_PER_PAGE`
  - `RESPONSE_CACHE_DIR`
  - `MCP_TRANSPORT`
  - `MCP_HOST`
  - `MCP_PORT`
- Container-only selection config:
  - `MCP_SERVER` in `docker-compose.yml`, `Dockerfile`, and `entrypoint.sh` switches between `meraki-mcp-dynamic.py` and `meraki-mcp.py`.

**Build:**
- `Dockerfile` builds a Python 3.13 slim image, installs `requirements.txt`, copies the two server files plus `.env-example`, and sets HTTP-friendly defaults.
- `docker-compose.yml` binds port `8000`, mounts the named volume `meraki-cache`, reads secrets from `.env`, and defaults to the dynamic server.
- `pyproject.toml` provides project metadata but is not sufficient alone to reproduce the fully pinned environment in `requirements.txt`.

## Platform Requirements

**Development:**
- Python 3.13+ with a virtualenv, per `AGENTS.md` and `INSTALL.md`.
- `pip install -r requirements.txt` for the runtime used by the documented `fastmcp` launcher commands.
- Optional Node.js only when using `mcp-remote` to connect Claude Desktop to an HTTP-hosted server, as documented in `README.md` and `INSTALL.md`.
- Docker Desktop or compatible Docker Engine for containerized runs via `docker compose up -d`.

**Production:**
- No dedicated production platform is encoded in the repo. The supported deployment targets are:
  - local Python process running `meraki-mcp.py` or `meraki-mcp-dynamic.py`
  - HTTP/SSE process exposing `/mcp` from the FastMCP app in `meraki-mcp.py` or `meraki-mcp-dynamic.py`
  - Docker container built from `Dockerfile` and run directly or through `docker-compose.yml`

## Dependency Source Notes

- `pyproject.toml` specifies lower bounds such as `fastmcp>=2.14.5` and `uvicorn>=0.34.0`.
- `requirements.txt` pins the concrete environment actually used by docs and Docker, including `fastmcp==3.0.2`, `mcp==1.26.0`, `pydantic==2.12.5`, and `uvicorn==0.41.0`.
- Use `requirements.txt` as the authoritative runtime snapshot for reproducing this repository; use `pyproject.toml` as metadata and minimum-version guidance.

---

*Stack analysis: 2026-03-27*

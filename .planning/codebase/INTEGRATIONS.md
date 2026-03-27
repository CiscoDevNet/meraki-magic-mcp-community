# External Integrations

**Analysis Date:** 2026-03-27

## APIs & External Services

**Network Management API:**
- Cisco Meraki Dashboard API - the core external service used for all operational reads and writes.
  - SDK/Client: `meraki==2.0.2` from `requirements.txt`
  - Implementation: `meraki.DashboardAPI(...)` in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `inspect_tools.py`
  - Auth: `MERAKI_API_KEY` from the repo-root `.env`, with optional default scoping from `MERAKI_ORG_ID`
  - Behavior: both server variants enable SDK retry/rate-limit handling; the dynamic variant adds response caching and read-only blocking in `meraki-mcp-dynamic.py`

**MCP Client Integrations:**
- Claude Desktop / Cursor - local client integrations documented in `README.md`, `README-DYNAMIC.md`, `QUICKSTART.md`, and `INSTALL.md`.
  - SDK/Client: FastMCP CLI entry point from the installed Python environment (`.venv/bin/fastmcp` or Windows equivalent)
  - Auth: none in the repo; clients launch the local process directly over `stdio`
- `mcp-remote` / Node.js bridge - documented for connecting Claude Desktop to HTTP-hosted instances in `README.md`, `README-DYNAMIC.md`, and `INSTALL.md`.
  - SDK/Client: `npx -y mcp-remote http://<host>:8000/mcp`
  - Auth: none configured in the repo; network exposure is controlled outside the application

**Container Runtime:**
- Docker / Docker Compose - deployment integration defined in `Dockerfile`, `docker-compose.yml`, and `entrypoint.sh`.
  - Runtime behavior: `entrypoint.sh` selects `meraki-mcp-dynamic.py` or `meraki-mcp.py` from `MCP_SERVER`
  - Auth: secrets are injected through `.env` referenced by `docker-compose.yml`

**Optional Sandbox Environment:**
- Cisco DevNet Meraki sandbox - referenced in `AGENTS.md` as the recommended external environment for manual testing against non-production infrastructure.
  - SDK/Client: same `meraki` SDK usage as production
  - Auth: sandbox-issued Meraki credentials supplied through `.env`

## Data Storage

**Databases:**
- Not detected. No relational database, ORM, migration tool, or persistent application database config appears in `pyproject.toml`, `requirements.txt`, or the Python entry points.

**File Storage:**
- Local filesystem only.
  - Cache directory: `.meraki_cache/` at the repo root by default, documented in `.env-example`, created and used in `meraki-mcp-dynamic.py`, and mounted as a Docker volume in `docker-compose.yml`
  - Stored data: large truncated API responses are persisted as JSON files by `save_response_to_file(...)` in `meraki-mcp-dynamic.py`

**Caching:**
- In-memory TTL cache in `meraki-mcp-dynamic.py` via the `SimpleCache` class
  - Control vars: `ENABLE_CACHING` and `CACHE_TTL_SECONDS` from `.env-example`
- File-backed response cache in `meraki-mcp-dynamic.py`
  - Control vars: `ENABLE_FILE_CACHING`, `MAX_RESPONSE_TOKENS`, `MAX_PER_PAGE`, and `RESPONSE_CACHE_DIR`
  - Access helpers: `get_cached_response`, `list_cached_responses`, and `clear_cached_files` tools in `meraki-mcp-dynamic.py`

## Authentication & Identity

**Auth Provider:**
- Cisco Meraki API key authentication
  - Implementation: `MERAKI_API_KEY` is loaded with `load_dotenv(...)` and passed into `meraki.DashboardAPI(...)` in both `meraki-mcp.py` and `meraki-mcp-dynamic.py`
  - Default tenant scoping: `MERAKI_ORG_ID` is used automatically when a tool call omits an organization identifier in both variants

**Client/User Authentication:**
- Not detected for the MCP server itself.
  - The HTTP endpoint exposed by `mcp.streamable_http_app()` in `meraki-mcp.py` and `meraki-mcp-dynamic.py` does not add built-in auth, sessions, or identity middleware.
  - Access control is operational rather than application-level: local `stdio` launch, network placement of the HTTP server, and optional `READ_ONLY_MODE` in `meraki-mcp-dynamic.py`.

## Monitoring & Observability

**Error Tracking:**
- None detected. No Sentry, OpenTelemetry exporter setup, or external error collector is configured in code or repo config files.

**Logs:**
- Minimal process logging to stderr from `entrypoint.sh`, `meraki-mcp.py`, and `meraki-mcp-dynamic.py`
- Meraki SDK internal logging is explicitly suppressed in both server variants via `suppress_logging=True`
- Operational introspection is exposed through MCP tools rather than a logging backend:
  - `cache_stats`, `get_mcp_config`, and method discovery tools in `meraki-mcp-dynamic.py`
  - `get_organization_api_requests` and `get_organization_webhook_logs` in `meraki-mcp.py`

## CI/CD & Deployment

**Hosting:**
- Local host execution from `meraki-mcp.py` or `meraki-mcp-dynamic.py`
- HTTP/SSE service using the exported FastMCP ASGI app in `meraki-mcp.py` and `meraki-mcp-dynamic.py`
- Docker containerized deployment from `Dockerfile` and `docker-compose.yml`

**CI Pipeline:**
- None detected. No `.github/workflows/`, CI config files, or deployment automation files are present in the repository.

## Environment Configuration

**Required env vars:**
- `MERAKI_API_KEY` - required in `meraki-mcp.py` and `meraki-mcp-dynamic.py`
- `MERAKI_ORG_ID` - optional default organization scope in both server variants
- `MCP_TRANSPORT` - transport selection for `stdio`, `http`, or `sse`, read in both server variants
- `MCP_HOST` and `MCP_PORT` - bind settings for HTTP/SSE mode in both server variants
- `MCP_SERVER` - container startup selector in `entrypoint.sh` and `docker-compose.yml`
- Dynamic-server-only controls from `.env-example` and `meraki-mcp-dynamic.py`:
  - `ENABLE_CACHING`
  - `CACHE_TTL_SECONDS`
  - `READ_ONLY_MODE`
  - `ENABLE_FILE_CACHING`
  - `MAX_RESPONSE_TOKENS`
  - `MAX_PER_PAGE`
  - `RESPONSE_CACHE_DIR`

**Secrets location:**
- Local development: repo-root `.env` file, which exists and is ignored by `.gitignore`
- Container deployment: `.env` loaded through `env_file` in `docker-compose.yml`
- Safe template: `.env-example` documents the expected variables without real credentials

## Webhooks & Callbacks

**Incoming:**
- None detected. No webhook receiver routes, callback handlers, or HTTP endpoints beyond the MCP transport are implemented in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, or `entrypoint.sh`.

**Outgoing:**
- Direct HTTPS requests to the Cisco Meraki Dashboard API through the `meraki` SDK in both server variants
- No custom outbound webhook sender is implemented in repository code
- Webhook-adjacent visibility only:
  - `get_organization_webhook_logs(...)` in `meraki-mcp.py` reads webhook delivery logs from Meraki
  - `call_meraki_api(...)` in `meraki-mcp-dynamic.py` can reach webhook-related Meraki SDK methods when exposed by the API

## Transport Surface

**Local process mode:**
- `stdio` is the default in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, `.env-example`, and the setup docs

**Remote/service mode:**
- `http` is mapped to FastMCP StreamableHTTP in both server variants by converting `MCP_TRANSPORT=http` to `transport="streamable-http"`
- `sse` is supported as an alternate server transport in both server variants
- The documented HTTP endpoint is `/mcp`, as shown in `README.md` and `INSTALL.md`

---

*Integration audit: 2026-03-27*

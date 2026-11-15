# Codebase Concerns

**Analysis Date:** 2026-11-15

This replaces the 2026-03-27 audit. Items from that audit that have since been fixed are listed at the end so they are not re-reported. The other documents in `.planning/codebase/` are still the 2026-03-27 snapshot and predate several dependency upgrades; check them against the code before relying on them.

## Security Considerations

**HTTP transports have no authentication:**
- Risk: Both servers expose HTTP/SSE transports through `FastMCP` without authentication, authorization, or TLS. `Dockerfile` sets `MCP_HOST=0.0.0.0` and `docker-compose.yml` publishes port `8000` on all host interfaces. Anyone who can reach the port can call every tool with the configured Meraki API key.
- Files: `meraki-mcp.py`, `meraki-mcp-dynamic.py`, `Dockerfile`, `docker-compose.yml`
- Current mitigation: `READ_ONLY_MODE` defaults to `true` in both servers, and stdio/loopback are the defaults outside Docker.
- Recommendations: Publish the compose port on `127.0.0.1` by default, add a bearer-token check for HTTP mode, document TLS termination at a reverse proxy, and run the container as a non-root user.

**Cached responses on disk contain Meraki data:**
- Risk: Large dynamic responses are written to `RESPONSE_CACHE_DIR` with the request parameters and full payload, which can include secrets such as SSID pre-shared keys. `get_cached_response` and `list_cached_responses` expose them over MCP.
- Files: `meraki-mcp-dynamic.py`
- Current mitigation: Files and the directory are created owner-only, paths are confined to the cache directory, and files are pruned by age (`RESPONSE_CACHE_MAX_AGE_HOURS`) and total size (`RESPONSE_CACHE_MAX_MB`).
- Recommendations: Consider disabling file caching by default for shared HTTP deployments and returning file names instead of absolute paths.

**Raw exception strings are returned to clients:**
- Risk: The dynamic server's generic exception handler returns `str(e)`, and the manual server lets exceptions propagate to FastMCP. In shared HTTP deployments this can expose internal paths or library details.
- Files: `meraki-mcp-dynamic.py`, `meraki-mcp.py`
- Recommendations: Log details server-side and return sanitized errors.

## Tech Debt

**Two servers with overlapping scope:**
- Issue: `meraki-mcp.py` hand-wraps 83 SDK methods that `call_meraki_api` in `meraki-mcp-dynamic.py` can already reach. Features added to one server (response size limits, caching, structured errors) are not present in the other.
- Files: `meraki-mcp.py`, `meraki-mcp-dynamic.py`
- Fix approach: Keep the manual server for genuinely curated workflows and share helpers through `meraki_mcp_config.py` instead of duplicating them.

**Manual tools pass their own method names to the write guard:**
- Issue: Each manual write tool calls `_guard_write("<sdkMethodName>")` by hand. A new write tool that omits the call is not blocked by `READ_ONLY_MODE`.
- Files: `meraki-mcp.py`
- Current mitigation: Tests check that guarded names exist in the SDK, but not that every write tool is guarded.
- Fix approach: Add a test that fails when a tool calls a non-read SDK method without a guard, or route SDK calls through one guarded helper.

**Documentation is spread over seven overlapping guides:**
- Issue: `README.md`, `README-DYNAMIC.md`, `INSTALL.md`, `QUICKSTART.md`, `OPTIMIZATIONS.md`, `COMPARISON.md` and `UPDATE_GUIDE.md` repeat setup and usage guidance.
- Current mitigation: A test fails when the docs mention tool names that no longer exist or the old endpoint counts.
- Fix approach: Treat one file as the source of truth per topic and link to it from the others.

## Performance Bottlenecks

**Manual tools return entire datasets in one response:**
- Problem: Several manual tools request `total_pages='all'` with `perPage=1000` and return the full payload.
- Files: `meraki-mcp.py`
- Improvement path: Reuse the dynamic server's truncation and file-cache handling, or return paginated windows.

**No explicit concurrency limit:**
- Problem: SDK calls run in the default thread pool via `asyncio.to_thread(...)` with no bound, timeout or backpressure.
- Files: `meraki-mcp.py`, `meraki-mcp-dynamic.py`
- Improvement path: Bound concurrency and add request timeouts before positioning HTTP mode as a shared service.

## Fragile Areas

**Write and destructive classification is based on method names:**
- Files: `meraki_mcp_config.py`
- Why fragile: Read-only mode treats every method that is not `get*`/`list*` as a write, which fails closed. Whether a write also needs `confirm_destructive_action` still depends on the reviewed verb lists.
- Current mitigation: Tests run against the installed SDK and fail on an unreviewed verb or a delete-like method that is not classified as destructive.

**Replacements for removed SDK methods are untested against a live organization:**
- Files: `meraki-mcp.py`
- Why fragile: `get_device_status`, `get_device_uplink`, `get_organization_status`, `get_security_center`, `get_switch_vlans` and `create_switch_vlan` were re-pointed at current SDK methods and verified only with the HTTP layer stubbed.
- Safe modification: Exercise them against a DevNet sandbox before a release.

## Missing Features

**No integration tests:**
- Problem: The unit tests stub the SDK client or inspect it without making API calls. Nothing exercises a real Meraki organization or the HTTP transports end to end.

**No production-grade observability:**
- Problem: Both servers suppress Meraki SDK logging and add no structured logging, metrics or health endpoint.

## Resolved Since the 2026-03-27 Audit

- Manual tools calling SDK methods that no longer exist: fixed, with a test that checks every referenced method against the installed SDK.
- `READ_ONLY_MODE` missing from the manual server and defaulting to off: both servers now default to read-only.
- Read-only mode bypassable through unlisted verbs or the client's internal HTTP session: fixed.
- No automated tests or CI: `tests/` runs in `.github/workflows/tests.yml` on every pull request.
- Dependencies declared in two places: `pyproject.toml` is the source of truth and `requirements.txt` is the lockfile generated from it.
- Unbounded in-memory and file caches: both are bounded.
- Docs referring to tools that do not exist and to outdated endpoint counts: fixed.
- Credentials loaded from a project `.env` file: the servers read the process environment only.

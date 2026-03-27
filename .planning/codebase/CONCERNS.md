# Codebase Concerns

**Analysis Date:** 2026-03-27

## Tech Debt

**Manual server duplication and drift pressure:**
- Issue: `meraki-mcp.py` is a 1k+ line hand-maintained wrapper with 83 `@mcp.tool()` registrations, while `meraki-mcp-dynamic.py` already provides a generic SDK bridge. The manual surface duplicates SDK method mapping work and has already drifted from the installed Meraki SDK.
- Files: `meraki-mcp.py`, `meraki-mcp-dynamic.py`, `README.md`, `COMPARISON.md`
- Impact: Every SDK upgrade requires manual auditing of dozens of wrappers and docs. Broken manual tools can survive until a user triggers them.
- Fix approach: Keep `meraki-mcp.py` limited to genuinely curated workflows, move routine endpoint exposure to `meraki-mcp-dynamic.py`, and back the remaining manual tools with compatibility tests against the installed SDK.

**Multiple dependency definitions with no lockfile:**
- Issue: `pyproject.toml` uses broad version ranges while `requirements.txt` pins a different installation surface. There is no committed lockfile.
- Files: `pyproject.toml`, `requirements.txt`
- Impact: Install behavior depends on which file a contributor uses. SDK or transport-layer behavior can change without a code change in this repo.
- Fix approach: Pick a single source of truth for application dependencies, generate a lockfile, and document one install path.

**Documentation overstates and contradicts implementation:**
- Issue: The docs claim a "40 curated endpoints" manual server, "operation labeling", and several helper/tool names that do not match the current code.
- Files: `README.md`, `README-DYNAMIC.md`, `INSTALL.md`, `OPTIMIZATIONS.md`, `COMPARISON.md`, `meraki-mcp.py`, `meraki-mcp-dynamic.py`
- Impact: Operator expectations diverge from runtime behavior, and support/debugging time increases because examples are not trustworthy.
- Fix approach: Generate docs from live tool metadata where possible and add a docs verification pass that checks example tool names against the running server.

## Known Bugs

**Manual device status tool calls a non-existent SDK method:**
- Symptoms: Invoking `get_device_status` will fail at runtime because `dashboard.devices.getDeviceStatuses` is not present in the installed Meraki SDK.
- Files: `meraki-mcp.py`
- Trigger: Call `get_device_status(serial=...)`.
- Workaround: Use `search_methods(keyword="status")` and `get_method_info(...)` in `meraki-mcp-dynamic.py` to find the current SDK equivalent before calling it through `call_meraki_api(...)`.

**Manual device uplink tool calls a non-existent SDK method:**
- Symptoms: Invoking `get_device_uplink` will fail at runtime because `dashboard.devices.getDeviceUplink` is not present in the installed Meraki SDK.
- Files: `meraki-mcp.py`
- Trigger: Call `get_device_uplink(serial=...)`.
- Workaround: Use the discovery helpers in `meraki-mcp-dynamic.py` to find the current devices/uplink endpoint and call that instead.

**Dynamic README examples refer to tools that do not exist:**
- Symptoms: The documented examples use `list_available_tools`, `search_tools`, `get_tool_info`, `organizations_getOrganizations`, and `networks_getNetworkClients`, but the implementation exposes `list_all_methods`, `search_methods`, `get_method_info`, 12 pre-registered tool names, and `call_meraki_api(...)`.
- Files: `README-DYNAMIC.md`, `meraki-mcp-dynamic.py`
- Trigger: Follow the "Example Usage in Claude" or "Testing" sections in `README-DYNAMIC.md`.
- Workaround: Use `get_mcp_config`, `list_all_methods`, `search_methods`, `get_method_info`, and `call_meraki_api(...)` from `meraki-mcp-dynamic.py`.

## Security Considerations

**Unauthenticated remote control plane for a write-capable admin API:**
- Risk: Both server files expose HTTP/SSE transports through `FastMCP` and `mcp.streamable_http_app()` without any authentication, authorization, or TLS enforcement. `docker-compose.yml` publishes port `8000`, `Dockerfile` defaults to HTTP mode, and `.env-example` defaults `READ_ONLY_MODE=false`. The manual server has no read-only gate at all.
- Files: `meraki-mcp.py`, `meraki-mcp-dynamic.py`, `Dockerfile`, `docker-compose.yml`, `.env-example`
- Current mitigation: None in code beyond optional loopback binding and optional `READ_ONLY_MODE` in `meraki-mcp-dynamic.py`.
- Recommendations: Default to loopback and read-only mode, require auth in front of HTTP mode, terminate TLS at a reverse proxy, and add explicit warnings that the manual server is always write-capable.

**Sensitive Meraki data is cached to disk and re-exposed via MCP:**
- Risk: Large dynamic responses are written as JSON files containing request parameters and full response payloads. The server then exposes absolute cache paths and retrieval tools over MCP.
- Files: `meraki-mcp-dynamic.py`, `.env-example`, `Dockerfile`, `docker-compose.yml`
- Current mitigation: `_validate_cache_filepath(...)` prevents path traversal outside `RESPONSE_CACHE_DIR`.
- Recommendations: Disable file caching by default for shared deployments, avoid returning absolute paths, add file permission hardening and retention limits, and treat cached responses as sensitive data equal to API output.

**Raw exception strings are returned to clients:**
- Risk: Generic exception handlers serialize `str(e)` directly into JSON responses. In shared HTTP deployments this can leak internal path, parameter, or library details to callers.
- Files: `meraki-mcp-dynamic.py`
- Current mitigation: Meraki API errors are normalized in one branch.
- Recommendations: Replace generic exception passthrough with structured server-side logging and sanitized client-facing errors.

## Performance Bottlenecks

**Manual endpoints fetch entire datasets into one MCP response:**
- Problem: Several manual tools request `total_pages='all'` and `perPage=1000`, then serialize the full payload with `json.dumps(..., indent=2)`.
- Files: `meraki-mcp.py`
- Cause: The manual server does not implement the pagination, truncation, or file-backed overflow controls present in `meraki-mcp-dynamic.py`.
- Improvement path: Port the dynamic response-size controls into the manual tools or make the manual server return paginated windows instead of full datasets.

**Dynamic file cache grows without an automatic quota or eviction policy:**
- Problem: Cached JSON files persist under `.meraki_cache` or the Docker volume until a user manually calls `clear_cached_files(...)`.
- Files: `meraki-mcp-dynamic.py`, `docker-compose.yml`, `Dockerfile`
- Cause: There is no size cap, age-based startup cleanup, or background maintenance job.
- Improvement path: Add quota-based eviction, startup cleanup, and documented retention defaults for long-running containers.

**All SDK operations run in the default thread pool:**
- Problem: The server wraps synchronous SDK calls with `asyncio.to_thread(...)`, which works for low throughput but provides no explicit concurrency control for shared HTTP use.
- Files: `meraki-mcp.py`, `meraki-mcp-dynamic.py`
- Cause: The Meraki SDK is synchronous and the server relies on implicit threadpool behavior.
- Improvement path: Bound concurrency, add request timeouts and backpressure, and document expected throughput limits for HTTP mode.

## Fragile Areas

**Manual SDK wrappers are fragile under SDK evolution:**
- Files: `meraki-mcp.py`
- Why fragile: Each tool names Meraki SDK methods directly. A rename or signature change breaks only that tool, and there is no centralized compatibility check.
- Safe modification: Verify every touched wrapper against the installed SDK before release and prefer discovery-based or generated wrappers where possible.
- Test coverage: No repository test files were detected for manual tool registration or invocation.

**Read-only enforcement in the dynamic server is heuristic:**
- Files: `meraki-mcp-dynamic.py`
- Why fragile: `READ_ONLY_MODE` and cache invalidation rely on verb-prefix lists in `READ_ONLY_PREFIXES` and `WRITE_PREFIXES`. New or renamed mutating SDK methods can bypass the safeguard if their names do not match the current prefixes.
- Safe modification: Derive mutability from an authoritative API schema or maintain an explicit allow/deny map that is validated against the current SDK method list at startup.
- Test coverage: No automated tests were found for read-only classification or cache invalidation behavior.

**The docs set is large, overlapping, and easy to desynchronize:**
- Files: `README.md`, `README-DYNAMIC.md`, `INSTALL.md`, `QUICKSTART.md`, `OPTIMIZATIONS.md`, `COMPARISON.md`, `UPDATE_GUIDE.md`
- Why fragile: Setup, transport, performance, and usage guidance is repeated across multiple long documents with overlapping examples.
- Safe modification: Treat one file as the source of truth per topic and generate or lint repeated snippets.
- Test coverage: No docs-lint or example-validation workflow was detected.

## Scaling Limits

**Shared HTTP deployment does not scale safely beyond trusted local use:**
- Current capacity: One Python process, synchronous SDK calls wrapped in threads, no auth, no explicit rate limiting, no health checks, and no structured metrics.
- Limit: Once the server is used by multiple operators or exposed beyond localhost, it becomes difficult to control throughput, audit access, or protect write operations.
- Scaling path: Add auth, reverse-proxy controls, health endpoints, metrics, structured logs, and worker/process management before positioning HTTP mode as a shared service.

**Response cache storage has unbounded growth characteristics:**
- Current capacity: Cache growth is limited only by available disk space in `.meraki_cache` or the `meraki-cache` Docker volume.
- Limit: Large organizations and repeated inventory/event queries can accumulate sizable JSON artifacts over time.
- Scaling path: Add retention-by-default, a disk quota, and observability around cache size and hit rate.

## Dependencies at Risk

**Meraki SDK upgrades can silently change server behavior:**
- Risk: The project advertises that the dynamic server auto-updates with SDK upgrades, but there is no automated compatibility suite to catch signature changes, new write verbs, or deprecated methods.
- Impact: A routine dependency bump can change available methods, break docs, or weaken `READ_ONLY_MODE`.
- Migration plan: Pin the tested Meraki SDK version, run a compatibility audit during upgrades, and publish update notes that are generated from the observed method index.

**Transport/runtime packages are managed in two places:**
- Risk: `fastmcp`, `mcp`, `meraki`, and `uvicorn` are declared in both `pyproject.toml` and `requirements.txt` with different versioning strategies.
- Impact: Different contributor environments can surface different transport behavior or tool-registration behavior.
- Migration plan: Consolidate dependency management and validate installs through one documented bootstrap command.

## Missing Critical Features

**No automated test suite or CI verification path:**
- Problem: `CONTRIBUTING.md` expects tests, `requirements.txt` includes `pytest`, but no `tests/` directory, `*.test.py`/`*.spec.py` files, or `.github/workflows/` CI pipeline were detected.
- Blocks: Safe SDK upgrades, safe refactors of `meraki-mcp.py`, and confident changes to caching/read-only behavior in `meraki-mcp-dynamic.py`.

**No authentication/authorization layer for HTTP mode:**
- Problem: The HTTP deployment guidance assumes network reachability is enough protection.
- Blocks: Secure shared-team or internet-adjacent deployment of `meraki-mcp-dynamic.py` and `meraki-mcp.py`.

**No production-grade observability:**
- Problem: Both servers suppress Meraki SDK logging and do not add structured application logging, metrics, traces, or a health endpoint.
- Blocks: Root-cause analysis for rate limiting, cache growth, broken SDK methods, and operational incidents in HTTP/Docker deployments.

## Test Coverage Gaps

**Manual tool compatibility is untested:**
- What's not tested: Registration and runtime invocation of curated manual tools, including broken wrappers like `get_device_status` and `get_device_uplink`.
- Files: `meraki-mcp.py`
- Risk: SDK drift remains latent until a user calls the affected tool in a live Meraki environment.
- Priority: High

**Dynamic safety controls are untested:**
- What's not tested: `READ_ONLY_MODE`, prefix-based write detection, cache invalidation, path validation, large-response truncation, and cache-file retrieval behavior.
- Files: `meraki-mcp-dynamic.py`
- Risk: Safety guarantees can regress without detection, especially when dependencies change.
- Priority: High

**Documentation examples are untested:**
- What's not tested: Command snippets, tool names, and walkthroughs in the setup and dynamic usage docs.
- Files: `README.md`, `README-DYNAMIC.md`, `INSTALL.md`, `QUICKSTART.md`, `OPTIMIZATIONS.md`
- Risk: Users hit dead-end examples and may misconfigure transport or safety settings.
- Priority: Medium

---

*Concerns audit: 2026-03-27*

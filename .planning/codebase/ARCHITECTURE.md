# Architecture

**Analysis Date:** 2026-03-27

## Pattern Overview

**Overall:** Flat dual-entrypoint integration service built around `FastMCP` and the Meraki Python SDK.

**Key Characteristics:**
- Keep server bootstrap, Meraki client setup, tool registration, and transport export in top-level scripts: `meraki-mcp.py` and `meraki-mcp-dynamic.py`.
- Treat `meraki-mcp.py` as the curated/manual variant with hand-written tools and Pydantic request schemas.
- Treat `meraki-mcp-dynamic.py` as the hybrid/full-coverage variant with a generic dispatcher, discovery tools, and cache management.

## Layers

**Bootstrap And Runtime Layer:**
- Purpose: Load environment, select transport, create the `FastMCP` server, initialize the Meraki SDK client, and expose an ASGI app when HTTP mode is enabled.
- Location: `meraki-mcp.py`, `meraki-mcp-dynamic.py`
- Contains: `load_dotenv(...)`, `MCP_TRANSPORT`/`MCP_HOST`/`MCP_PORT` parsing, `FastMCP(...)`, `meraki.DashboardAPI(...)`, `app = mcp.streamable_http_app()`, `mcp.run(...)`
- Depends on: `python-dotenv`, `mcp.server.fastmcp.FastMCP`, `meraki.DashboardAPI`
- Used by: Claude Desktop `stdio` runs, HTTP deployments, Docker entrypoint selection in `entrypoint.sh`

**Curated Tool Layer:**
- Purpose: Expose a stable set of hand-written Meraki operations with explicit parameter models and a small amount of endpoint-specific shaping.
- Location: `meraki-mcp.py`
- Contains: Pydantic models such as `SsidUpdateSchema`, `FirewallRule`, `DeviceUpdateSchema`, and grouped `@mcp.tool()` functions for organizations, networks, devices, wireless, switch, appliance, camera, and action batches
- Depends on: The global `dashboard` SDK client plus local helpers `to_async(...)` and `_build_kwargs(...)`
- Used by: Users who want cleaner tool names, schema validation, and curated operations

**Dynamic Tool Layer:**
- Purpose: Expose the full Meraki SDK surface through a generic API caller plus a smaller convenience set of pre-registered tools.
- Location: `meraki-mcp-dynamic.py`
- Contains: `_call_meraki_method_internal(...)`, `call_meraki_api(...)`, common wrappers such as `getOrganizations(...)`, discovery tools such as `list_all_methods(...)`, and metadata tools such as `get_mcp_config(...)`
- Depends on: `inspect.signature(...)`, the global `dashboard` client, cache helpers, and section metadata in `SDK_SECTIONS`
- Used by: Users who need broad SDK coverage, method discovery, and lower maintenance when the SDK changes

**Caching And Response Management Layer:**
- Purpose: Control response size and avoid repeating large read calls in the dynamic server.
- Location: `meraki-mcp-dynamic.py`
- Contains: `SimpleCache`, response token estimation, pagination limiting, file-backed cache writes under `RESPONSE_CACHE_DIR`, and retrieval tools `get_cached_response(...)`, `list_cached_responses(...)`, `clear_cached_files(...)`
- Depends on: `datetime`, `hashlib`, `threading`, filesystem access to `.meraki_cache/`
- Used by: Dynamic read operations and large-response workflows

**Inspection And Operator Support Layer:**
- Purpose: Help operators understand available tools and deployment choices without changing runtime behavior.
- Location: `inspect_tools.py`, `README.md`, `README-DYNAMIC.md`, `COMPARISON.md`, `INSTALL.md`, `QUICKSTART.md`
- Contains: Offline SDK inspection, side-by-side manual/dynamic comparison, deployment examples, and setup guidance
- Depends on: The Meraki SDK structure and the two top-level server scripts
- Used by: Maintainers choosing between the manual and dynamic variants

## Data Flow

**Manual Tool Request:**

1. An MCP client invokes a named tool registered in `meraki-mcp.py`.
2. The tool optionally validates structured input through a Pydantic model such as `NetworkUpdateSchema` or `SsidUpdateSchema`.
3. The tool calls the relevant `dashboard.<section>.<method>` SDK method directly or through `asyncio.to_thread(...)`.
4. The tool returns a JSON string produced with `json.dumps(..., indent=2)`.

**Dynamic Tool Request:**

1. An MCP client invokes either a convenience tool in `meraki-mcp-dynamic.py` or the generic `call_meraki_api(...)` tool.
2. `call_meraki_api(...)` forwards to `_call_meraki_method_internal(...)`, which validates section and method names against the live SDK object graph.
3. The dispatcher auto-fills `organizationId` from `MERAKI_ORG_ID` when the target SDK method accepts it, enforces pagination limits, and blocks writes when `READ_ONLY_MODE` is enabled.
4. Read calls optionally hit `SimpleCache`; large responses can be truncated and persisted to `.meraki_cache/`, with follow-up pagination exposed through `get_cached_response(...)`.
5. The dispatcher normalizes success and most error paths into JSON strings.

**HTTP And Container Startup:**

1. `entrypoint.sh` selects `meraki-mcp.py` or `meraki-mcp-dynamic.py` from `MCP_SERVER`.
2. The selected script maps `MCP_TRANSPORT=http` to FastMCP's `streamable-http` transport and exposes `app = mcp.streamable_http_app()`.
3. `Dockerfile` and `docker-compose.yml` run the selected script in HTTP mode, bind port `8000`, and mount `.meraki_cache/` as container state.

**State Management:**
- Use environment variables as the primary configuration source in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `entrypoint.sh`.
- Keep the Meraki SDK client as a process-global singleton named `dashboard` in each server script.
- Keep dynamic cache state in memory through `SimpleCache` and on disk under `.meraki_cache/`.
- Keep no shared Python package or shared module between the manual and dynamic variants; the two scripts duplicate their own bootstrap and SDK setup.

## Key Abstractions

**FastMCP Server Instance:**
- Purpose: Register tools/resources and run the MCP transport.
- Examples: `mcp = FastMCP("Meraki Magic MCP", ...)` in `meraki-mcp.py`; `mcp = FastMCP("Meraki Magic MCP - Full API", ...)` in `meraki-mcp-dynamic.py`
- Pattern: One server instance per script, built at import time

**Meraki Dashboard Client:**
- Purpose: Provide access to Meraki API sections such as `organizations`, `networks`, `devices`, `wireless`, and `appliance`.
- Examples: `dashboard = meraki.DashboardAPI(...)` in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `inspect_tools.py`
- Pattern: Global integration client injected implicitly through module scope

**Schema-Validated Request Models:**
- Purpose: Constrain high-value manual write operations and encode nested request shapes.
- Examples: `SsidUpdateSchema`, `FirewallRule`, `DeviceUpdateSchema`, `ContentFilteringSchema` in `meraki-mcp.py`
- Pattern: Pydantic `BaseModel` classes consumed directly by `@mcp.tool()` functions

**Generic SDK Dispatcher:**
- Purpose: Turn `(section, method, parameters)` into an actual Meraki SDK call with policy checks and consistent JSON output.
- Examples: `_call_meraki_method_internal(...)`, `call_meraki_method(...)`, `call_meraki_api(...)` in `meraki-mcp-dynamic.py`
- Pattern: Reflective gateway over the SDK object graph

**Method Discovery Index:**
- Purpose: Build a static-at-startup map of callable SDK methods for search and introspection.
- Examples: `_build_method_index()` and `_METHOD_INDEX` in `meraki-mcp-dynamic.py`
- Pattern: Startup-generated metadata cache used by discovery tools, not by manual endpoints

## Entry Points

**Curated MCP Server:**
- Location: `meraki-mcp.py`
- Triggers: `python meraki-mcp.py`, FastMCP CLI execution, or container startup with `MCP_SERVER=manual`
- Responsibilities: Register curated tools, perform schema validation for selected operations, and provide a small greeting resource

**Dynamic MCP Server:**
- Location: `meraki-mcp-dynamic.py`
- Triggers: `python meraki-mcp-dynamic.py`, FastMCP CLI execution, or default container startup with `MCP_SERVER=dynamic`
- Responsibilities: Register the generic caller, discovery/cache tools, common convenience wrappers, and manage large response handling

**Container Entrypoint:**
- Location: `entrypoint.sh`
- Triggers: `Dockerfile` `ENTRYPOINT ["./entrypoint.sh"]`
- Responsibilities: Select the server variant, echo effective runtime settings, and exec Python against the chosen script

**Offline Inspection Utility:**
- Location: `inspect_tools.py`
- Triggers: Direct script execution by a maintainer
- Responsibilities: Inspect the Meraki SDK without issuing API calls and report how many dynamic tools would be available

## Error Handling

**Strategy:** Return JSON-encoded API data on success and keep startup failure handling explicit around missing credentials.

**Patterns:**
- Fail fast on missing `MERAKI_API_KEY` in both `meraki-mcp.py` and `meraki-mcp-dynamic.py` by printing to `stderr` and exiting the process.
- In `meraki-mcp-dynamic.py`, catch `meraki.exceptions.APIError`, `TypeError`, and generic `Exception` inside `_call_meraki_method_internal(...)` and convert them into structured JSON responses.
- In `meraki-mcp.py`, let most SDK exceptions propagate naturally; endpoint-specific functions mostly focus on data shaping rather than exception normalization.
- Validate cached file access in `meraki-mcp-dynamic.py` through `_validate_cache_filepath(...)` before reading from disk.

## Cross-Cutting Concerns

**Logging:** Keep Meraki SDK logging suppressed via `suppress_logging=True`; emit only startup and mode messages to `stderr` in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `entrypoint.sh`.

**Validation:** Use Pydantic models in `meraki-mcp.py` for curated writes; use `inspect.signature(...)` and runtime parameter checking in `meraki-mcp-dynamic.py` for generic access.

**Authentication:** Read `MERAKI_API_KEY` and optional `MERAKI_ORG_ID` from environment or `.env`; pass the API key into the `dashboard` client in both server scripts.

**Runtime Modes:** Support `stdio` by default and HTTP through `MCP_TRANSPORT=http`, which is normalized to `streamable-http` in both `meraki-mcp.py` and `meraki-mcp-dynamic.py`. Keep container deployments HTTP-first through `Dockerfile` and `docker-compose.yml`.

**Manual vs Dynamic Relationship:** Treat `meraki-mcp.py` and `meraki-mcp-dynamic.py` as sibling implementations over the same Meraki SDK and environment contract. They do not share Python modules. `meraki-mcp.py` optimizes for curated, schema-aware operations; `meraki-mcp-dynamic.py` optimizes for breadth, discovery, caching, and generic dispatch. Run either one alone or both side by side from client configuration documented in `README.md` and `README-DYNAMIC.md`.

---

*Architecture analysis: 2026-03-27*

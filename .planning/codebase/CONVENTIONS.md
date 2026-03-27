# Coding Conventions

**Analysis Date:** 2026-03-27

## Naming Patterns

**Files:**
- Executable server entrypoints use hyphenated script names in the repository root: `meraki-mcp.py`, `meraki-mcp-dynamic.py`.
- Helper scripts use snake_case with `.py` suffix: `inspect_tools.py`.
- Documentation files use uppercase or uppercase-hyphen Markdown names: `README.md`, `README-DYNAMIC.md`, `INSTALL.md`, `OPTIMIZATIONS.md`.

**Functions:**
- Manual MCP tool wrappers in `meraki-mcp.py` use snake_case names such as `get_networks`, `update_wireless_ssid`, and `create_action_batch`.
- Dynamic MCP convenience tools in `meraki-mcp-dynamic.py` mirror Meraki SDK method names in camelCase, such as `getOrganizations`, `getNetworkClients`, and `updateDeviceSwitchPort`.
- Internal helpers are prefixed with `_` when not exposed as tools, such as `_build_kwargs` in `meraki-mcp.py` and `_call_meraki_method_internal` in `meraki-mcp-dynamic.py`.

**Variables:**
- Module-level configuration constants are uppercase and loaded from the environment in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `inspect_tools.py`: `MERAKI_API_KEY`, `MERAKI_ORG_ID`, `MCP_TRANSPORT`, `CACHE_TTL_SECONDS`.
- Local Python variables use snake_case, even when they are later translated to Meraki SDK camelCase parameters, for example `org_id`, `network_id`, `device_policy`, and `global_bandwidth_limits` in `meraki-mcp.py`.
- Temporary request dictionaries are commonly named `params`, `kwargs`, `update_dict`, `rules_dict`, or `response_data` in `meraki-mcp.py` and `meraki-mcp-dynamic.py`.

**Types:**
- Pydantic models in `meraki-mcp.py` use PascalCase and `Schema` suffixes where the model represents request payloads: `SsidUpdateSchema`, `DeviceUpdateSchema`, `ActionBatchSchema`.
- Support models also use PascalCase: `Dot11wSettings`, `FirewallRule`, `SimpleCache`.
- Type hints rely on built-in generics and `typing` names in both servers, for example `list[str]`, `Dict[str, Any]`, and `Optional[bool]`.

## Code Style

**Formatting:**
- No formatter configuration is present. `pyproject.toml` only defines project metadata and runtime dependencies; there is no Ruff, Black, isort, or autopep8 config.
- Code follows 4-space indentation and keeps one top-level declaration per block in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `inspect_tools.py`.
- Tool responses are consistently serialized with `json.dumps(..., indent=2)` in `meraki-mcp.py` and `meraki-mcp-dynamic.py`.
- Section banners made of `###################` are used to break up large single-file modules in `meraki-mcp.py` and `meraki-mcp-dynamic.py`.

**Linting:**
- No lint configuration is detected in the repository root. Files such as `.ruff.toml`, `ruff.toml`, `.flake8`, `setup.cfg`, and `tox.ini` are not present.
- Style consistency is maintained manually. When editing `meraki-mcp.py` or `meraki-mcp-dynamic.py`, match existing spacing, banner comments, and `json.dumps(..., indent=2)` output style.

## Import Organization

**Order:**
1. Standard library imports appear first in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `inspect_tools.py`, including `os`, `sys`, `json`, `asyncio`, `functools`, `inspect`, `hashlib`, and `threading`.
2. Third-party imports follow, including `meraki`, `pydantic`, `mcp.server.fastmcp.FastMCP`, and `dotenv.load_dotenv`.
3. There are no local package imports because the repository is a flat script layout without a `src/` package.

**Path Aliases:**
- Not used. All imports are direct module imports from installed dependencies or Python standard library modules.

## Error Handling

**Patterns:**
- Configuration failures are treated as fatal at import time. Both `meraki-mcp.py` and `meraki-mcp-dynamic.py` check `MERAKI_API_KEY`, print a message to `stderr`, and call `sys.exit(1)` if it is missing.
- The dynamic server centralizes runtime error handling in `_call_meraki_method_internal` inside `meraki-mcp-dynamic.py`. It catches `meraki.exceptions.APIError`, `TypeError`, and generic `Exception`, then returns a JSON string with `error`, `message`, and related metadata instead of raising.
- The manual server in `meraki-mcp.py` usually lets SDK exceptions bubble out. Most tool functions are thin wrappers with no `try/except`, so failures depend on FastMCP and the Meraki SDK to surface errors.
- Invalid or unsafe file-cache access is normalized to JSON error payloads in `get_cached_response` and `list_cached_responses` in `meraki-mcp-dynamic.py`.

## Logging

**Framework:** `print` to `stderr`

**Patterns:**
- Meraki SDK logging is intentionally suppressed with `suppress_logging=True` in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `inspect_tools.py`.
- Startup and configuration messages are emitted with `print(..., file=sys.stderr)` in `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `entrypoint.sh`.
- The Python `logging` module is not used anywhere in the repository.

## Comments

**When to Comment:**
- Use short banner comments to separate major domains or systems, following the existing style in `meraki-mcp.py` and `meraki-mcp-dynamic.py`.
- Add brief inline comments only when they explain operational intent, such as cache invalidation, read-only behavior, or transport selection.
- Keep user-facing explanation in docstrings rather than long inline comments. Most MCP tools in `meraki-mcp.py` and `meraki-mcp-dynamic.py` already have concise docstrings.

**JSDoc/TSDoc:**
- Not applicable. Python docstrings are used instead.
- Pydantic fields in `meraki-mcp.py` carry `description=` metadata, which acts as the schema-level documentation for MCP tool inputs.

## Function Design

**Size:** Large files, small wrappers
- `meraki-mcp.py` and `meraki-mcp-dynamic.py` are large top-level scripts, but individual MCP tool functions are usually thin wrappers around one SDK call plus `json.dumps`.
- Shared behavior is extracted only when it eliminates obvious repetition, for example `to_async`, `_build_kwargs`, `create_cache_key`, and `_validate_cache_filepath`.

**Parameters:**
- Optional organization scoping usually follows the same pattern in `meraki-mcp.py`: accept `org_id: str = None`, then resolve `organization_id = org_id or MERAKI_ORG_ID`.
- Manual wrappers prefer Pythonic snake_case parameter names and convert to Meraki camelCase when building kwargs, for example `device_policy` to `devicePolicy` in `update_client_policy` and `global_bandwidth_limits` to `globalBandwidthLimits` in `update_appliance_traffic_shaping` in `meraki-mcp.py`.
- Dynamic wrappers preserve Meraki SDK naming more directly and often accept `**params` or a free-form `parameters: Dict[str, Any]`, as in `call_meraki_api` in `meraki-mcp-dynamic.py`.

**Return Values:**
- The dominant return type is `str` containing pretty-printed JSON from `json.dumps(..., indent=2)` in both server scripts.
- A few mutating manual tools return plain success strings instead of JSON, such as `delete_network`, `claim_devices`, and `remove_device` in `meraki-mcp.py`.
- Dynamic helper tools return JSON strings for both success and failure so the response shape is predictable in `meraki-mcp-dynamic.py`.

## Module Design

**Exports:** Decorator-driven module entrypoints
- MCP tools are defined as top-level functions decorated with `@mcp.tool()` in `meraki-mcp.py` and `meraki-mcp-dynamic.py`.
- The only non-tool public export is the module-level ASGI `app` in both server files.
- `meraki-mcp.py` also exposes a simple `@mcp.resource("greeting: //{name}")` resource near the bottom of the file.

**Barrel Files:** Not used
- The repository has no package directory, no `__init__.py`, and no barrel-style re-export modules.
- New functionality is added directly to the root scripts rather than through a package hierarchy.

## Environment & Config

**Environment Loading:**
- Both server entrypoints call `load_dotenv(Path(__file__).resolve().parent / ".env")` at import time in `meraki-mcp.py` and `meraki-mcp-dynamic.py`.
- `inspect_tools.py` uses plain `load_dotenv()` and falls back to `MERAKI_API_KEY="dummy_key"` so offline SDK inspection works without real credentials.
- `.env-example` is the source of truth for supported variables such as `MERAKI_API_KEY`, `MERAKI_ORG_ID`, `ENABLE_CACHING`, `CACHE_TTL_SECONDS`, `READ_ONLY_MODE`, `ENABLE_FILE_CACHING`, `MAX_RESPONSE_TOKENS`, `MAX_PER_PAGE`, `RESPONSE_CACHE_DIR`, `MCP_TRANSPORT`, `MCP_HOST`, and `MCP_PORT`.

**Secrets Handling:**
- `.gitignore` excludes `.env`, `.venv/`, and `.meraki_cache/`, so local credentials and cached API output stay out of version control.
- `AGENTS.md` explicitly says real credentials must not be committed and `.env` is the secret-bearing file for local development.

**Configuration Pattern:**
- Keep new runtime switches as uppercase environment variables with string defaults at module import time, matching `meraki-mcp.py` and `meraki-mcp-dynamic.py`.
- Docker overrides runtime defaults through `Dockerfile`, `docker-compose.yml`, and `entrypoint.sh`, not through a separate settings module.

## Developer Workflow

**Setup:**
- The documented local workflow is: create `.venv`, activate it, upgrade `pip`, install `requirements.txt`, and copy `.env-example` to `.env`, as described in `AGENTS.md` and `INSTALL.md`.
- Python 3.13+ is required in `AGENTS.md`, `INSTALL.md`, `.python-version`, and `pyproject.toml`.

**Run Modes:**
- The recommended local command is `python meraki-mcp-dynamic.py` from `AGENTS.md` and `README.md`.
- The curated/manual alternative is `python meraki-mcp.py` from `AGENTS.md` and `README.md`.
- HTTP and container workflows are documented through `MCP_TRANSPORT=http`, `docker compose up -d`, `Dockerfile`, `docker-compose.yml`, and `entrypoint.sh`.

**Safe Verification Habit:**
- `inspect_tools.py` is the repository’s safe preflight script. It inspects the SDK and prints coverage details without making API calls.
- `README-DYNAMIC.md`, `QUICKSTART.md`, and `INSTALL.md` all direct contributors to start with discovery or read-only operations before trying writes.

**Backward Compatibility:**
- `AGENTS.md` states that existing sample behavior should not be changed unless the result is clearly an improvement or bug fix, and changes should be documented.

---

*Convention analysis: 2026-03-27*

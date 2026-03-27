# Testing Patterns

**Analysis Date:** 2026-03-27

## Test Framework

**Runner:**
- `pytest==7.4.4` is pinned in `requirements.txt`, but no test runner configuration file such as `pytest.ini`, `conftest.py`, or `pyproject.toml` pytest settings is present.
- Config: Not detected.

**Assertion Library:**
- Pytest assertions are the implied default because `pytest` is listed in `requirements.txt`.
- No repository files currently use pytest assertions because no automated test modules are present.

**Run Commands:**
```bash
python3 -m pytest                         # Intended test runner after installing `requirements.txt`; no test files are present
# Watch mode: Not configured
# Coverage: Not configured
python3 inspect_tools.py                  # Safe offline SDK inspection; no API calls
python3 -m compileall meraki-mcp.py meraki-mcp-dynamic.py inspect_tools.py  # Syntax-only smoke check
```

## Test File Organization

**Location:**
- Not detected. There is no `tests/` directory and no co-located test modules under the repository root.

**Naming:**
- Not detected. Patterns such as `test_*.py`, `*_test.py`, `*.spec.py`, and `*.test.py` are absent from the repository.

**Structure:**
```text
Not detected
```

## Test Structure

**Suite Organization:**
```python
# No automated test suites are present in the repository.
# Current verification is runbook-based and centered on:
# - `inspect_tools.py` for offline SDK inspection
# - Claude Desktop prompts documented in `INSTALL.md`
# - HTTP initialize smoke checks documented in `INSTALL.md`
```

**Patterns:**
- Setup is manual and environment-driven: create `.venv`, install `requirements.txt`, copy `.env-example` to `.env`, then run one of the MCP entrypoints, as documented in `AGENTS.md` and `INSTALL.md`.
- Teardown is not documented. Manual verification relies on stopping the local Python process or `docker compose down`.
- Assertions are human-verified. Docs in `INSTALL.md` and `README-DYNAMIC.md` tell contributors to confirm MCP server presence, inspect JSON output, and check specific response fields such as `serverInfo.name` or `api_key_configured`.

## Mocking

**Framework:** Not detected

**Patterns:**
```python
# The repository does not define mocks, stubs, monkeypatch helpers, or fixture layers.
# The closest offline verification pattern is in `inspect_tools.py`:
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY", "dummy_key")
dashboard = meraki.DashboardAPI(api_key=MERAKI_API_KEY, suppress_logging=True)
```

**What to Mock:**
- Not established in repository code.

**What NOT to Mock:**
- Not established in repository code.

## Fixtures and Factories

**Test Data:**
```python
# Not detected. No shared fixtures, factories, or sample response payload modules are present.
```

**Location:**
- Not detected.

## Coverage

**Requirements:** None enforced
- `CONTRIBUTING.md` says pull requests are expected to include tests for affected behavior, but the repository has no implemented automated test suite, no coverage target, and no CI enforcement.

**View Coverage:**
```bash
# Not configured
```

## Test Types

**Unit Tests:**
- Not detected in the repository.
- Helper logic such as `_build_kwargs` in `meraki-mcp.py`, `SimpleCache` in `meraki-mcp-dynamic.py`, and `_validate_cache_filepath` in `meraki-mcp-dynamic.py` currently has no direct automated coverage.

**Integration Tests:**
- Manual integration testing is the primary current pattern.
- `AGENTS.md` directs contributors to validate behavior against the Cisco DevNet sandbox.
- `INSTALL.md` provides a Docker HTTP initialize request using `curl` and expected JSON response checks.
- `INSTALL.md`, `README.md`, and `README-DYNAMIC.md` describe Claude Desktop verification prompts such as listing organizations, admins, networks, and tool configuration.

**E2E Tests:**
- Not automated.
- Current end-to-end validation is manual through Claude Desktop MCP loading, direct `python meraki-mcp-dynamic.py` or `python meraki-mcp.py` runs, and optional Docker deployment via `docker-compose.yml`.

## Common Patterns

**Async Testing:**
```python
# Not detected. Async MCP tools in `meraki-mcp.py` and `meraki-mcp-dynamic.py`
# are not covered by automated tests.
```

**Error Testing:**
```json
{
  "error": "Meraki API Error",
  "message": "Invalid API key",
  "status": 401
}
```
- This JSON error shape is documented in `README-DYNAMIC.md` and `QUICKSTART.md`, but there are no automated assertions that verify it.

## Verification Workflow

**Offline / No API Calls:**
- Run `python3 inspect_tools.py` from `inspect_tools.py` and `QUICKSTART.md` to inspect SDK sections, method counts, and parameter signatures without hitting the Meraki API.
- Use syntax-only compilation against `meraki-mcp.py`, `meraki-mcp-dynamic.py`, and `inspect_tools.py` when you need a fast smoke check with no credentials.

**Live Local Verification:**
- Start the recommended server with `python meraki-mcp-dynamic.py` as shown in `AGENTS.md` and `README.md`.
- In Claude Desktop, follow `INSTALL.md` prompts: confirm the server is loaded, query organizations, query admins, and inspect `get_mcp_config`.
- Start with read-only operations first, following the guidance in `README-DYNAMIC.md` and `QUICKSTART.md`.

**HTTP / Docker Verification:**
- Use the HTTP initialize `curl` request from `INSTALL.md` after `docker compose up -d` or HTTP-mode local startup.
- Validate that the response contains `serverInfo.name = "Meraki Magic MCP - Full API"` as documented in `INSTALL.md`.

**Safety Checks:**
- `README-DYNAMIC.md`, `QUICKSTART.md`, and `OPTIMIZATIONS.md` all encourage read-only verification before mutating calls.
- `READ_ONLY_MODE=true` in `.env-example` and `OPTIMIZATIONS.md` is the current built-in guardrail for exploratory testing against real environments.

## Testing Gaps

**Automated Coverage Gap:**
- No automated tests exist for `meraki-mcp.py`, `meraki-mcp-dynamic.py`, or `inspect_tools.py`.

**Config Validation Gap:**
- Startup requirements around `.env` loading, `MERAKI_API_KEY`, transport selection, and cache directory handling are exercised only by manual runs of `meraki-mcp.py`, `meraki-mcp-dynamic.py`, `Dockerfile`, and `entrypoint.sh`.

**Behavioral Regression Gap:**
- Manual tool wrappers in `meraki-mcp.py` have no regression suite to catch schema drift, renamed SDK methods, or inconsistent return shapes.

**Safety Regression Gap:**
- Dynamic guardrails in `meraki-mcp-dynamic.py`, including read-only blocking, pagination limiting, cache invalidation, and cache-path validation, are not covered by automated tests.

---

*Testing analysis: 2026-03-27*

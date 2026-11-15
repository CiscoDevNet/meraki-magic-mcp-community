# Keeping Your Meraki MCP Up-to-Date

## How updates work

The dynamic MCP discovers API methods by inspecting the installed Meraki Python SDK. It does not use the Postman collection or a hand-maintained endpoint list.

- When Meraki releases new API endpoints, they publish a new version of the Meraki Python SDK
- When the SDK is upgraded, `call_meraki_api` and the discovery tools see the new methods with no code changes
- The manual MCP (`meraki-mcp.py`) wraps specific SDK methods by hand, so its tools only change when the code does

## Updating to the latest release of this project (recommended)

Each release of this project pins an SDK version in `requirements.txt` that the test suite has been run against:

```bash
cd /path/to/meraki-magic-mcp-community
git pull
source .venv/bin/activate
pip install -r requirements.txt
```

Then restart Claude Desktop (or the server process, or `docker compose up -d --build` for Docker).

## Trying a newer SDK than the pinned one

To use an SDK release before this project has adopted it, upgrade it in your virtual environment:

```bash
cd /path/to/meraki-magic-mcp-community
source .venv/bin/activate
pip install --upgrade "meraki<5"
python -m unittest discover -s tests
```

Run the tests before relying on the upgrade. They check the installed SDK and fail when:

- a new SDK method starts with a verb that has not been reviewed for read-only mode
- a delete-like method would run without `confirm_destructive_action`
- a method used by the manual server no longer exists

Read-only mode is safe either way: any method that is not a `get*`/`list*` read is blocked while `READ_ONLY_MODE=true`.

## Bumping the pinned SDK (contributors)

`pyproject.toml` holds the allowed version range and `requirements.txt` is the lockfile generated from it. To move the pin:

```bash
uv pip compile pyproject.toml -o requirements.txt --universal --upgrade-package meraki
pip install -r requirements.txt
python -m unittest discover -s tests
```

If the tests report unreviewed verbs, add them to `WRITE_PREFIXES` in `meraki_mcp_config.py` (and to `DESTRUCTIVE_PREFIXES` if they delete or wipe data). If they report a missing manual-server method, update that tool in `meraki-mcp.py`. Commit `pyproject.toml`, `requirements.txt` and any code changes together.

## Update workflow

```
┌─────────────────────────────────────────────┐
│  Meraki releases new API features           │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  Meraki updates the Python SDK on PyPI      │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  The SDK is upgraded and the tests pass     │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  Restart the MCP server                     │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  Dynamic MCP has the new methods            │
└─────────────────────────────────────────────┘
```

## Checking for new methods

After updating, you can see what is available:

```bash
# Count methods per section in the installed SDK
python3 inspect_tools.py
```

Or in Claude Desktop:

```
Use list_all_methods to show the method count per section
Use search_methods with keyword="new_feature_name"
```

`get_mcp_config` reports the total in `total_available_methods`.

## Recommended schedule

- **Monthly**: most users
- **Before major deployments**: always good practice

## Troubleshooting

### "No module named meraki"
```bash
cd /path/to/meraki-magic-mcp-community
source .venv/bin/activate
pip install -r requirements.txt
```

### "pip: command not found"
```bash
python3 -m pip install -r requirements.txt
```

### The update doesn't seem to work
1. Make sure the virtual environment is activated
2. Check the installed version with `pip show meraki`
3. Restart Claude Desktop completely; the server only reads the SDK at startup

## Summary

The dynamic MCP reads its method list from the Meraki Python SDK:

1. Update the project (`git pull`, then `pip install -r requirements.txt`)
2. Restart the MCP server
3. New SDK methods are available through `call_meraki_api`

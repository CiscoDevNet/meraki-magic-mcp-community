# Meraki Magic MCP - Dynamic Full API

This **hybrid dynamic MCP** provides access to **ALL** Meraki SDK methods (more than 1,000 as of SDK 4.7) through a combination of pre-registered common tools and a generic API caller.

## What This Gives You

Full access to all Meraki API methods across all SDK sections:

- **organizations**: 251 methods
- **appliance**: 181 methods
- **wireless**: 157 methods
- **networks**: 115 methods
- **switch**: 102 methods
- **sm**: 49 methods
- **camera**: 46 methods
- **devices**: 41 methods
- **cellularGateway**: 24 methods
- **sensor**: 19 methods
- **campusGateway**: 18 methods
- **wirelessController**: 15 methods
- **licensing**: 8 methods
- **insight**: 7 methods
- **administered**: 4 methods
- **spaces**: 2 methods

**Total: 1,039 methods with Meraki SDK 4.7.** The counts follow the installed SDK; `list_all_methods` and `get_mcp_config` report the current numbers.

## Architecture: Hybrid Approach

To avoid MCP conversation length limits, this uses a hybrid approach:

### 1. Pre-Registered Tools (12 most common)
Fast, convenient access to frequently-used operations:
- `getOrganizations`
- `getOrganizationAdmins`
- `getOrganizationNetworks`
- `getOrganizationDevices`
- `getNetwork`
- `getNetworkClients`
- `getNetworkEvents`
- `getNetworkDevices`
- `getDevice`
- `getNetworkWirelessSsids`
- `getDeviceSwitchPorts`
- `updateDeviceSwitchPort`

### 2. Generic API Caller (every SDK method)
Access any Meraki API method via `call_meraki_api`:

```python
call_meraki_api(
    section="appliance",
    method="getNetworkApplianceFirewallL3FirewallRules",
    parameters={"networkId": "L_123456"}
)
```

**Claude automatically routes to the right tool:**
- Common operations → Pre-registered tool (faster)
- Everything else → `call_meraki_api` (full coverage)

## Files

- `meraki-mcp-dynamic.py` - Hybrid MCP server (12 pre-registered + generic caller)
- `meraki-mcp.py` - Original manual MCP server (83 hand-written tools)

## Safety and Region Configuration

The server starts in read-only mode by default. Set `READ_ONLY_MODE=false` only when you intend to run write operations; every method that is not a `get*`/`list*` read is treated as a write. Destructive calls (`delete*`, `remove*`, `release*`, `wipe*`, `unenroll*`, `uninstall*`, `revoke*`, `detach*`, and bulk `*Delete` methods) also require `confirm_destructive_action=true` in `parameters`.

Set these variables in the MCP client `env` block or process environment to select a region and caller identifier:

```bash
export MERAKI_BASE_URL="https://api.meraki.com/api/v1"
export MERAKI_PYTHON_SDK_CALLER="MagicMCP CiscoDevNet"
export READ_ONLY_MODE=true
```

`MERAKI_PYTHON_SDK_CALLER` defaults to `MagicMCP CiscoDevNet` and must follow the [Meraki user agent format](https://developer.cisco.com/meraki/api-v1/user-agents-overview/).

## Helper Tools Included

Discovery tools to find and use any API method:

1. **list_all_methods** - Method counts per section, or the methods of one section when `section` is given
2. **search_methods** - Search for methods by keyword (multiple terms must all match; optional `section` and `limit`, default 50 results)
3. **get_method_info** - Get parameter details for any method
4. **get_mcp_config** - View MCP configuration
5. **cache_stats** - View caching statistics
6. **cache_clear** - Clear the in-memory response cache
7. **get_cached_response** - Page through a large response that was saved to a cache file
8. **list_cached_responses** - List cached response files
9. **clear_cached_files** - Delete cached response files older than a given age

## Deployment

### Option 1: Claude Desktop (stdio - local)

Update your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "Meraki_Magic_MCP": {
      "command": "/path/to/meraki-magic-mcp-community/.venv/bin/fastmcp",
      "args": [
        "run",
        "-t", "stdio",
        "/path/to/meraki-magic-mcp-community/meraki-mcp-dynamic.py"
      ],
      "env": {
        "MERAKI_API_KEY": "your_api_key_here",
        "MERAKI_ORG_ID": "your_org_id_here",
        "MERAKI_BASE_URL": "https://api.meraki.com/api/v1",
        "MERAKI_PYTHON_SDK_CALLER": "MagicMCP CiscoDevNet",
        "READ_ONLY_MODE": "true"
      }
    }
  }
}
```

Replace `/path/to/` with your actual installation path.

### Option 2: HTTP Server (remote access)

```bash
export MERAKI_API_KEY="your_api_key_here"
export MCP_TRANSPORT=http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
export MCP_AUTH_TOKEN="your_token_here"  # required header: Authorization: Bearer <token>

python meraki-mcp-dynamic.py
# Server at http://<host>:8000/mcp
```

Always set `MCP_AUTH_TOKEN` when binding to `0.0.0.0`; the server warns at startup if it is missing. Use a TLS reverse proxy across a network.

### Option 3: Docker

```bash
export MERAKI_API_KEY="your_api_key_here"
export MERAKI_ORG_ID="your_org_id_here"
docker compose up -d
# Server at http://localhost:8000/mcp (host loopback only; set MCP_PUBLISH_HOST=0.0.0.0 and MCP_AUTH_TOKEN for remote access)
```

Connect Claude Desktop to HTTP/Docker servers using mcp-remote:
```json
{
  "mcpServers": {
    "Meraki_Magic_MCP": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote", "http://localhost:8000/mcp",
        "--header", "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "Bearer your_token_here"
      }
    }
  }
}
```

Drop the `--header` arguments and the `env` block if the server has no `MCP_AUTH_TOKEN`.

See [INSTALL.md](INSTALL.md#http-transport-mode) for full details.

## Example Usage in Claude

### Discover available methods
```
Use list_all_methods with section="wireless" to show me the wireless methods
```

### Search for specific functionality
```
Use search_methods to find all methods related to "firewall"
```

### Get parameter details
```
Use get_method_info to show me the parameters for section="organizations", method="getOrganization"
```

### Call actual API methods
```
Use getOrganizations to list all organizations
```

```
Use getNetworkClients with networkId="L_12345" and timespan=86400
```

```
Use call_meraki_api with section="appliance", method="getNetworkApplianceVpnSiteToSiteVpn" and parameters={"networkId": "L_12345"}
```

## Advantages of Dynamic Approach

✅ **Complete Coverage** - Every SDK method is available immediately
✅ **Auto-Updated** - When Meraki SDK updates, you get new endpoints automatically
✅ **No Manual Coding** - No need to hand-code each endpoint
✅ **Small Tool List** - 22 MCP tools instead of one per endpoint, which keeps the conversation context small
✅ **Consistent Interface** - All methods are called the same way
✅ **Error Handling** - Built-in error handling for all methods
✅ **Async Support** - All methods wrapped in async handlers

## Disadvantages vs. Manual Approach

⚠️ **Less Type Safety** - No Pydantic schemas for validation
⚠️ **Generic Descriptions** - Method descriptions come from the SDK docstrings
⚠️ **No Custom Logic** - Can't add custom business logic per endpoint
⚠️ **Extra Discovery Step** - Less common methods must be found with `search_methods` before they can be called

## When to Use Which Version

**Use Dynamic (`meraki-mcp-dynamic.py`) when:**
- You need access to many different API endpoints
- You want complete API coverage
- You're exploring/prototyping
- You want automatic updates when SDK changes

**Use Manual (`meraki-mcp.py`) when:**
- You only need specific, well-defined endpoints
- You want strong type validation (Pydantic schemas)
- You need custom business logic
- You want clean, curated tool descriptions

## Hybrid Approach

You can use BOTH! Configure both servers in your Claude Desktop config:

```json
{
  "mcpServers": {
    "Meraki_Curated": {
      "command": "/path/to/meraki-magic-mcp-community/.venv/bin/fastmcp",
      "args": ["run", "-t", "stdio", "/path/to/meraki-magic-mcp-community/meraki-mcp.py"]
    },
    "Meraki_Full_API": {
      "command": "/path/to/meraki-magic-mcp-community/.venv/bin/fastmcp",
      "args": ["run", "-t", "stdio", "/path/to/meraki-magic-mcp-community/meraki-mcp-dynamic.py"]
    }
  }
}
```

This gives you:
- Curated, well-documented tools for common operations
- Full API access for everything else

## Testing

Before testing with your production API key, I recommend:

1. **Test tool listing** (doesn't call Meraki API):
   - Use `list_all_methods` helper
   - Use `search_methods` helper
   - Use `get_method_info` helper

2. **Test with read-only operations first**:
   - `getOrganizations`
   - `getOrganizationNetworks`
   - `getNetwork`

3. **Avoid write operations until confident**:
   - Anything that is not a `get*` method is blocked while `READ_ONLY_MODE=true`
   - Set `READ_ONLY_MODE=false` and pass `confirm_destructive_action=true` for destructive calls only after verifying the target

## Error Handling

All tools include built-in error handling that returns JSON with error details:

```json
{
  "error": "Meraki API Error",
  "message": "Invalid API key",
  "status": 401
}
```

## Auto-fills Organization ID

If a method requires `organizationId` and you haven't provided it, the tool will automatically use your `MERAKI_ORG_ID` from the process environment.

## Next Steps

1. Restart Claude Desktop (if config changed)
2. Test the helper tools first (they don't call Meraki API)
3. Test read-only operations with your production environment
4. Explore the full API at your own pace!

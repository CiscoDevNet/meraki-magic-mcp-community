# Meraki Magic MCP - Dynamic Full API

This **hybrid dynamic MCP** provides access to **ALL** Meraki SDK methods (~804+ endpoints) through a combination of pre-registered common tools and a generic API caller.

## What This Gives You

Full access to all Meraki API methods across all SDK sections:

- **organizations**: ~172 methods
- **networks**: ~114 methods
- **switch**: ~101 methods
- **appliance**: ~130 methods
- **wireless**: ~105 methods
- **camera**: ~45 methods
- **devices**: ~27 methods
- **sm**: ~49 methods
- **cellularGateway**: ~24 methods
- **sensor**: ~18 methods
- **insight**: ~7 methods
- **licensing**: ~8 methods
- **administered**: ~4 methods

**Total: ~804 methods accessible!**

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

### 2. Generic API Caller (all 804+ methods)
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
- `meraki-mcp.py` - Original manual MCP server (40 hand-coded endpoints)

## Safety and Region Configuration

The server starts in read-only mode by default. Set `READ_ONLY_MODE=false` only when you intend to run create/update/delete/remove operations. Destructive `delete*` and `remove*` calls also require `confirm_destructive_action=true` in `parameters`.

Set `MERAKI_BASE_URL` to use a non-default Meraki Dashboard API region, for example:

```env
MERAKI_BASE_URL="https://api.meraki.com/api/v1"
READ_ONLY_MODE=true
```

## Helper Tools Included

Discovery tools to find and use any API method:

1. **list_all_methods** - Browse all 804+ methods (optionally by section)
2. **search_methods** - Search for methods by keyword
3. **get_method_info** - Get parameter details for any method
4. **get_mcp_config** - View MCP configuration
5. **cache_stats** - View caching statistics
6. **cache_clear** - Clear response cache

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
      ]
    }
  }
}
```

Replace `/path/to/` with your actual installation path.

### Option 2: HTTP Server (remote access)

```bash
# In .env:
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=8000

python meraki-mcp-dynamic.py
# Server at http://<host>:8000/mcp
```

### Option 3: Docker

```bash
docker compose up -d
# Server at http://localhost:8000/mcp
```

Connect Claude Desktop to HTTP/Docker servers using mcp-remote:
```json
{
  "mcpServers": {
    "Meraki_Magic_MCP": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8000/mcp"]
    }
  }
}
```

See [INSTALL.md](INSTALL.md#http-transport-mode) for full details.

## Example Usage in Claude

### Discover available tools
```
Use the list_available_tools to show me all wireless tools
```

### Search for specific functionality
```
Use search_tools to find all tools related to "firewall"
```

### Get parameter details
```
Use get_tool_info to show me the parameters for organizations_getOrganization
```

### Call actual API methods
```
Use organizations_getOrganizations to list all organizations
```

```
Use networks_getNetworkClients with networkId="L_12345" and timespan=86400
```

## Advantages of Dynamic Approach

✅ **Complete Coverage** - All 800+ endpoints available immediately
✅ **Auto-Updated** - When Meraki SDK updates, you get new endpoints automatically
✅ **No Manual Coding** - No need to hand-code each endpoint
✅ **Consistent Interface** - All tools follow the same pattern
✅ **Error Handling** - Built-in error handling for all methods
✅ **Async Support** - All methods wrapped in async handlers

## Disadvantages vs. Manual Approach

⚠️ **Less Type Safety** - No Pydantic schemas for validation
⚠️ **Generic Descriptions** - Tool descriptions are auto-generated
⚠️ **No Custom Logic** - Can't add custom business logic per endpoint
⚠️ **Larger Tool List** - 800+ tools may be overwhelming in Claude UI

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
   - Use `list_available_tools` helper
   - Use `search_tools` helper
   - Use `get_tool_info` helper

2. **Test with read-only operations first**:
   - `organizations_getOrganizations`
   - `organizations_getOrganization`
   - `networks_getNetwork`

3. **Avoid destructive operations until confident**:
   - Anything with `delete` in the name
   - Anything with `update` or `create`
   - Set `READ_ONLY_MODE=false` and pass `confirm_destructive_action=true` for delete/remove calls only after verifying the target

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

If a method requires `organizationId` and you haven't provided it, the tool will automatically use your `MERAKI_ORG_ID` from `.env` file.

## Next Steps

1. Restart Claude Desktop (if config changed)
2. Test the helper tools first (they don't call Meraki API)
3. Test read-only operations with your production environment
4. Explore the full API at your own pace!

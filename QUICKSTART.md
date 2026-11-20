# Meraki Dynamic MCP - Quick Start Guide

This guide gets the dynamic server (`meraki-mcp-dynamic.py`) running in Claude Desktop and walks through the first few calls. For full installation steps on macOS and Windows, HTTP transport and Docker, see [INSTALL.md](INSTALL.md).

## How the dynamic server works

The dynamic server does not register one MCP tool per Meraki endpoint. It exposes a small set of tools:

- **12 pre-registered tools** for the most common operations, such as `getOrganizations`, `getOrganizationNetworks`, `getNetworkClients` and `getDeviceSwitchPorts`
- **`call_meraki_api`**, a generic caller that reaches every method in the Meraki Python SDK (more than 1,000 as of SDK 4.7)
- **Discovery tools** (`list_all_methods`, `search_methods`, `get_method_info`) to find methods and their parameters
- **Cache and configuration tools** (`get_mcp_config`, `cache_stats`, `cache_clear`, `get_cached_response`, `list_cached_responses`, `clear_cached_files`)

## Step 1: Inspect (safe, no API calls)

Run the inspection script to see what the SDK provides:

```bash
cd /path/to/meraki-magic-mcp-community
source .venv/bin/activate
python3 inspect_tools.py
```

It prints method counts by section, sample methods, parameter details and search examples. It only inspects the SDK and makes no API calls.

## Step 2: Update Claude Desktop config

Edit your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Option A: Dynamic server only (recommended)**
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
        "READ_ONLY_MODE": "true"
      }
    }
  }
}
```

**Option B: Run both servers**
```json
{
  "mcpServers": {
    "Meraki_Curated": {
      "command": "/path/to/meraki-magic-mcp-community/.venv/bin/fastmcp",
      "args": [
        "run",
        "-t", "stdio",
        "/path/to/meraki-magic-mcp-community/meraki-mcp.py"
      ],
      "env": {
        "MERAKI_API_KEY": "your_api_key_here",
        "MERAKI_ORG_ID": "your_org_id_here",
        "READ_ONLY_MODE": "true"
      }
    },
    "Meraki_Full_API": {
      "command": "/path/to/meraki-magic-mcp-community/.venv/bin/fastmcp",
      "args": [
        "run",
        "-t", "stdio",
        "/path/to/meraki-magic-mcp-community/meraki-mcp-dynamic.py"
      ],
      "env": {
        "MERAKI_API_KEY": "your_api_key_here",
        "MERAKI_ORG_ID": "your_org_id_here",
        "READ_ONLY_MODE": "true"
      }
    }
  }
}
```

Replace `/path/to/` with your actual installation path. For HTTP/Docker deployment options, see [INSTALL.md](INSTALL.md#http-transport-mode).

## Step 3: Restart Claude Desktop

Completely quit and restart Claude Desktop for the config changes to take effect.

## Step 4: Test the discovery tools (safe)

These tools do not call the Meraki API. They only read the SDK's method list.

### See the sections and how many methods each has
```
Use list_all_methods to show me the available sections
```

### List the methods in one section
```
Use list_all_methods with section="wireless"
```

### Search for methods
```
Use search_methods with keyword="firewall"
```

Several words narrow the search, because a method must contain all of them. Results are capped at 50 unless you pass `limit`:
```
Use search_methods with keyword="update wireless ssid"
```

### Get a method's parameters
```
Use get_method_info with section="organizations" and method="getOrganization"
```

## Step 5: Test read-only operations

### Pre-registered tools
```
Use getOrganizations to list all my organizations
```
```
Use getOrganizationNetworks to list the networks in my organization
```
```
Use getNetwork with networkId="YOUR_NETWORK_ID"
```

### Any other method, through `call_meraki_api`
```
Use call_meraki_api with section="appliance", method="getNetworkApplianceFirewallL3FirewallRules" and parameters={"networkId": "YOUR_NETWORK_ID"}
```

All method arguments, including IDs such as `networkId` or `serial`, go inside `parameters`.

## Automatic organization ID

If a method needs `organizationId` and you don't provide it, the server uses `MERAKI_ORG_ID` from its environment.

## Discovery workflow

1. **Find the method** with `search_methods`
2. **Check its parameters** with `get_method_info`
3. **Call it** with `call_meraki_api`

Example:
```
1. "Use search_methods with keyword='site vpn'"
2. "Use get_method_info with section='appliance' and method='getNetworkApplianceVpnSiteToSiteVpn'"
3. "Use call_meraki_api with section='appliance', method='getNetworkApplianceVpnSiteToSiteVpn' and parameters={'networkId': 'L_12345'}"
```

## Safety

The server defaults to `READ_ONLY_MODE=true`. In that mode only `get*` and `list*` methods run; every other method is treated as a write and blocked. Set `READ_ONLY_MODE=false` in the MCP client `env` or process environment when you intend to make changes.

### Safe (read-only)
- Any method starting with `get`
- The discovery, cache and configuration tools

### Use with caution (needs `READ_ONLY_MODE=false`)
- `create*`, `update*`, `claim*`, `reboot*`, `bulk*`, `batch*` and every other non-read method

### Requires explicit confirmation
Destructive methods also need `confirm_destructive_action=true` inside `parameters`, after read-only mode has been disabled:
- `delete*`, `remove*`, `release*`
- `wipe*`, `unenroll*`, `uninstall*`, `revoke*`, `detach*`
- Bulk methods ending in `Delete`

## Common use cases

Each line is a `section` and `method` for `call_meraki_api`.

### Monitor network health
```
organizations  getOrganizationDevicesStatuses
networks       getNetworkEvents
networks       getNetworkHealthAlerts
```

### Manage wireless
```
wireless  getNetworkWirelessSsids
wireless  updateNetworkWirelessSsid
wireless  getNetworkWirelessRfProfiles
wireless  getNetworkWirelessAirMarshal
```

### Configure firewall
```
appliance  getNetworkApplianceFirewallL3FirewallRules
appliance  getNetworkApplianceFirewallL7FirewallRules
appliance  getNetworkApplianceFirewallInboundFirewallRules
```

### Troubleshoot
```
devices   createDeviceLiveToolsPing
devices   createDeviceLiveToolsCableTest
networks  getNetworkEvents
```

### Manage admins
```
organizations  getOrganizationAdmins
organizations  createOrganizationAdmin
organizations  updateOrganizationAdmin
```

## Large responses

Responses above `MAX_RESPONSE_TOKENS` are saved to a cache file and returned as a short preview with the file path. Use `get_cached_response` to page through the full data. See [OPTIMIZATIONS.md](OPTIMIZATIONS.md) for details.

## Error messages

All tools return JSON. Errors look like:

```json
{"error":"Meraki API Error","message":"Invalid network ID","status":404}
```

## More documentation

- [README-DYNAMIC.md](README-DYNAMIC.md) - Dynamic server reference
- [COMPARISON.md](COMPARISON.md) - Manual vs. dynamic server
- [OPTIMIZATIONS.md](OPTIMIZATIONS.md) - Caching, response size limits and read-only mode
- [UPDATE_GUIDE.md](UPDATE_GUIDE.md) - Upgrading the Meraki SDK

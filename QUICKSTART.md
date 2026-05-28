# Meraki Dynamic MCP - Quick Start Guide

## What Was Created

I've created a **dynamic version** of your Meraki MCP that automatically exposes **all ~804 Meraki SDK methods** as MCP tools.

## Files Created

1. **meraki-mcp-dynamic.py** - The dynamic MCP server
2. **inspect_tools.py** - Safe inspection script (no API calls)
3. **README-DYNAMIC.md** - Detailed documentation
4. **COMPARISON.md** - Manual vs. Dynamic comparison
5. **QUICKSTART.md** - This file

## Step 1: Inspect (Safe - No API Calls)

Before using the dynamic MCP, run the inspection script to see what will be available:

```bash
cd /path/to/meraki-magic-mcp-community
source .venv/bin/activate
python3 inspect_tools.py
```

This will show you:
- Tool counts by section
- Sample tool names
- Parameter details
- Search examples
- Coverage comparison

**This is 100% safe** - it doesn't make any API calls.

## Step 2: Update Claude Desktop Config

Edit your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Option A: Replace existing MCP**
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

**Option B: Run both (recommended)**
```json
{
  "mcpServers": {
    "Meraki_Curated": {
      "command": "/path/to/meraki-magic-mcp-community/.venv/bin/fastmcp",
      "args": [
        "run",
        "-t", "stdio",
        "/path/to/meraki-magic-mcp-community/meraki-mcp.py"
      ]
    },
    "Meraki_Full_API": {
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

Replace `/path/to/` with your actual installation path. For HTTP/Docker deployment options, see [INSTALL.md](INSTALL.md#http-transport-mode).

## Step 3: Restart Claude Desktop

Completely quit and restart Claude Desktop for the config changes to take effect.

## Step 4: Test Discovery Tools (Safe)

These helper tools **don't make API calls** - they just list available tools:

### List all tools
```
Use list_available_tools to show me all available tools
```

### List tools by category
```
Use list_available_tools with category="wireless" to show wireless tools
```

### Search for tools
```
Use search_tools with keyword="firewall" to find firewall-related tools
```

### Get tool details
```
Use get_tool_info with tool_name="organizations_getOrganization" to see parameters
```

## Step 5: Test Read-Only Operations

Start with safe, read-only operations:

### Get organizations
```
Use organizations_getOrganizations to list all my organizations
```

### Get networks
```
Use organizations_getOrganizationNetworks with organizationId="YOUR_ORG_ID"
```

### Get devices
```
Use organizations_getOrganizationDevices with organizationId="YOUR_ORG_ID"
```

### Get network details
```
Use networks_getNetwork with networkId="YOUR_NETWORK_ID"
```

## Tool Naming Pattern

All tools follow this pattern: `{section}_{methodName}`

Examples:
- `organizations_getOrganization`
- `networks_getNetworkClients`
- `wireless_getNetworkWirelessSsids`
- `devices_rebootDevice`
- `appliance_updateNetworkApplianceFirewallL3FirewallRules`

## Auto-Organization ID

If you don't provide `organizationId` to a tool that needs it, the MCP will automatically use your `MERAKI_ORG_ID` from `.env`.

## Discovery Workflow

1. **Find tools** - Use `search_tools` to find what you need
2. **Check parameters** - Use `get_tool_info` to see required parameters
3. **Call the tool** - Use the tool with proper parameters

Example:
```
1. "Use search_tools with keyword='vpn' to find VPN-related tools"
2. "Use get_tool_info with tool_name='appliance_getNetworkApplianceVpnSiteToSiteVpn'"
3. "Use appliance_getNetworkApplianceVpnSiteToSiteVpn with networkId='L_12345'"
```

## Safety Tips

The server defaults to `READ_ONLY_MODE=true`, so write operations are blocked until you explicitly set `READ_ONLY_MODE=false` in `.env`.

### ✅ Safe Operations (Read-Only)
- Anything with `get` in the name
- `list_available_tools`
- `search_tools`
- `get_tool_info`

### ⚠️ Use with Caution
- Anything with `update` in the name
- Anything with `create` in the name
- `reboot` operations

### 🛑 Double-Check Before Using
- Anything with `delete` in the name
- Anything with `remove` in the name
- Network/device claiming operations

Delete/remove calls also require `confirm_destructive_action=true` after read-only mode has been disabled.

## Common Use Cases

### Monitor network health
```
organizations_getOrganizationDevicesStatuses
networks_getNetworkEvents
networks_getNetworkHealthChannelUtilization
```

### Manage wireless
```
wireless_getNetworkWirelessSsids
wireless_updateNetworkWirelessSsid
wireless_getNetworkWirelessRfProfiles
wireless_getNetworkWirelessAirMarshal
```

### Configure firewall
```
appliance_getNetworkApplianceFirewallL3FirewallRules
appliance_getNetworkApplianceFirewallL7FirewallRules
appliance_getNetworkApplianceFirewallInboundFirewallRules
```

### Troubleshoot
```
devices_createDeviceLiveToolsPing
devices_createDeviceLiveToolsCableTest
networks_getNetworkEvents
```

### Manage admins
```
organizations_getOrganizationAdmins
organizations_createOrganizationAdmin
organizations_updateOrganizationAdmin
```

## Error Messages

All tools return formatted JSON. Errors look like:

```json
{
  "error": "Meraki API Error",
  "message": "Invalid network ID",
  "status": 404
}
```

## Next Steps

1. ✅ Run `inspect_tools.py` to see available tools
2. ✅ Update Claude Desktop config
3. ✅ Restart Claude Desktop
4. ✅ Test discovery tools (list_available_tools, search_tools)
5. ✅ Test read-only operations
6. ✅ Gradually explore more advanced features

## Support

- **README-DYNAMIC.md** - Full documentation
- **COMPARISON.md** - Manual vs. Dynamic comparison
- **inspect_tools.py** - See all available tools safely

## Coverage

- **Manual MCP**: 40 tools (0.57% of API)
- **Dynamic MCP**: ~804 tools (100% of SDK)
- **Increase**: 20x more coverage!

Happy automating! 🚀

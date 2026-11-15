# Manual vs. Dynamic MCP Comparison

## Overview

This project ships two MCP servers:

| Feature | Manual (`meraki-mcp.py`) | Dynamic (`meraki-mcp-dynamic.py`) |
|---------|--------------------------|-----------------------------------|
| **MCP tools** | 83 hand-written tools | 22 tools: 12 common operations, `call_meraki_api`, and discovery/cache helpers |
| **API coverage** | The endpoints those 83 tools wrap | Every method in the Meraki Python SDK (more than 1,000 as of SDK 4.7) |
| **Type safety** | Pydantic schemas for complex updates | Generic `parameters` object, checked by the SDK |
| **Documentation** | Hand-written descriptions | SDK docstrings via `get_method_info` |
| **Maintenance** | Each tool is updated by hand | New SDK methods are available after an SDK upgrade |
| **Read-only mode** | Yes (`READ_ONLY_MODE`, default on) | Yes (`READ_ONLY_MODE`, default on) |
| **Destructive confirmation** | Yes | Yes |
| **Response caching and size limits** | No | Yes |
| **Transports** | stdio, HTTP, SSE | stdio, HTTP, SSE |
| **Docker** | Supported | Supported (default) |

## What each version includes

### Manual MCP (`meraki-mcp.py`)

83 curated tools with snake_case names, grouped as:

- **Organization** - organizations, networks, devices, inventory, licenses, configuration changes
- **Network** - network details and updates, clients, client policies, traffic
- **Device** - details, updates, claim/remove, reboot, status, uplinks
- **Wireless** - SSIDs, wireless settings, RF profiles, channel utilization, signal quality
- **Switch** - ports, VLANs, port statuses, QoS rules, access control lists
- **Appliance** - security events, VPN, firewall rules, content filtering, traffic shaping
- **Camera** - video and quality settings, analytics, snapshots, sense
- **Advanced organization** - admins, API requests, webhook logs, network events and alert settings
- **Live device tools** - ping, cable test, LED blink, wake-on-LAN
- **Network automation** - action batches

The full list with arguments is in [README.md](README.md#manual-mcp-tools-reference).

### Dynamic MCP (`meraki-mcp-dynamic.py`)

**Pre-registered tools (12)**
`getOrganizations`, `getOrganizationAdmins`, `getOrganizationNetworks`, `getOrganizationDevices`, `getNetwork`, `getNetworkClients`, `getNetworkEvents`, `getNetworkDevices`, `getDevice`, `getNetworkWirelessSsids`, `getDeviceSwitchPorts`, `updateDeviceSwitchPort`

**Generic caller (1)**
`call_meraki_api(section, method, parameters)` reaches every method in these SDK sections:

| Section | Methods (SDK 4.7) |
|---------|-------------------|
| organizations | 251 |
| appliance | 181 |
| wireless | 157 |
| networks | 115 |
| switch | 102 |
| sm | 49 |
| camera | 46 |
| devices | 41 |
| cellularGateway | 24 |
| sensor | 19 |
| campusGateway | 18 |
| wirelessController | 15 |
| licensing | 8 |
| insight | 7 |
| administered | 4 |
| spaces | 2 |

Run `python3 inspect_tools.py` or call `list_all_methods` for the counts in your installed SDK.

**Discovery tools (3)**
`list_all_methods`, `search_methods`, `get_method_info`

**Cache and configuration tools (6)**
`get_mcp_config`, `cache_stats`, `cache_clear`, `get_cached_response`, `list_cached_responses`, `clear_cached_files`

## Example use cases

### Use the manual MCP when

1. **Setting up a new network** - `create_network`, `get_network_details`, `update_network`
2. **Basic wireless config** - `get_wireless_ssids`, `update_wireless_ssid`
3. **Device management basics** - `claim_devices`, `update_device`, `reboot_device`
4. **Client monitoring** - `get_clients`, `get_client_policy`, `update_client_policy`

### Use the dynamic MCP when

Each line is a `section` and `method` for `call_meraki_api`.

1. **Advanced wireless optimization**
   - wireless `getNetworkWirelessRfProfiles`
   - wireless `createNetworkWirelessRfProfile`
   - wireless `getNetworkWirelessChannelUtilizationHistory`
   - wireless `getNetworkWirelessFailedConnections`

2. **Security and compliance**
   - appliance `getNetworkApplianceFirewallL7FirewallRules`
   - appliance `getNetworkApplianceSecurityIntrusion`
   - organizations `getOrganizationConfigurationChanges`

3. **Troubleshooting**
   - networks `getNetworkEvents`
   - devices `createDeviceLiveToolsPing`
   - devices `createDeviceLiveToolsCableTest`

4. **Automation and webhooks**
   - networks `createNetworkWebhooksHttpServer`
   - organizations `createOrganizationAlertsProfile`
   - organizations `createOrganizationActionBatch`

5. **Advanced switch management**
   - switch `createNetworkSwitchStack`
   - switch `getNetworkSwitchAccessPolicies`
   - switch `createNetworkSwitchPortSchedule`
   - switch `getNetworkSwitchQosRules`

6. **Licensing and admin**
   - organizations `getOrganizationAdmins`
   - organizations `createOrganizationAdmin`
   - licensing `getOrganizationLicensingCotermLicenses`

7. **Camera analytics**
   - camera `getDeviceCameraAnalyticsLive`
   - camera `getDeviceCameraAnalyticsZones`
   - camera `generateDeviceCameraSnapshot`

## Recommendation

**Start with the dynamic MCP** for full API coverage with a small tool list. The manual version is a reference for adding:
- Pydantic schemas for complex updates
- Tool descriptions written for a specific workflow
- Custom logic that combines several API calls

Both servers can run side by side; see [QUICKSTART.md](QUICKSTART.md#step-2-update-claude-desktop-config).

[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/mkutka-meraki-magic-mcp-badge.png)](https://mseep.ai/app/mkutka-meraki-magic-mcp)

Meraki Magic MCP

Meraki Magic is a Python-based MCP (Model Context Protocol) server for Cisco's Meraki Dashboard. Meraki Magic provides tools for querying the Meraki Dashboard API to discover, monitor, and manage your Meraki environment.

## Two Versions Available

**🚀 Dynamic MCP (Recommended)** - `meraki-mcp-dynamic.py`
- **~804 API endpoints** automatically exposed
- **100% SDK coverage** - all Meraki API methods available
- **Auto-updates** when you upgrade the Meraki SDK
- **No manual coding** required for new endpoints

**📋 Manual MCP** - `meraki-mcp.py`
- **40 curated endpoints** with detailed schemas
- **Type-safe** with Pydantic validation
- **Custom business logic** for specific use cases
- **Clean documentation** for common operations

## Features

**Dynamic MCP includes:**
- All organization management (admins, networks, devices, inventory, licensing)
- Complete wireless management (SSIDs, RF profiles, Air Marshal, analytics)
- Full switch management (ports, VLANs, stacks, QoS, access policies)
- Advanced appliance/security (all firewall types, NAT, VPN, traffic shaping)
- Camera management (analytics, quality, schedules, permissions)
- Network monitoring (events, alerts, health, performance)
- Live troubleshooting tools (ping, cable test, ARP table)
- Webhooks and automation (alert profiles, action batches)
- And 700+ more endpoints...

**Manual MCP includes:**
- Network discovery and management
- Device discovery and configuration
- Client discovery and policy management
- Wireless SSID management
- Switch port and VLAN configuration
- Basic firewall rules
- Camera settings

## Quick Installation

### Prerequisites
- Python 3.13+
- Claude Desktop (or any MCP-compatible client)
- Meraki Dashboard API Key
- Meraki Organization ID

### Fast Track

**macOS:**
```bash
git clone https://github.com/CiscoDevNet/meraki-magic-mcp-community.git
cd meraki-magic-mcp-community
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env-example .env
# Edit .env with your API credentials
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/CiscoDevNet/meraki-magic-mcp-community.git
cd meraki-magic-mcp-community
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env-example .env
# Edit .env with your API credentials
```

**📖 For detailed step-by-step instructions, see [INSTALL.md](INSTALL.md)**

## Configuration

Edit `.env` with your Meraki credentials:

```env
MERAKI_API_KEY="your_api_key_here"
MERAKI_ORG_ID="your_org_id_here"
MERAKI_BASE_URL="https://api.meraki.com/api/v1"

# Optional: Performance tuning
ENABLE_CACHING=true
CACHE_TTL_SECONDS=300
READ_ONLY_MODE=true
```

Get your API key from: **Meraki Dashboard → Organization → Settings → Dashboard API access**

`READ_ONLY_MODE` defaults to `true` to block create/update/delete/remove operations. Set `READ_ONLY_MODE=false` only when you intend to make changes. Delete/remove calls also require `confirm_destructive_action=true`.

Use `MERAKI_BASE_URL` to point the MCP server at another Meraki region or compatible Dashboard API base URI.

## Deployment Options

There are three ways to deploy Meraki Magic MCP:

| Method | Best For | Transport |
|--------|----------|-----------|
| **[Local (stdio)](#claude-desktop-setup)** | Claude Desktop / Cursor on same machine | stdio |
| **[HTTP Server](#http-transport)** | Remote access, shared team server | StreamableHTTP |
| **[Docker](#docker-deployment)** | Containerized / production deployments | StreamableHTTP |

## Claude Desktop Setup

### Dynamic MCP (Recommended)

1. **Locate Claude config file:**
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2. **Edit config with your paths:**

**macOS Example:**
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

**Windows Example:**
```json
{
  "mcpServers": {
    "Meraki_Magic_MCP": {
      "command": "C:/Users/YourName/meraki-magic-mcp-community/.venv/Scripts/fastmcp.exe",
      "args": [
        "run",
        "-t", "stdio",
        "C:/Users/YourName/meraki-magic-mcp-community/meraki-mcp-dynamic.py"
      ]
    }
  }
}
```

Replace `/path/to/` with your actual installation path. Windows users: use forward slashes `/` and include `.exe`.

3. **Restart Claude Desktop** (Quit completely, then reopen)

4. **Verify:** Ask Claude "What MCP servers are available?"

**📖 Detailed setup instructions: [INSTALL.md](INSTALL.md)**

### Manual MCP (Original)

Use `meraki-mcp.py` instead of `meraki-mcp-dynamic.py` in the config above.

### Both MCPs (Advanced)

You can run both simultaneously:

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

## HTTP Transport

Run the MCP server over HTTP for remote access or shared team use:

```bash
# Set transport in .env
MCP_TRANSPORT=http
MCP_HOST=127.0.0.1  # Use 0.0.0.0 for remote access
MCP_PORT=8000

# Start the server
python meraki-mcp-dynamic.py
# Server available at http://127.0.0.1:8000/mcp
```

Connect Claude Desktop to an HTTP server using [mcp-remote](https://www.npmjs.com/package/mcp-remote) (requires Node.js):

```json
{
  "mcpServers": {
    "Meraki_Magic_MCP": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://127.0.0.1:8000/mcp"]
    }
  }
}
```

## Docker Deployment

The fastest way to deploy remotely:

```bash
cp .env-example .env
# Edit .env with your MERAKI_API_KEY and MERAKI_ORG_ID
docker compose up -d
# Server available at http://localhost:8000/mcp
```

**📖 Full HTTP & Docker instructions: [INSTALL.md](INSTALL.md#http-transport-mode)**

## Keeping Updated

The dynamic MCP automatically stays current with Meraki's API:

```bash
# Manually update SDK
pip install --upgrade meraki
```

Then restart Claude Desktop. See [UPDATE_GUIDE.md](UPDATE_GUIDE.md) for details.

## Performance & Safety Features

The dynamic MCP includes several optimizations:

✅ **Response Caching** - Read-only operations cached for 5 minutes (reduces API calls by 50-90%)
✅ **Read-Only Mode** - Optional safety mode blocks write operations
✅ **Auto-Retry** - Automatic retry on failures (3 attempts)
✅ **Rate Limit Handling** - Automatically waits when rate limited
✅ **Operation Labeling** - Tools labeled as [READ], [WRITE], or [MISC]

See [OPTIMIZATIONS.md](OPTIMIZATIONS.md) for details.

## Documentation

- **[INSTALL.md](INSTALL.md)** - Detailed installation guide (macOS & Windows)
- **[QUICKSTART.md](QUICKSTART.md)** - Get started quickly with examples
- **[README-DYNAMIC.md](README-DYNAMIC.md)** - Dynamic MCP technical details
- **[COMPARISON.md](COMPARISON.md)** - Compare manual vs dynamic approaches
- **[UPDATE_GUIDE.md](UPDATE_GUIDE.md)** - Keep your MCP current with latest APIs
- **[OPTIMIZATIONS.md](OPTIMIZATIONS.md)** - Performance and safety features

## How It Works

The Dynamic MCP provides two ways to access Meraki APIs:

1. **Pre-registered tools** (12 most common operations):
   - `getOrganizations`, `getOrganizationAdmins`, `getOrganizationNetworks`
   - `getNetworkClients`, `getNetworkEvents`, `getDeviceSwitchPorts`
   - And 6 more common operations

2. **Generic API caller** (`call_meraki_api`):
   - Access ALL 804+ Meraki API methods
   - Example: `call_meraki_api(section="appliance", method="getNetworkApplianceFirewallL3FirewallRules", parameters={"networkId": "L_123"})`
   - Destructive methods require `confirm_destructive_action=true` in `parameters`

## Example Usage

```
Get all admins in my organization

Show me firewall rules for network "Main Office"

Update switch port 12 on device ABC123 to enable BPDU guard

Get wireless clients from the last hour

Create a new network named "Branch Office"
```

## Support

- **Issues:** [GitHub Issues](https://github.com/CiscoDevNet/meraki-magic-mcp-community/issues)
- **Meraki API Docs:** [developer.cisco.com/meraki/api-v1](https://developer.cisco.com/meraki/api-v1)
- **MCP Protocol:** [modelcontextprotocol.io](https://modelcontextprotocol.io)

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## Manual MCP Tools Reference

The following tools are available in the manual MCP (`meraki-mcp.py`). **The dynamic MCP provides access to these and 760+ additional endpoints through the generic `call_meraki_api` tool.**

### Network Tools Guide

This guide provides a comprehensive overview of the curated network tools available in the manual MCP, organized by category and functionality.

### Table of Contents

1. [Organization Management Tools](#organization-management-tools)
2. [Network Management Tools](#network-management-tools)
3. [Device Management Tools](#device-management-tools)
4. [Wireless Management Tools](#wireless-management-tools)
5. [Switch Management Tools](#switch-management-tools)
6. [Appliance Management Tools](#appliance-management-tools)
7. [Camera Management Tools](#camera-management-tools)
8. [Network Automation Tools](#network-automation-tools)
9. [Advanced Monitoring Tools](#advanced-monitoring-tools)
10. [Live Device Tools](#live-device-tools)

---

## Organization Management Tools

### Basic Organization Operations
- **`get_organizations()`** - Get a list of organizations the user has access to
- **`get_organization_details(org_id)`** - Get details for a specific organization
- **`get_organization_status(org_id)`** - Get the status and health of an organization
- **`get_organization_inventory(org_id)`** - Get the inventory for an organization
- **`get_organization_license(org_id)`** - Get the license state for an organization
- **`get_organization_conf_change(org_id)`** - Get the org change state for an organization

### Advanced Organization Management
- **`get_organization_admins(org_id)`** - Get a list of organization admins
- **`create_organization_admin(org_id, email, name, org_access, tags, networks)`** - Create a new organization admin
- **`get_organization_api_requests(org_id, timespan)`** - Get organization API request history
- **`get_organization_webhook_logs(org_id, timespan)`** - Get organization webhook logs

### Network Management
- **`get_networks(org_id)`** - Get a list of networks from Meraki
- **`create_network(name, tags, productTypes, org_id, copyFromNetworkId)`** - Create a new network
- **`delete_network(network_id, confirm_destructive_action)`** - Delete a network in Meraki
- **`get_network_details(network_id)`** - Get details for a specific network
- **`update_network(network_id, update_data)`** - Update a network's properties

---

## Network Management Tools

### Network Monitoring
- **`get_network_events(network_id, timespan, per_page)`** - Get network events history
- **`get_network_event_types(network_id)`** - Get available network event types
- **`get_network_alerts_history(network_id, timespan)`** - Get network alerts history
- **`get_network_alerts_settings(network_id)`** - Get network alerts settings
- **`update_network_alerts_settings(network_id, defaultDestinations, alerts)`** - Update network alerts settings

### Client Management
- **`get_clients(network_id, timespan)`** - Get a list of clients from a network
- **`get_client_details(network_id, client_id)`** - Get details for a specific client
- **`get_client_usage(network_id, client_id)`** - Get the usage history for a client
- **`get_client_policy(network_id, client_id)`** - Get the policy for a specific client
- **`update_client_policy(network_id, client_id, device_policy, group_policy_id)`** - Update policy for a client

### Network Traffic & Analysis
- **`get_network_traffic(network_id, timespan)`** - Get traffic analysis data for a network

---

## Device Management Tools

### Device Information
- **`get_devices(org_id)`** - Get a list of devices from Meraki
- **`get_network_devices(network_id)`** - Get a list of devices in a specific network
- **`get_device_details(serial)`** - Get details for a specific device by serial number
- **`get_device_status(serial)`** - Get the current status of a device
- **`get_device_uplink(serial)`** - Get the uplink status of a device

### Device Operations
- **`update_device(serial, device_settings)`** - Update a device in the Meraki organization
- **`claim_devices(network_id, serials)`** - Claim one or more devices into a Meraki network
- **`remove_device(network_id, serial, confirm_destructive_action)`** - Remove a device from its network
- **`reboot_device(serial)`** - Reboot a device

### Device Monitoring
- **`get_device_clients(serial, timespan)`** - Get clients connected to a specific device

---

## Live Device Tools

### Network Diagnostics
- **`ping_device(serial, target_ip, count)`** - Ping a device from another device
- **`get_device_ping_results(serial, ping_id)`** - Get results from a device ping test
- **`cable_test_device(serial, ports)`** - Run cable test on device ports
- **`get_device_cable_test_results(serial, cable_test_id)`** - Get results from a device cable test

### Device Control
- **`blink_device_leds(serial, duration)`** - Blink device LEDs for identification
- **`wake_on_lan_device(serial, mac)`** - Send wake-on-LAN packet to a device

---

## Wireless Management Tools

### Basic Wireless Operations
- **`get_wireless_ssids(network_id)`** - Get wireless SSIDs for a network
- **`update_wireless_ssid(network_id, ssid_number, ssid_settings)`** - Update a wireless SSID
- **`get_wireless_settings(network_id)`** - Get wireless settings for a network

### Advanced Wireless Management
- **`get_wireless_rf_profiles(network_id)`** - Get wireless RF profiles for a network
- **`create_wireless_rf_profile(network_id, name, band_selection_type, **kwargs)`** - Create a wireless RF profile
- **`get_wireless_channel_utilization(network_id, timespan)`** - Get wireless channel utilization history
- **`get_wireless_signal_quality(network_id, timespan)`** - Get wireless signal quality history
- **`get_wireless_connection_stats(network_id, timespan)`** - Get wireless connection statistics
- **`get_wireless_client_connectivity_events(network_id, client_id, timespan)`** - Get wireless client connectivity events

---

## Switch Management Tools

### Basic Switch Operations
- **`get_switch_ports(serial)`** - Get ports for a switch
- **`update_switch_port(serial, port_id, name, tags, enabled, vlan)`** - Update a switch port
- **`get_switch_vlans(network_id)`** - Get VLANs for a network
- **`create_switch_vlan(network_id, vlan_id, name, subnet, appliance_ip)`** - Create a switch VLAN

### Advanced Switch Management
- **`get_switch_port_statuses(serial)`** - Get switch port statuses
- **`cycle_switch_ports(serial, ports)`** - Cycle (restart) switch ports
- **`get_switch_access_control_lists(network_id)`** - Get switch access control lists
- **`update_switch_access_control_lists(network_id, rules)`** - Update switch access control lists
- **`get_switch_qos_rules(network_id)`** - Get switch QoS rules
- **`create_switch_qos_rule(network_id, vlan, protocol, src_port, **kwargs)`** - Create a switch QoS rule

---

## Appliance Management Tools

### Basic Appliance Operations
- **`get_security_center(network_id)`** - Get security information for a network
- **`get_vpn_status(network_id)`** - Get VPN status for a network
- **`get_firewall_rules(network_id)`** - Get firewall rules for a network
- **`update_firewall_rules(network_id, rules)`** - Update firewall rules for a network

### Advanced Appliance Management
- **`get_appliance_vpn_site_to_site(network_id)`** - Get appliance VPN site-to-site configuration
- **`update_appliance_vpn_site_to_site(network_id, mode, hubs, subnets)`** - Update appliance VPN site-to-site configuration
- **`get_appliance_content_filtering(network_id)`** - Get appliance content filtering settings
- **`update_appliance_content_filtering(network_id, **kwargs)`** - Update appliance content filtering settings
- **`get_appliance_security_events(network_id, timespan)`** - Get appliance security events
- **`get_appliance_traffic_shaping(network_id)`** - Get appliance traffic shaping settings
- **`update_appliance_traffic_shaping(network_id, global_bandwidth_limits)`** - Update appliance traffic shaping settings

---

## Camera Management Tools

### Basic Camera Operations
- **`get_camera_video_settings(network_id, serial)`** - Get video settings for a camera
- **`get_camera_quality_settings(network_id)`** - Get quality and retention settings for cameras

### Advanced Camera Management
- **`get_camera_analytics_live(serial)`** - Get live camera analytics
- **`get_camera_analytics_overview(serial, timespan)`** - Get camera analytics overview
- **`get_camera_analytics_zones(serial)`** - Get camera analytics zones
- **`generate_camera_snapshot(serial, timestamp)`** - Generate a camera snapshot
- **`get_camera_sense(serial)`** - Get camera sense configuration
- **`update_camera_sense(serial, sense_enabled, mqtt_broker_id, audio_detection)`** - Update camera sense configuration

---

## Network Automation Tools

### Action Batches
- **`create_action_batch(org_id, actions, confirmed, synchronous)`** - Create an action batch for bulk operations
- **`get_action_batch_status(org_id, batch_id)`** - Get action batch status
- **`get_action_batches(org_id)`** - Get all action batches for an organization

---

## Schema Definitions

The manual MCP includes comprehensive Pydantic schemas for data validation:

- `SsidUpdateSchema` - Wireless SSID configuration
- `FirewallRule` - Firewall rule configuration
- `DeviceUpdateSchema` - Device update parameters
- `NetworkUpdateSchema` - Network update parameters
- `AdminCreationSchema` - Admin creation parameters
- `ActionBatchSchema` - Action batch configuration
- `VpnSiteToSiteSchema` - VPN site-to-site configuration
- `ContentFilteringSchema` - Content filtering settings
- `TrafficShapingSchema` - Traffic shaping configuration
- `CameraSenseSchema` - Camera sense settings
- `SwitchQosRuleSchema` - Switch QoS rule configuration

---

## Best Practices

1. **Error Handling**: Always check API responses for errors
2. **Rate Limiting**: The Meraki API has rate limits; use appropriate delays (or use dynamic MCP with caching)
3. **Batch Operations**: Use action batches for bulk operations
4. **Validation**: Use the provided schemas for data validation
5. **Monitoring**: Regularly check network events and alerts
6. **Security**: Keep API keys secure and rotate them regularly

---

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify your API key is correct and has appropriate permissions
2. **Rate Limiting**: If you encounter rate limiting, implement delays between requests (or use dynamic MCP with caching)
3. **Network Not Found**: Ensure the network ID is correct and accessible
4. **Device Not Found**: Verify the device serial number is correct and the device is online

### Debug Information

Enable debug logging by setting the appropriate log level in your environment.

---

## ⚠️ Disclaimer

**IMPORTANT: PRODUCTION USE DISCLAIMER**

This software is provided "AS IS" without warranty of any kind, either express or implied. The authors and contributors make no representations or warranties regarding the suitability, reliability, availability, accuracy, or completeness of this software for any purpose.

**USE AT YOUR OWN RISK**: This MCP server is designed for development, testing, and educational purposes. Running this software in production environments is done entirely at your own risk. The authors and contributors are not responsible for any damages, data loss, service interruptions, or other issues that may arise from the use of this software in production environments.

**SECURITY CONSIDERATIONS**: This software requires access to your Meraki API credentials. Ensure that:
- API keys are stored securely and not committed to version control
- API keys have appropriate permissions and are rotated regularly
- Network access is properly secured
- Regular security audits are performed

**NO WARRANTY**: The authors disclaim all warranties, including but not limited to warranties of merchantability, fitness for a particular purpose, and non-infringement. In no event shall the authors be liable for any claim, damages, or other liability arising from the use of this software.

**SUPPORT**: This is an open-source project. For production use, consider implementing additional testing, monitoring, and support mechanisms appropriate for your environment.

## License

See [LICENSE](LICENSE) file for details.

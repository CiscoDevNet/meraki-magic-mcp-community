# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: MIT

import os
import sys
import json
import meraki
import asyncio
import functools
from typing import Dict, List, Optional, Any, TypedDict, Union, Callable
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from pathlib import Path
from meraki_mcp_config import (
    get_meraki_base_url,
    get_read_only_mode,
    guard_write_operation,
)

# Load environment variables from .env file
load_dotenv(Path(__file__).resolve().parent / ".env")

# Transport configuration
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio").lower()
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))

# Create an MCP server
mcp = FastMCP("Meraki Magic MCP", host=MCP_HOST, port=MCP_PORT)

# Configuration
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY")
MERAKI_ORG_ID = os.getenv("MERAKI_ORG_ID")
MERAKI_BASE_URL = get_meraki_base_url()
READ_ONLY_MODE = get_read_only_mode()

if not MERAKI_API_KEY:
    print("FATAL: MERAKI_API_KEY is not set. Add it to .env or the environment.", file=sys.stderr)
    sys.exit(1)

# Initialize Meraki API client using Meraki SDK
dashboard = meraki.DashboardAPI(
    api_key=MERAKI_API_KEY,
    base_url=MERAKI_BASE_URL,
    suppress_logging=True,
    caller="MerakiMagicMCP/0.1.0 Anthropic",
    maximum_retries=3,
    wait_on_rate_limit=True,
)

###################
# ASYNC UTILITIES
###################

def to_async(func: Callable) -> Callable:
    """
    Convert a synchronous function to an asynchronous function

    Args:
        func: The synchronous function to convert

    Returns:
        An asynchronous version of the function
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper

def _build_kwargs(**params) -> dict:
    """Return only non-None keyword arguments. Correctly handles False and 0."""
    return {k: v for k, v in params.items() if v is not None}

def _guard_write(method_name: str, confirm_destructive_action: bool = False) -> str | None:
    return guard_write_operation(method_name, READ_ONLY_MODE, confirm_destructive_action)

# Create async versions of commonly used Meraki API methods
async_get_organizations = to_async(dashboard.organizations.getOrganizations)
async_get_organization = to_async(dashboard.organizations.getOrganization)
async_get_organization_networks = to_async(dashboard.organizations.getOrganizationNetworks)
async_get_organization_devices = to_async(dashboard.organizations.getOrganizationDevices)
async_get_network = to_async(dashboard.networks.getNetwork)
async_get_network_devices = to_async(dashboard.networks.getNetworkDevices)
async_get_network_clients = to_async(dashboard.networks.getNetworkClients)
async_get_device = to_async(dashboard.devices.getDevice)
async_update_device = to_async(dashboard.devices.updateDevice)
async_get_wireless_ssids = to_async(dashboard.wireless.getNetworkWirelessSsids)
async_update_wireless_ssid = to_async(dashboard.wireless.updateNetworkWirelessSsid)

###################
# SCHEMA DEFINITIONS
###################

# Wireless SSID Schema
class Dot11wSettings(BaseModel):
    enabled: bool = Field(False, description="Whether 802.11w is enabled or not")
    required: bool = Field(False, description="Whether 802.11w is required or not")

class Dot11rSettings(BaseModel):
    enabled: bool = Field(False, description="Whether 802.11r is enabled or not")
    adaptive: bool = Field(False, description="Whether 802.11r is adaptive or not")

class RadiusServer(BaseModel):
    host: str = Field(..., description="IP address of the RADIUS server")
    port: int = Field(..., description="Port of the RADIUS server")
    secret: str = Field(..., description="Secret for the RADIUS server")
    radsecEnabled: Optional[bool] = Field(None, description="Whether RADSEC is enabled or not")
    openRoamingCertificateId: Optional[int] = Field(None, description="OpenRoaming certificate ID")
    caCertificate: Optional[str] = Field(None, description="CA certificate for RADSEC")

class SsidUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, description="The name of the SSID")
    enabled: Optional[bool] = Field(None, description="Whether the SSID is enabled or not")
    authMode: Optional[str] = Field(None, description="The auth mode for the SSID (e.g., 'open', 'psk', '8021x-radius')")
    enterpriseAdminAccess: Optional[str] = Field(None, description="Enterprise admin access setting")
    encryptionMode: Optional[str] = Field(None, description="The encryption mode for the SSID")
    psk: Optional[str] = Field(None, description="The pre-shared key for the SSID when using PSK auth mode")
    wpaEncryptionMode: Optional[str] = Field(None, description="WPA encryption mode (e.g., 'WPA1 and WPA2', 'WPA2 only')")
    dot11w: Optional[Dot11wSettings] = Field(None, description="802.11w settings")
    dot11r: Optional[Dot11rSettings] = Field(None, description="802.11r settings")
    splashPage: Optional[str] = Field(None, description="The type of splash page for the SSID")
    radiusServers: Optional[List[RadiusServer]] = Field(None, description="List of RADIUS servers")
    visible: Optional[bool] = Field(None, description="Whether the SSID is visible or not")
    availableOnAllAps: Optional[bool] = Field(None, description="Whether the SSID is available on all APs")
    bandSelection: Optional[str] = Field(None, description="Band selection for SSID (e.g., '5 GHz band only', 'Dual band operation')")

# Firewall Rule Schema
class FirewallRule(BaseModel):
    comment: str = Field(..., description="Description of the firewall rule")
    policy: str = Field(..., description="'allow' or 'deny'")
    protocol: str = Field(..., description="The protocol (e.g., 'tcp', 'udp', 'any')")
    srcPort: Optional[str] = Field("Any", description="Source port (e.g., '80', '443-8080', 'Any')")
    srcCidr: str = Field("Any", description="Source CIDR (e.g., '192.168.1.0/24', 'Any')")
    destPort: Optional[str] = Field("Any", description="Destination port (e.g., '80', '443-8080', 'Any')")
    destCidr: str = Field("Any", description="Destination CIDR (e.g., '192.168.1.0/24', 'Any')")
    syslogEnabled: Optional[bool] = Field(False, description="Whether syslog is enabled for this rule")

# Device Update Schema
class DeviceUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, description="The name of the device")
    tags: Optional[List[str]] = Field(None, description="List of tags for the device")
    lat: Optional[float] = Field(None, description="Latitude of the device")
    lng: Optional[float] = Field(None, description="Longitude of the device")
    address: Optional[str] = Field(None, description="Physical address of the device")
    notes: Optional[str] = Field(None, description="Notes for the device")
    moveMapMarker: Optional[bool] = Field(None, description="Whether to move the map marker or not")
    switchProfileId: Optional[str] = Field(None, description="Switch profile ID")
    floorPlanId: Optional[str] = Field(None, description="Floor plan ID")

# Network Update Schema
class NetworkUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, description="The name of the network")
    timeZone: Optional[str] = Field(None, description="The timezone of the network")
    tags: Optional[List[str]] = Field(None, description="List of tags for the network")
    enrollmentString: Optional[str] = Field(None, description="Enrollment string for the network")
    notes: Optional[str] = Field(None, description="Notes for the network")

# Admin Creation Schema
class AdminCreationSchema(BaseModel):
    email: str = Field(..., description="Email address of the admin")
    name: str = Field(..., description="Name of the admin")
    orgAccess: str = Field(..., description="Access level for the organization")
    tags: Optional[List[str]] = Field(None, description="List of tags for the admin")
    networks: Optional[List[dict]] = Field(None, description="Network access for the admin")

# Action Batch Schema
class ActionBatchSchema(BaseModel):
    actions: List[dict] = Field(..., description="List of actions to perform")
    confirmed: bool = Field(True, description="Whether the batch is confirmed")
    synchronous: bool = Field(False, description="Whether the batch is synchronous")

# VPN Configuration Schema
class VpnSiteToSiteSchema(BaseModel):
    mode: str = Field(..., description="VPN mode (none, full, or hub-and-spoke)")
    hubs: Optional[List[dict]] = Field(None, description="List of hub configurations")
    subnets: Optional[List[dict]] = Field(None, description="List of subnet configurations")

# Content Filtering Schema
class ContentFilteringSchema(BaseModel):
    allowedUrls: Optional[List[str]] = Field(None, description="List of allowed URLs")
    blockedUrls: Optional[List[str]] = Field(None, description="List of blocked URLs")
    blockedUrlPatterns: Optional[List[str]] = Field(None, description="List of blocked URL patterns")
    youtubeRestrictedForTeenagers: Optional[bool] = Field(None, description="Restrict YouTube for teenagers")
    youtubeRestrictedForMature: Optional[bool] = Field(None, description="Restrict YouTube for mature content")

# Traffic Shaping Schema
class TrafficShapingSchema(BaseModel):
    globalBandwidthLimits: Optional[dict] = Field(None, description="Global bandwidth limits")
    rules: Optional[List[dict]] = Field(None, description="Traffic shaping rules")

# Camera Sense Schema
class CameraSenseSchema(BaseModel):
    senseEnabled: Optional[bool] = Field(None, description="Whether camera sense is enabled")
    mqttBrokerId: Optional[str] = Field(None, description="MQTT broker ID")
    audioDetection: Optional[dict] = Field(None, description="Audio detection settings")

# Switch QoS Rule Schema
class SwitchQosRuleSchema(BaseModel):
    vlan: int = Field(..., description="VLAN ID")
    protocol: str = Field(..., description="Protocol (tcp, udp, any)")
    srcPort: int = Field(..., description="Source port")
    srcPortRange: Optional[str] = Field(None, description="Source port range")
    dstPort: Optional[int] = Field(None, description="Destination port")
    dstPortRange: Optional[str] = Field(None, description="Destination port range")
    dscp: Optional[int] = Field(None, description="DSCP value")

#######################
# ORGANIZATION TOOLS  #
#######################

# Get organizations
@mcp.tool()
async def get_organizations() -> str:
    """Get a list of organizations the user has access to"""
    organizations = await async_get_organizations()
    return json.dumps(organizations, indent=2)

# Get organization details
@mcp.tool()
async def get_organization_details(org_id: str = None) -> str:
    """Get details for a specific organization, defaults to the configured organization"""
    organization_id = org_id or MERAKI_ORG_ID
    org_details = await async_get_organization(organization_id)
    return json.dumps(org_details, indent=2)

# Get networks from Meraki
@mcp.tool()
async def get_networks(org_id: str = None) -> str:
    """Get a list of networks from Meraki"""
    organization_id = org_id or MERAKI_ORG_ID
    networks = await async_get_organization_networks(organization_id)
    return json.dumps(networks, indent=2)

# Get devices from Meraki
@mcp.tool()
async def get_devices(org_id: str = None) -> str:
    """Get a list of devices from Meraki"""
    organization_id = org_id or MERAKI_ORG_ID
    devices = await async_get_organization_devices(organization_id)
    return json.dumps(devices, indent=2)

# Create network in Meraki
@mcp.tool()
def create_network(name: str, tags: list[str], productTypes: list[str], org_id: str = None, copyFromNetworkId: str = None) -> str:
    """Create a new network in Meraki, optionally copying from another network."""
    blocked = _guard_write("createOrganizationNetwork")
    if blocked:
        return blocked
    organization_id = org_id or MERAKI_ORG_ID
    kwargs = {}
    if copyFromNetworkId:
        kwargs['copyFromNetworkId'] = copyFromNetworkId
    network = dashboard.organizations.createOrganizationNetwork(organization_id, name, productTypes, tags=tags, **kwargs)
    return json.dumps(network, indent=2)

# Delete network in Meraki
@mcp.tool()
def delete_network(network_id: str, confirm_destructive_action: bool = False) -> str:
    """Delete a network in Meraki."""
    blocked = _guard_write("deleteNetwork", confirm_destructive_action)
    if blocked:
        return blocked
    dashboard.networks.deleteNetwork(network_id)
    return f"Network {network_id} deleted"

# Get organization status
@mcp.tool()
def get_organization_status(org_id: str = None) -> str:
    """Get the status and health of an organization"""
    organization_id = org_id or MERAKI_ORG_ID
    status = dashboard.organizations.getOrganizationStatus(organization_id)
    return json.dumps(status, indent=2)

# Get organization inventory
@mcp.tool()
def get_organization_inventory(org_id: str = None) -> str:
    """Get the inventory for an organization"""
    organization_id = org_id or MERAKI_ORG_ID
    inventory = dashboard.organizations.getOrganizationInventoryDevices(organization_id)
    return json.dumps(inventory, indent=2)

# Get organization license state
@mcp.tool()
def get_organization_license(org_id: str = None) -> str:
    """Get the license state for an organization"""
    organization_id = org_id or MERAKI_ORG_ID
    license_state = dashboard.organizations.getOrganizationLicensesOverview(organization_id)
    return json.dumps(license_state, indent=2)

# Get organization configuration changes
@mcp.tool()
def get_organization_conf_change(org_id: str = None) -> str:
    """Get the org change state for an organization"""
    organization_id = org_id or MERAKI_ORG_ID
    org_config_changes = dashboard.organizations.getOrganizationConfigurationChanges(organization_id)
    return json.dumps(org_config_changes, indent=2)

#######################
# NETWORK TOOLS       #
#######################

# Get network details
@mcp.tool()
def get_network_details(network_id: str) -> str:
    """Get details for a specific network"""
    network = dashboard.networks.getNetwork(network_id)
    return json.dumps(network, indent=2)

# Get network devices
@mcp.tool()
def get_network_devices(network_id: str) -> str:
    """Get a list of devices in a specific network"""
    devices = dashboard.networks.getNetworkDevices(network_id)
    return json.dumps(devices, indent=2)

# Update network
@mcp.tool()
def update_network(network_id: str, update_data: NetworkUpdateSchema) -> str:
    """
    Update a network's properties using a schema-validated model

    Args:
        network_id: The ID of the network to update
        update_data: Network properties to update (name, timeZone, tags, enrollmentString, notes)
    """
    blocked = _guard_write("updateNetwork")
    if blocked:
        return blocked

    # Convert the Pydantic model to a dictionary and filter out None values
    update_dict = update_data.model_dump(exclude_none=True)

    result = dashboard.networks.updateNetwork(network_id, **update_dict)
    return json.dumps(result, indent=2)

# Get clients from Meraki
@mcp.tool()
def get_clients(network_id: str, timespan: int = 86400) -> str:
    """
    Get a list of clients from a specific Meraki network.

    Args:
        network_id (str): The ID of the Meraki network.
        timespan (int): The timespan in seconds to get clients (default: 24 hours)

    Returns:
        str: JSON-formatted list of clients.
    """
    clients = dashboard.networks.getNetworkClients(network_id, timespan=timespan)
    return json.dumps(clients, indent=2)

# Get client details
@mcp.tool()
def get_client_details(network_id: str, client_id: str) -> str:
    """Get details for a specific client in a network"""
    client = dashboard.networks.getNetworkClient(network_id, client_id)
    return json.dumps(client, indent=2)

# Get client usage history
@mcp.tool()
def get_client_usage(network_id: str, client_id: str) -> str:
    """Get the usage history for a client"""
    usage = dashboard.networks.getNetworkClientUsageHistory(network_id, client_id)
    return json.dumps(usage, indent=2)

# Get client policy from Meraki
@mcp.tool()
async def get_client_policy(network_id: str, client_id: str) -> str:
    """
    Get the policy for a specific client in a specific Meraki network.

    Args:
        network_id (str): The ID of the Meraki network.
        client_id (str): The ID (MAC address or client ID) of the client.

    Returns:
        str: JSON-formatted client policy.
    """
    policy = await asyncio.to_thread(
        dashboard.networks.getNetworkClientPolicy, network_id, client_id
    )
    return json.dumps(policy, indent=2)

# Update client policy
@mcp.tool()
def update_client_policy(network_id: str, client_id: str, device_policy: str, group_policy_id: str = None) -> str:
    """Update policy for a client"""
    blocked = _guard_write("updateNetworkClientPolicy")
    if blocked:
        return blocked
    kwargs = {'devicePolicy': device_policy}
    if group_policy_id:
        kwargs['groupPolicyId'] = group_policy_id

    result = dashboard.networks.updateNetworkClientPolicy(network_id, client_id, **kwargs)
    return json.dumps(result, indent=2)

# Get network traffic analysis
@mcp.tool()
def get_network_traffic(network_id: str, timespan: int = 86400) -> str:
    """Get traffic analysis data for a network"""
    traffic = dashboard.networks.getNetworkTraffic(network_id, timespan=timespan)
    return json.dumps(traffic, indent=2)

#######################
# DEVICE TOOLS        #
#######################

# Get device details
@mcp.tool()
async def get_device_details(serial: str) -> str:
    """Get details for a specific device by serial number"""
    device = await async_get_device(serial)
    return json.dumps(device, indent=2)

# Update device
@mcp.tool()
async def update_device(serial: str, device_settings: DeviceUpdateSchema) -> str:
    """
    Update a device in the Meraki organization using a schema-validated model

    Args:
        serial: The serial number of the device to update
        device_settings: Device properties to update (name, tags, lat, lng, address, notes, etc.)

    Returns:
        Confirmation of the update with the new settings
    """
    blocked = _guard_write("updateDevice")
    if blocked:
        return blocked

    # Convert the Pydantic model to a dictionary and filter out None values
    update_dict = device_settings.model_dump(exclude_none=True)

    await async_update_device(serial, **update_dict)

    # Get the updated device details to return
    updated_device = await async_get_device(serial)

    return json.dumps({
        "status": "success",
        "message": f"Device {serial} updated",
        "updated_settings": update_dict,
        "current_device": updated_device
    }, indent=2)

# Claim devices into the Meraki organization
@mcp.tool()
def claim_devices(network_id: str, serials: list[str]) -> str:
    """Claim one or more devices into a Meraki network"""
    blocked = _guard_write("claimNetworkDevices")
    if blocked:
        return blocked
    dashboard.networks.claimNetworkDevices(network_id, serials)
    return f"Devices {serials} claimed into network {network_id}"

# Remove device from network
@mcp.tool()
def remove_device(network_id: str, serial: str, confirm_destructive_action: bool = False) -> str:
    """Remove a device from a network"""
    blocked = _guard_write("removeNetworkDevices", confirm_destructive_action)
    if blocked:
        return blocked
    dashboard.networks.removeNetworkDevices(network_id, serial)
    return f"Device {serial} removed from network {network_id}"

# Reboot device
@mcp.tool()
def reboot_device(serial: str) -> str:
    """Reboot a device"""
    blocked = _guard_write("rebootDevice")
    if blocked:
        return blocked
    result = dashboard.devices.rebootDevice(serial)
    return json.dumps(result, indent=2)

# Get device clients
@mcp.tool()
def get_device_clients(serial: str, timespan: int = 86400) -> str:
    """Get clients connected to a specific device"""
    clients = dashboard.devices.getDeviceClients(serial, timespan=timespan)
    return json.dumps(clients, indent=2)

# Get device status
@mcp.tool()
def get_device_status(serial: str) -> str:
    """Get the current status of a device"""
    status = dashboard.devices.getDeviceStatuses(serial)
    return json.dumps(status, indent=2)

# Get device uplink status
@mcp.tool()
def get_device_uplink(serial: str) -> str:
    """Get the uplink status of a device"""
    uplink = dashboard.devices.getDeviceUplink(serial)
    return json.dumps(uplink, indent=2)

#######################
# WIRELESS TOOLS      #
#######################

# Get wireless SSIDs
@mcp.tool()
async def get_wireless_ssids(network_id: str) -> str:
    """Get wireless SSIDs for a network"""
    ssids = await async_get_wireless_ssids(network_id)
    return json.dumps(ssids, indent=2)

# Update wireless SSID
@mcp.tool()
async def update_wireless_ssid(network_id: str, ssid_number: str, ssid_settings: SsidUpdateSchema) -> str:
    """
    Update a wireless SSID with comprehensive schema validation

    Args:
        network_id: The ID of the network containing the SSID
        ssid_number: The number of the SSID to update
        ssid_settings: Comprehensive SSID settings following the Meraki schema

    Returns:
        The updated SSID configuration
    """
    blocked = _guard_write("updateNetworkWirelessSsid")
    if blocked:
        return blocked

    # Convert the Pydantic model to a dictionary and filter out None values
    update_dict = ssid_settings.model_dump(exclude_none=True)

    result = await async_update_wireless_ssid(network_id, ssid_number, **update_dict)
    return json.dumps(result, indent=2)

# Get wireless settings
@mcp.tool()
def get_wireless_settings(network_id: str) -> str:
    """Get wireless settings for a network"""
    settings = dashboard.wireless.getNetworkWirelessSettings(network_id)
    return json.dumps(settings, indent=2)



#######################
# SWITCH TOOLS        #
#######################

# Get switch ports
@mcp.tool()
def get_switch_ports(serial: str) -> str:
    """Get ports for a switch"""
    ports = dashboard.switch.getDeviceSwitchPorts(serial)
    return json.dumps(ports, indent=2)

# Update switch port
@mcp.tool()
def update_switch_port(serial: str, port_id: str, name: str = None, tags: list[str] = None, enabled: bool = None, vlan: int = None) -> str:
    """Update a switch port"""
    blocked = _guard_write("updateDeviceSwitchPort")
    if blocked:
        return blocked
    kwargs = _build_kwargs(name=name, tags=tags, enabled=enabled, vlan=vlan)
    result = dashboard.switch.updateDeviceSwitchPort(serial, port_id, **kwargs)
    return json.dumps(result, indent=2)

# Get switch VLAN settings
@mcp.tool()
def get_switch_vlans(network_id: str) -> str:
    """Get VLANs for a network"""
    vlans = dashboard.switch.getNetworkSwitchVlans(network_id)
    return json.dumps(vlans, indent=2)

# Create switch VLAN
@mcp.tool()
def create_switch_vlan(network_id: str, vlan_id: int, name: str, subnet: str = None, appliance_ip: str = None) -> str:
    """Create a switch VLAN"""
    blocked = _guard_write("createNetworkSwitchVlan")
    if blocked:
        return blocked
    kwargs = {}
    if subnet:
        kwargs['subnet'] = subnet
    if appliance_ip:
        kwargs['applianceIp'] = appliance_ip

    result = dashboard.switch.createNetworkSwitchVlan(network_id, vlan_id, name, **kwargs)
    return json.dumps(result, indent=2)

#######################
# APPLIANCE TOOLS     #
#######################

# Get security center
@mcp.tool()
def get_security_center(network_id: str) -> str:
    """Get security information for a network"""
    security = dashboard.appliance.getNetworkApplianceSecurityCenter(network_id)
    return json.dumps(security, indent=2)

# Get VPN status
@mcp.tool()
def get_vpn_status(network_id: str) -> str:
    """Get VPN status for a network"""
    vpn_status = dashboard.appliance.getNetworkApplianceVpnSiteToSiteVpn(network_id)
    return json.dumps(vpn_status, indent=2)

# Get firewall rules
@mcp.tool()
def get_firewall_rules(network_id: str) -> str:
    """Get firewall rules for a network"""
    rules = dashboard.appliance.getNetworkApplianceFirewallL3FirewallRules(network_id)
    return json.dumps(rules, indent=2)

# Update firewall rules
@mcp.tool()
def update_firewall_rules(network_id: str, rules: List[FirewallRule]) -> str:
    """
    Update firewall rules for a network using schema-validated models

    Args:
        network_id: The ID of the network
        rules: List of firewall rules following the Meraki schema

    Returns:
        The updated firewall rules configuration
    """
    blocked = _guard_write("updateNetworkApplianceFirewallL3FirewallRules")
    if blocked:
        return blocked

    # Convert the list of Pydantic models to a list of dictionaries
    rules_dict = [rule.model_dump(exclude_none=True) for rule in rules]

    result = dashboard.appliance.updateNetworkApplianceFirewallL3FirewallRules(network_id, rules=rules_dict)
    return json.dumps(result, indent=2)

#######################
# CAMERA TOOLS        #
#######################

# Get camera video settings
@mcp.tool()
def get_camera_video_settings(serial: str) -> str:
    """Get video settings for a camera"""
    settings = dashboard.camera.getDeviceCameraVideoSettings(serial)
    return json.dumps(settings, indent=2)

# Get camera quality and retention settings
@mcp.tool()
def get_camera_quality_settings(network_id: str) -> str:
    """Get quality and retention settings for cameras in a network"""
    settings = dashboard.camera.getNetworkCameraQualityRetentionProfiles(network_id)
    return json.dumps(settings, indent=2)

#######################
# ADVANCED ORGANIZATION TOOLS
#######################

# Get organization admins
@mcp.tool()
def get_organization_admins(org_id: str = None) -> str:
    """Get a list of organization admins"""
    organization_id = org_id or MERAKI_ORG_ID
    admins = dashboard.organizations.getOrganizationAdmins(organization_id)
    return json.dumps(admins, indent=2)

# Create organization admin
@mcp.tool()
def create_organization_admin(org_id: str, email: str, name: str, org_access: str, tags: list[str] = None, networks: list[dict] = None) -> str:
    """Create a new organization admin"""
    blocked = _guard_write("createOrganizationAdmin")
    if blocked:
        return blocked
    organization_id = org_id or MERAKI_ORG_ID
    kwargs = {
        'email': email,
        'name': name,
        'orgAccess': org_access
    }
    if tags:
        kwargs['tags'] = tags
    if networks:
        kwargs['networks'] = networks
    
    result = dashboard.organizations.createOrganizationAdmin(organization_id, **kwargs)
    return json.dumps(result, indent=2)

# Get organization API requests
@mcp.tool()
def get_organization_api_requests(org_id: str = None, timespan: int = 86400) -> str:
    """Get organization API request history"""
    organization_id = org_id or MERAKI_ORG_ID
    requests = dashboard.organizations.getOrganizationApiRequests(organization_id, timespan=timespan)
    return json.dumps(requests, indent=2)

# Get organization webhook logs
@mcp.tool()
def get_organization_webhook_logs(org_id: str = None, timespan: int = 86400) -> str:
    """Get organization webhook logs"""
    organization_id = org_id or MERAKI_ORG_ID
    logs = dashboard.organizations.getOrganizationWebhooksLogs(organization_id, timespan=timespan)
    return json.dumps(logs, indent=2)

#######################
# ENHANCED NETWORK MONITORING
#######################

# Get network events
@mcp.tool()
def get_network_events(network_id: str, timespan: int = 86400, per_page: int = 100) -> str:
    """Get network events history"""
    events = dashboard.networks.getNetworkEvents(network_id, timespan=timespan, perPage=per_page)
    return json.dumps(events, indent=2)

# Get network event types
@mcp.tool()
def get_network_event_types(network_id: str) -> str:
    """Get available network event types"""
    event_types = dashboard.networks.getNetworkEventsEventTypes(network_id)
    return json.dumps(event_types, indent=2)

# Get network alerts history
@mcp.tool()
def get_network_alerts_history(network_id: str, timespan: int = 86400) -> str:
    """Get network alerts history"""
    alerts = dashboard.networks.getNetworkAlertsHistory(network_id, timespan=timespan)
    return json.dumps(alerts, indent=2)

# Get network alerts settings
@mcp.tool()
def get_network_alerts_settings(network_id: str) -> str:
    """Get network alerts settings"""
    settings = dashboard.networks.getNetworkAlertsSettings(network_id)
    return json.dumps(settings, indent=2)

# Update network alerts settings
@mcp.tool()
def update_network_alerts_settings(network_id: str, defaultDestinations: dict = None, alerts: list[dict] = None) -> str:
    """Update network alerts settings"""
    blocked = _guard_write("updateNetworkAlertsSettings")
    if blocked:
        return blocked
    kwargs = {}
    if defaultDestinations:
        kwargs['defaultDestinations'] = defaultDestinations
    if alerts:
        kwargs['alerts'] = alerts
    
    result = dashboard.networks.updateNetworkAlertsSettings(network_id, **kwargs)
    return json.dumps(result, indent=2)

#######################
# LIVE DEVICE TOOLS
#######################

# Ping device
@mcp.tool()
def ping_device(serial: str, target_ip: str, count: int = 5) -> str:
    """Ping a device from another device"""
    blocked = _guard_write("createDeviceLiveToolsPing")
    if blocked:
        return blocked
    result = dashboard.devices.createDeviceLiveToolsPing(serial, target_ip, count=count)
    return json.dumps(result, indent=2)

# Get ping results
@mcp.tool()
def get_device_ping_results(serial: str, ping_id: str) -> str:
    """Get results from a device ping test"""
    result = dashboard.devices.getDeviceLiveToolsPing(serial, ping_id)
    return json.dumps(result, indent=2)

# Cable test device
@mcp.tool()
def cable_test_device(serial: str, ports: list[str]) -> str:
    """Run cable test on device ports"""
    blocked = _guard_write("createDeviceLiveToolsCableTest")
    if blocked:
        return blocked
    result = dashboard.devices.createDeviceLiveToolsCableTest(serial, ports)
    return json.dumps(result, indent=2)

# Get cable test results
@mcp.tool()
def get_device_cable_test_results(serial: str, cable_test_id: str) -> str:
    """Get results from a device cable test"""
    result = dashboard.devices.getDeviceLiveToolsCableTest(serial, cable_test_id)
    return json.dumps(result, indent=2)

# Blink device LEDs
@mcp.tool()
def blink_device_leds(serial: str, duration: int = 5) -> str:
    """Blink device LEDs for identification"""
    blocked = _guard_write("blinkDeviceLeds")
    if blocked:
        return blocked
    result = dashboard.devices.blinkDeviceLeds(serial, duration=duration)
    return json.dumps(result, indent=2)

# Wake on LAN
@mcp.tool()
def wake_on_lan_device(serial: str, mac: str) -> str:
    """Send wake-on-LAN packet to a device"""
    blocked = _guard_write("createDeviceLiveToolsWakeOnLan")
    if blocked:
        return blocked
    result = dashboard.devices.createDeviceLiveToolsWakeOnLan(serial, mac)
    return json.dumps(result, indent=2)

#######################
# ADVANCED WIRELESS TOOLS
#######################

# Get wireless RF profiles
@mcp.tool()
def get_wireless_rf_profiles(network_id: str) -> str:
    """Get wireless RF profiles for a network"""
    profiles = dashboard.wireless.getNetworkWirelessRfProfiles(network_id)
    return json.dumps(profiles, indent=2)

# Create wireless RF profile
@mcp.tool()
def create_wireless_rf_profile(network_id: str, name: str, band_selection_type: str, **kwargs) -> str:
    """Create a wireless RF profile"""
    blocked = _guard_write("createNetworkWirelessRfProfile")
    if blocked:
        return blocked
    result = dashboard.wireless.createNetworkWirelessRfProfile(network_id, name, bandSelectionType=band_selection_type, **kwargs)
    return json.dumps(result, indent=2)

# Get wireless channel utilization
@mcp.tool()
def get_wireless_channel_utilization(network_id: str, timespan: int = 86400) -> str:
    """Get wireless channel utilization history"""
    utilization = dashboard.wireless.getNetworkWirelessChannelUtilizationHistory(network_id, timespan=timespan)
    return json.dumps(utilization, indent=2)

# Get wireless signal quality
@mcp.tool()
def get_wireless_signal_quality(network_id: str, timespan: int = 86400) -> str:
    """Get wireless signal quality history"""
    quality = dashboard.wireless.getNetworkWirelessSignalQualityHistory(network_id, timespan=timespan)
    return json.dumps(quality, indent=2)

# Get wireless connection stats
@mcp.tool()
def get_wireless_connection_stats(network_id: str, timespan: int = 86400) -> str:
    """Get wireless connection statistics"""
    stats = dashboard.wireless.getNetworkWirelessConnectionStats(network_id, timespan=timespan)
    return json.dumps(stats, indent=2)

# Get wireless client connectivity events
@mcp.tool()
def get_wireless_client_connectivity_events(network_id: str, client_id: str, timespan: int = 86400) -> str:
    """Get wireless client connectivity events"""
    events = dashboard.wireless.getNetworkWirelessClientConnectivityEvents(network_id, client_id, timespan=timespan)
    return json.dumps(events, indent=2)

#######################
# ADVANCED SWITCH TOOLS
#######################

# Get switch port statuses
@mcp.tool()
def get_switch_port_statuses(serial: str) -> str:
    """Get switch port statuses"""
    statuses = dashboard.switch.getDeviceSwitchPortsStatuses(serial)
    return json.dumps(statuses, indent=2)

# Cycle switch ports
@mcp.tool()
def cycle_switch_ports(serial: str, ports: list[str]) -> str:
    """Cycle (restart) switch ports"""
    blocked = _guard_write("cycleDeviceSwitchPorts")
    if blocked:
        return blocked
    result = dashboard.switch.cycleDeviceSwitchPorts(serial, ports)
    return json.dumps(result, indent=2)

# Get switch access control lists
@mcp.tool()
def get_switch_access_control_lists(network_id: str) -> str:
    """Get switch access control lists"""
    acls = dashboard.switch.getNetworkSwitchAccessControlLists(network_id)
    return json.dumps(acls, indent=2)

# Update switch access control lists
@mcp.tool()
def update_switch_access_control_lists(network_id: str, rules: list[dict]) -> str:
    """Update switch access control lists"""
    blocked = _guard_write("updateNetworkSwitchAccessControlLists")
    if blocked:
        return blocked
    result = dashboard.switch.updateNetworkSwitchAccessControlLists(network_id, rules)
    return json.dumps(result, indent=2)

# Get switch QoS rules
@mcp.tool()
def get_switch_qos_rules(network_id: str) -> str:
    """Get switch QoS rules"""
    rules = dashboard.switch.getNetworkSwitchQosRules(network_id)
    return json.dumps(rules, indent=2)

# Create switch QoS rule
@mcp.tool()
def create_switch_qos_rule(network_id: str, vlan: int, protocol: str, src_port: int, src_port_range: str = None, dst_port: int = None, dst_port_range: str = None, dscp: int = None) -> str:
    """Create a switch QoS rule"""
    blocked = _guard_write("createNetworkSwitchQosRule")
    if blocked:
        return blocked
    kwargs = {
        'vlan': vlan,
        'protocol': protocol,
        'srcPort': src_port,
        **_build_kwargs(
            srcPortRange=src_port_range,
            dstPort=dst_port,
            dstPortRange=dst_port_range,
            dscp=dscp,
        )
    }
    result = dashboard.switch.createNetworkSwitchQosRule(network_id, **kwargs)
    return json.dumps(result, indent=2)

#######################
# ADVANCED APPLIANCE TOOLS
#######################

# Get appliance VPN site-to-site status
@mcp.tool()
def get_appliance_vpn_site_to_site(network_id: str) -> str:
    """Get appliance VPN site-to-site configuration"""
    vpn = dashboard.appliance.getNetworkApplianceVpnSiteToSiteVpn(network_id)
    return json.dumps(vpn, indent=2)

# Update appliance VPN site-to-site
@mcp.tool()
def update_appliance_vpn_site_to_site(network_id: str, mode: str, hubs: list[dict] = None, subnets: list[dict] = None) -> str:
    """Update appliance VPN site-to-site configuration"""
    blocked = _guard_write("updateNetworkApplianceVpnSiteToSiteVpn")
    if blocked:
        return blocked
    kwargs = {'mode': mode, **_build_kwargs(hubs=hubs, subnets=subnets)}
    result = dashboard.appliance.updateNetworkApplianceVpnSiteToSiteVpn(network_id, **kwargs)
    return json.dumps(result, indent=2)

# Get appliance content filtering
@mcp.tool()
def get_appliance_content_filtering(network_id: str) -> str:
    """Get appliance content filtering settings"""
    filtering = dashboard.appliance.getNetworkApplianceContentFiltering(network_id)
    return json.dumps(filtering, indent=2)

# Update appliance content filtering
@mcp.tool()
def update_appliance_content_filtering(network_id: str, allowed_urls: list[str] = None, blocked_urls: list[str] = None, blocked_url_patterns: list[str] = None, youtube_restricted_for_teenagers: bool = None, youtube_restricted_for_mature: bool = None) -> str:
    """Update appliance content filtering settings"""
    blocked = _guard_write("updateNetworkApplianceContentFiltering")
    if blocked:
        return blocked
    kwargs = {}
    if allowed_urls:
        kwargs['allowedUrls'] = allowed_urls
    if blocked_urls:
        kwargs['blockedUrls'] = blocked_urls
    if blocked_url_patterns:
        kwargs['blockedUrlPatterns'] = blocked_url_patterns
    if youtube_restricted_for_teenagers is not None:
        kwargs['youtubeRestrictedForTeenagers'] = youtube_restricted_for_teenagers
    if youtube_restricted_for_mature is not None:
        kwargs['youtubeRestrictedForMature'] = youtube_restricted_for_mature
    
    result = dashboard.appliance.updateNetworkApplianceContentFiltering(network_id, **kwargs)
    return json.dumps(result, indent=2)

# Get appliance security events
@mcp.tool()
def get_appliance_security_events(network_id: str, timespan: int = 86400) -> str:
    """Get appliance security events"""
    events = dashboard.appliance.getNetworkApplianceSecurityEvents(network_id, timespan=timespan)
    return json.dumps(events, indent=2)

# Get appliance traffic shaping
@mcp.tool()
def get_appliance_traffic_shaping(network_id: str) -> str:
    """Get appliance traffic shaping settings"""
    shaping = dashboard.appliance.getNetworkApplianceTrafficShaping(network_id)
    return json.dumps(shaping, indent=2)

# Update appliance traffic shaping
@mcp.tool()
def update_appliance_traffic_shaping(network_id: str, global_bandwidth_limits: dict = None) -> str:
    """Update appliance traffic shaping settings"""
    blocked = _guard_write("updateNetworkApplianceTrafficShaping")
    if blocked:
        return blocked
    kwargs = {}
    if global_bandwidth_limits:
        kwargs['globalBandwidthLimits'] = global_bandwidth_limits
    
    result = dashboard.appliance.updateNetworkApplianceTrafficShaping(network_id, **kwargs)
    return json.dumps(result, indent=2)

#######################
# CAMERA TOOLS
#######################

# Get camera analytics live
@mcp.tool()
def get_camera_analytics_live(serial: str) -> str:
    """Get live camera analytics"""
    analytics = dashboard.camera.getDeviceCameraAnalyticsLive(serial)
    return json.dumps(analytics, indent=2)

# Get camera analytics overview
@mcp.tool()
def get_camera_analytics_overview(serial: str, timespan: int = 86400) -> str:
    """Get camera analytics overview"""
    overview = dashboard.camera.getDeviceCameraAnalyticsOverview(serial, timespan=timespan)
    return json.dumps(overview, indent=2)

# Get camera analytics zones
@mcp.tool()
def get_camera_analytics_zones(serial: str) -> str:
    """Get camera analytics zones"""
    zones = dashboard.camera.getDeviceCameraAnalyticsZones(serial)
    return json.dumps(zones, indent=2)

# Generate camera snapshot
@mcp.tool()
def generate_camera_snapshot(serial: str, timestamp: str = None) -> str:
    """Generate a camera snapshot"""
    blocked = _guard_write("generateDeviceCameraSnapshot")
    if blocked:
        return blocked
    kwargs = {}
    if timestamp:
        kwargs['timestamp'] = timestamp
    
    result = dashboard.camera.generateDeviceCameraSnapshot(serial, **kwargs)
    return json.dumps(result, indent=2)

# Get camera sense
@mcp.tool()
def get_camera_sense(serial: str) -> str:
    """Get camera sense configuration"""
    sense = dashboard.camera.getDeviceCameraSense(serial)
    return json.dumps(sense, indent=2)

# Update camera sense
@mcp.tool()
def update_camera_sense(serial: str, sense_enabled: bool = None, mqtt_broker_id: str = None, audio_detection: dict = None) -> str:
    """Update camera sense configuration"""
    blocked = _guard_write("updateDeviceCameraSense")
    if blocked:
        return blocked
    kwargs = {}
    if sense_enabled is not None:
        kwargs['senseEnabled'] = sense_enabled
    if mqtt_broker_id:
        kwargs['mqttBrokerId'] = mqtt_broker_id
    if audio_detection:
        kwargs['audioDetection'] = audio_detection
    
    result = dashboard.camera.updateDeviceCameraSense(serial, **kwargs)
    return json.dumps(result, indent=2)

#######################
# NETWORK AUTOMATION TOOLS
#######################

# Create action batch
@mcp.tool()
def create_action_batch(org_id: str, actions: list[dict], confirmed: bool = True, synchronous: bool = False) -> str:
    """Create an action batch for bulk operations"""
    blocked = _guard_write("createOrganizationActionBatch")
    if blocked:
        return blocked
    organization_id = org_id or MERAKI_ORG_ID
    result = dashboard.organizations.createOrganizationActionBatch(organization_id, actions, confirmed=confirmed, synchronous=synchronous)
    return json.dumps(result, indent=2)

# Get action batch status
@mcp.tool()
def get_action_batch_status(org_id: str, batch_id: str) -> str:
    """Get action batch status"""
    organization_id = org_id or MERAKI_ORG_ID
    status = dashboard.organizations.getOrganizationActionBatch(organization_id, batch_id)
    return json.dumps(status, indent=2)

# Get action batches
@mcp.tool()
def get_action_batches(org_id: str = None) -> str:
    """Get all action batches for an organization"""
    organization_id = org_id or MERAKI_ORG_ID
    batches = dashboard.organizations.getOrganizationActionBatches(organization_id)
    return json.dumps(batches, indent=2)

# Define resources
#Add a dynamic greeting resource
@mcp.resource("greeting: //{name}")
def greeting(name: str) -> str:
    """Greet a user by name"""
    return f"Hello {name}!"

# Module-level ASGI app for external uvicorn invocation
app = mcp.streamable_http_app() if MCP_TRANSPORT in ("http", "streamable-http") else None

if __name__ == "__main__":
    transport = "streamable-http" if MCP_TRANSPORT == "http" else MCP_TRANSPORT
    print(f"Starting Meraki Magic MCP ({transport} transport)", file=sys.stderr)
    if transport in ("streamable-http", "sse"):
        print(f"Listening on {MCP_HOST}:{MCP_PORT}", file=sys.stderr)
    mcp.run(transport=transport)

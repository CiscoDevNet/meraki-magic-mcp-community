# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: MIT

import os
import sys
import json
import meraki
import asyncio
import functools
import inspect
import hashlib
import threading
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from dotenv import load_dotenv
from pathlib import Path
from meraki_mcp_config import (
    CONFIRM_DESTRUCTIVE_ACTION_PARAM,
    get_meraki_base_url,
    get_read_only_mode,
    guard_write_operation,
    is_read_only_operation,
    is_write_operation,
    pop_destructive_confirmation,
)

# Load environment variables from .env file
load_dotenv(Path(__file__).resolve().parent / ".env")

# Transport configuration
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio").lower()
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))

# Create an MCP server
mcp = FastMCP("Meraki Magic MCP - Full API", host=MCP_HOST, port=MCP_PORT)

# Configuration
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY")
MERAKI_ORG_ID = os.getenv("MERAKI_ORG_ID")
MERAKI_BASE_URL = get_meraki_base_url()

if not MERAKI_API_KEY:
    print("FATAL: MERAKI_API_KEY is not set. Add it to .env or the environment.", file=sys.stderr)
    sys.exit(1)

ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))  # 5 minutes default
READ_ONLY_MODE = get_read_only_mode()

# Response size management (new)
MAX_RESPONSE_TOKENS = int(os.getenv("MAX_RESPONSE_TOKENS", "5000"))  # Max tokens in response
MAX_PER_PAGE = int(os.getenv("MAX_PER_PAGE", "100"))  # Max items per page for paginated endpoints
ENABLE_FILE_CACHING = os.getenv("ENABLE_FILE_CACHING", "true").lower() == "true"
_SCRIPT_DIR = Path(__file__).resolve().parent
_raw_cache_dir = os.getenv("RESPONSE_CACHE_DIR", ".meraki_cache")
RESPONSE_CACHE_DIR = str(Path(_raw_cache_dir) if Path(_raw_cache_dir).is_absolute() else _SCRIPT_DIR / _raw_cache_dir)

# Create cache directory if it doesn't exist
if ENABLE_FILE_CACHING:
    Path(RESPONSE_CACHE_DIR).mkdir(exist_ok=True)

# Initialize Meraki API client with optimizations
dashboard = meraki.DashboardAPI(
    api_key=MERAKI_API_KEY,
    base_url=MERAKI_BASE_URL,
    suppress_logging=True,
    maximum_retries=3,  # Auto-retry on failures
    wait_on_rate_limit=True  # Auto-wait on rate limits instead of failing
)

###################
# CACHING SYSTEM
###################

class SimpleCache:
    """Simple in-memory cache with TTL. Thread-safe via threading.Lock."""
    def __init__(self):
        self._lock = threading.Lock()
        self.cache = {}
        self.timestamps = {}

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        with self._lock:
            if key in self.cache:
                if datetime.now() - self.timestamps[key] < timedelta(seconds=CACHE_TTL_SECONDS):
                    return self.cache[key]
                else:
                    # Expired, remove
                    del self.cache[key]
                    del self.timestamps[key]
            return None

    def set(self, key: str, value: Any):
        """Set cached value"""
        with self._lock:
            self.cache[key] = value
            self.timestamps[key] = datetime.now()

    def clear(self):
        """Clear all cache"""
        with self._lock:
            self.cache.clear()
            self.timestamps.clear()

    def invalidate(self, prefix: str):
        """Remove all cache entries whose key starts with the given prefix."""
        with self._lock:
            keys_to_delete = [k for k in self.cache if k.startswith(prefix)]
            for k in keys_to_delete:
                del self.cache[k]
                del self.timestamps[k]

    def stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "total_items": len(self.cache),
            "cache_enabled": ENABLE_CACHING,
            "ttl_seconds": CACHE_TTL_SECONDS
        }

cache = SimpleCache()

###################
# FILE CACHE UTILITIES
###################

def estimate_token_count(text: str) -> int:
    """Rough estimate of token count (4 chars ≈ 1 token)"""
    return len(text) // 4

def save_response_to_file(data: Any, section: str, method: str, params: Dict) -> str:
    """Save large response to a file and return the file path"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    param_hash = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]
    filename = f"{section}_{method}_{param_hash}_{timestamp}.json"
    filepath = os.path.join(RESPONSE_CACHE_DIR, filename)

    with open(filepath, 'w') as f:
        json.dump({
            "cached_at": timestamp,
            "section": section,
            "method": method,
            "parameters": params,
            "data": data
        }, f, indent=2)

    return filepath

def _validate_cache_filepath(filepath: str) -> str:
    """Resolve filepath and confirm it is inside RESPONSE_CACHE_DIR.
    Returns the resolved absolute path string.
    Raises ValueError if the path escapes the cache directory.
    """
    cache_root = Path(RESPONSE_CACHE_DIR).resolve()
    resolved = Path(filepath).resolve()
    if not str(resolved).startswith(str(cache_root) + os.sep) and resolved != cache_root:
        raise ValueError(
            f"filepath must be inside the cache directory ({cache_root})"
        )
    return str(resolved)

def load_response_from_file(filepath: str) -> Any:
    """Load cached response from file"""
    try:
        safe_filepath = _validate_cache_filepath(filepath)
        with open(safe_filepath, 'r') as f:
            cached = json.load(f)
            return cached.get('data')
    except ValueError:
        return None
    except Exception as e:
        return None

def create_truncated_response(data: Any, filepath: str, section: str, method: str, params: Dict) -> Dict:
    """Create a truncated response with metadata about the full cached result"""
    item_count = len(data) if isinstance(data, list) else 1
    preview_items = data[:3] if isinstance(data, list) and len(data) > 3 else data

    return {
        "_response_truncated": True,
        "_reason": f"Response too large (~{estimate_token_count(json.dumps(data))} tokens)",
        "_full_response_cached": filepath,
        "_total_items": item_count,
        "_showing": "preview" if isinstance(data, list) else "summary",
        "_preview": preview_items,
        "_hints": {
            "reduce_page_size": f"Reduce request: Use perPage parameter with value <= {MAX_PER_PAGE}",
            "access_via_mcp_paginated": f"get_cached_response(filepath='{filepath}', offset=0, limit=10) - Returns 10 items at a time",
            "access_via_cli_full": f"cat {filepath} | jq '.data' - View all data",
            "search_via_cli": f"cat {filepath} | jq '.data[] | select(.field == \"value\")' - Search/filter",
            "count_via_cli": f"cat {filepath} | jq '.data | length' - Count items",
            "recommendation": "For large datasets, command-line tools (jq, grep) are recommended over MCP tools"
        },
        "section": section,
        "method": method,
        "parameters": params
    }

def enforce_pagination_limits(params: Dict, method: str) -> Dict:
    """Enforce pagination limits on API parameters"""
    # Common pagination parameters
    pagination_params = ['perPage', 'per_page', 'pageSize', 'limit']

    for param in pagination_params:
        if param in params:
            original_value = params[param]
            if isinstance(original_value, int) and original_value > MAX_PER_PAGE:
                params[param] = MAX_PER_PAGE
                # Note: We'll add a warning in the response about this

    return params

###################
# ASYNC UTILITIES
###################

def to_async(func):
    """Convert a synchronous function to an asynchronous function"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)
    return wrapper

###################
# DYNAMIC TOOL GENERATION
###################

# SDK sections to expose
SDK_SECTIONS = [
    'organizations',
    'networks',
    'devices',
    'wireless',
    'switch',
    'appliance',
    'camera',
    'cellularGateway',
    'sensor',
    'sm',
    'insight',
    'licensing',
    'administered'
]

def create_cache_key(section: str, method: str, kwargs: Dict) -> str:
    """Create a cache key from method call.
    Format: '<section>::<md5hash>' so invalidate(section) clears all related entries.
    """
    sorted_kwargs = json.dumps(kwargs, sort_keys=True)
    key_hash = hashlib.md5(f"{section}_{method}_{sorted_kwargs}".encode()).hexdigest()
    return f"{section}::{key_hash}"

###################
# GENERIC API CALLER - Provides access to ALL 804+ endpoints
###################

def _call_meraki_method_internal(section: str, method: str, params: dict) -> str:
    """Internal helper to call Meraki API methods"""
    pagination_limited = False
    params = dict(params or {})
    confirm_destructive_action = (
        pop_destructive_confirmation(params)
        if CONFIRM_DESTRUCTIVE_ACTION_PARAM in params
        else False
    )
    original_params = params.copy()

    try:
        # Validate section
        if not hasattr(dashboard, section):
            return json.dumps({
                "error": f"Invalid section '{section}'",
                "available_sections": SDK_SECTIONS
            }, indent=2)

        section_obj = getattr(dashboard, section)

        # Validate method
        if not hasattr(section_obj, method):
            return json.dumps({
                "error": f"Method '{method}' not found in section '{section}'"
            }, indent=2)

        method_func = getattr(section_obj, method)

        if not callable(method_func):
            return json.dumps({"error": f"'{method}' is not callable"}, indent=2)

        # Determine operation type
        is_read = is_read_only_operation(method)
        is_write = is_write_operation(method)

        blocked = guard_write_operation(method, READ_ONLY_MODE, confirm_destructive_action)
        if blocked:
            return blocked

        # Auto-fill org ID if needed
        sig = inspect.signature(method_func)
        method_params = [p for p in sig.parameters.keys() if p != 'self']

        if 'organizationId' in method_params and 'organizationId' not in params and MERAKI_ORG_ID:
            params['organizationId'] = MERAKI_ORG_ID

        # Enforce pagination limits
        params_before = params.copy()
        params = enforce_pagination_limits(params, method)
        if params != params_before:
            pagination_limited = True

        # Check cache for read operations
        if ENABLE_CACHING and is_read:
            cache_key = create_cache_key(section, method, params)
            cached = cache.get(cache_key)
            if cached is not None:
                if isinstance(cached, dict):
                    cached['_from_cache'] = True
                return json.dumps(cached, indent=2)

        # Call the method
        result = method_func(**params)

        # Invalidate cached read results for this section after any write operation
        if ENABLE_CACHING and is_write:
            cache.invalidate(section)

        # Check response size and handle large responses
        result_json = json.dumps(result)
        estimated_tokens = estimate_token_count(result_json)

        if ENABLE_FILE_CACHING and estimated_tokens > MAX_RESPONSE_TOKENS:
            # Save full response to file
            filepath = save_response_to_file(result, section, method, original_params)

            # Create truncated response with metadata
            truncated_response = create_truncated_response(result, filepath, section, method, original_params)

            # Add pagination warning if limits were enforced
            if pagination_limited:
                truncated_response["_pagination_limited"] = True
                truncated_response["_pagination_message"] = f"Request modified: pagination limited to {MAX_PER_PAGE} items per page"

            # Cache the truncated response (not the full result)
            if ENABLE_CACHING and is_read:
                cache_key = create_cache_key(section, method, params)
                cache.set(cache_key, truncated_response)

            return json.dumps(truncated_response, indent=2)

        # Normal response (small enough)
        response_data = result
        if pagination_limited and isinstance(response_data, dict):
            response_data["_pagination_limited"] = True
            response_data["_pagination_message"] = f"Request modified: pagination limited to {MAX_PER_PAGE} items per page"

        # Cache read results
        if ENABLE_CACHING and is_read:
            cache_key = create_cache_key(section, method, params)
            cache.set(cache_key, response_data)

        return json.dumps(response_data, indent=2)

    except meraki.exceptions.APIError as e:
        return json.dumps({
            "error": "Meraki API Error",
            "message": str(e),
            "status": getattr(e, 'status', 'unknown')
        }, indent=2)
    except TypeError as e:
        return json.dumps({
            "error": "Invalid parameters",
            "message": str(e),
            "hint": f"Use get_method_info(section='{section}', method='{method}') for parameter details"
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "type": type(e).__name__
        }, indent=2)

async def call_meraki_method(section: str, method: str, **params) -> str:
    """Internal async wrapper for pre-registered tools"""
    return await to_async(_call_meraki_method_internal)(section, method, params)

@mcp.tool()
async def call_meraki_api(
    section: str,
    method: str,
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        json_schema_extra={
            'type': 'object',
            'properties': {},
            'additionalProperties': True
        }
    )
) -> str:
    """
    Call any Meraki API method - provides access to all 804+ endpoints

    Args:
        section: SDK section (organizations, networks, wireless, switch, appliance, camera, devices, sensor, sm, etc.)
        method: Method name (e.g., getOrganizationAdmins, updateNetworkWirelessSsid, getNetworkApplianceFirewallL3FirewallRules)
        parameters: Dict of parameters (e.g., {"networkId": "L_123", "name": "MySSID"})

    Examples:
        call_meraki_api(section="organizations", method="getOrganizationAdmins", parameters={"organizationId": "123456"})
        call_meraki_api(section="wireless", method="updateNetworkWirelessSsid", parameters={"networkId": "L_123", "number": "0", "name": "NewSSID", "enabled": True})
        call_meraki_api(section="appliance", method="getNetworkApplianceFirewallL3FirewallRules", parameters={"networkId": "L_123"})
    """
    # Call internal method (parameters is always a dict due to default_factory)
    return await to_async(_call_meraki_method_internal)(section, method, parameters)

###################
# MOST COMMON TOOLS (Pre-registered for convenience)
###################

@mcp.tool()
async def getOrganizations() -> str:
    """Get all organizations"""
    return await call_meraki_method("organizations", "getOrganizations")

@mcp.tool()
async def getOrganizationAdmins(organizationId: str = None) -> str:
    """Get organization administrators"""
    params = {}
    if organizationId:
        params['organizationId'] = organizationId
    return await call_meraki_method("organizations", "getOrganizationAdmins", **params)

@mcp.tool()
async def getOrganizationNetworks(organizationId: str = None) -> str:
    """Get organization networks"""
    params = {}
    if organizationId:
        params['organizationId'] = organizationId
    return await call_meraki_method("organizations", "getOrganizationNetworks", **params)

@mcp.tool()
async def getOrganizationDevices(organizationId: str = None) -> str:
    """Get organization devices"""
    params = {}
    if organizationId:
        params['organizationId'] = organizationId
    return await call_meraki_method("organizations", "getOrganizationDevices", **params)

@mcp.tool()
async def getNetwork(networkId: str) -> str:
    """Get network details"""
    return await call_meraki_method("networks", "getNetwork", networkId=networkId)

@mcp.tool()
async def getNetworkClients(networkId: str, timespan: int = 86400) -> str:
    """Get network clients"""
    return await call_meraki_method("networks", "getNetworkClients", networkId=networkId, timespan=timespan)

@mcp.tool()
async def getNetworkEvents(networkId: str, productType: str = None, perPage: int = 100) -> str:
    """Get network events"""
    params = {"networkId": networkId, "perPage": perPage}
    if productType:
        params['productType'] = productType
    return await call_meraki_method("networks", "getNetworkEvents", **params)

@mcp.tool()
async def getNetworkDevices(networkId: str) -> str:
    """Get network devices"""
    return await call_meraki_method("networks", "getNetworkDevices", networkId=networkId)

@mcp.tool()
async def getDevice(serial: str) -> str:
    """Get device by serial"""
    return await call_meraki_method("devices", "getDevice", serial=serial)

@mcp.tool()
async def getNetworkWirelessSsids(networkId: str) -> str:
    """Get wireless SSIDs"""
    return await call_meraki_method("wireless", "getNetworkWirelessSsids", networkId=networkId)

# Switch Tools
@mcp.tool()
async def getDeviceSwitchPorts(serial: str) -> str:
    """Get switch ports for a device"""
    return await call_meraki_method("switch", "getDeviceSwitchPorts", serial=serial)

@mcp.tool()
async def updateDeviceSwitchPort(
    serial: str,
    portId: str,
    name: str = None,
    enabled: bool = None,
    poeEnabled: bool = None,
    type: str = None,
    vlan: int = None,
    voiceVlan: int = None,
) -> str:
    """Update switch port configuration. For the full parameter set use call_meraki_api."""
    params = {
        "serial": serial,
        "portId": portId,
        **{k: v for k, v in dict(
            name=name, enabled=enabled, poeEnabled=poeEnabled,
            type=type, vlan=vlan, voiceVlan=voiceVlan
        ).items() if v is not None}
    }
    return await call_meraki_method("switch", "updateDeviceSwitchPort", **params)

print("Registered hybrid MCP: 12 common tools + call_meraki_api for full API access (804+ methods)", file=sys.stderr)

###################
# METHOD INDEX (built once at startup - SDK structure is static)
###################

def _build_method_index() -> Dict:
    """Build a complete index of all callable SDK methods, grouped by section."""
    index = {}
    for section_name in SDK_SECTIONS:
        if not hasattr(dashboard, section_name):
            continue
        section_obj = getattr(dashboard, section_name)
        methods = sorted(
            m for m in dir(section_obj)
            if not m.startswith('_') and callable(getattr(section_obj, m))
        )
        if methods:
            index[section_name] = methods
    return index

_METHOD_INDEX = _build_method_index()

###################
# DISCOVERY TOOLS
###################

@mcp.tool()
async def list_all_methods(section: str = None) -> str:
    """
    List all available Meraki API methods

    Args:
        section: Optional section filter (organizations, networks, wireless, switch, appliance, etc.)
    """
    if section:
        if section not in _METHOD_INDEX:
            return json.dumps({
                "error": f"Section '{section}' not found",
                "available_sections": list(_METHOD_INDEX.keys())
            }, indent=2)
        sections_to_show = {section: _METHOD_INDEX[section]}
    else:
        sections_to_show = _METHOD_INDEX

    return json.dumps({
        "sections": sections_to_show,
        "total_methods": sum(len(v) for v in sections_to_show.values()),
        "usage": "Use call_meraki_api(section='...', method='...', parameters='{...}') to call any method"
    }, indent=2)

@mcp.tool()
async def search_methods(keyword: str) -> str:
    """
    Search for Meraki API methods by keyword

    Args:
        keyword: Search term (e.g., 'admin', 'firewall', 'ssid', 'event')
    """
    keyword_lower = keyword.lower()
    results = {
        section: [m for m in methods if keyword_lower in m.lower()]
        for section, methods in _METHOD_INDEX.items()
    }
    results = {k: v for k, v in results.items() if v}

    return json.dumps({
        "keyword": keyword,
        "results": results,
        "total_matches": sum(len(v) for v in results.values()),
        "usage": "Use call_meraki_api(section='...', method='...', parameters='{...}')"
    }, indent=2)

@mcp.tool()
async def get_method_info(section: str, method: str) -> str:
    """
    Get detailed parameter information for a method

    Args:
        section: SDK section (e.g., 'organizations', 'networks')
        method: Method name (e.g., 'getOrganizationAdmins')
    """
    try:
        if not hasattr(dashboard, section):
            return json.dumps({
                "error": f"Section '{section}' not found",
                "available_sections": SDK_SECTIONS
            }, indent=2)

        section_obj = getattr(dashboard, section)

        if not hasattr(section_obj, method):
            return json.dumps({
                "error": f"Method '{method}' not found in '{section}'"
            }, indent=2)

        method_func = getattr(section_obj, method)
        sig = inspect.signature(method_func)

        params = {}
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            params[param_name] = {
                "required": param.default == inspect.Parameter.empty,
                "default": None if param.default == inspect.Parameter.empty else str(param.default)
            }

        return json.dumps({
            "section": section,
            "method": method,
            "parameters": params,
            "docstring": inspect.getdoc(method_func),
            "usage_example": f'call_meraki_api(section="{section}", method="{method}", parameters=\'{{...}}\')'
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def cache_stats() -> str:
    """Get cache statistics and configuration"""
    stats = cache.stats()
    stats['read_only_mode'] = READ_ONLY_MODE
    return json.dumps(stats, indent=2)

@mcp.tool()
async def cache_clear() -> str:
    """Clear all cached data"""
    cache.clear()
    return json.dumps({
        "status": "success",
        "message": "Cache cleared successfully"
    }, indent=2)

@mcp.tool()
async def get_mcp_config() -> str:
    """Get MCP configuration"""
    return json.dumps({
        "mode": "hybrid",
        "description": "12 pre-registered tools + call_meraki_api for full API access",
        "pre_registered_tools": ["getOrganizations", "getOrganizationAdmins", "getOrganizationNetworks",
                                  "getOrganizationDevices", "getNetwork", "getNetworkClients",
                                  "getNetworkEvents", "getNetworkDevices", "getDevice",
                                  "getNetworkWirelessSsids", "getDeviceSwitchPorts", "updateDeviceSwitchPort"],
        "generic_caller": "call_meraki_api - access all 804+ methods",
        "total_available_methods": "804+",
        "read_only_mode": READ_ONLY_MODE,
        "meraki_base_url": MERAKI_BASE_URL,
        "caching_enabled": ENABLE_CACHING,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "file_caching_enabled": ENABLE_FILE_CACHING,
        "max_response_tokens": MAX_RESPONSE_TOKENS,
        "max_per_page": MAX_PER_PAGE,
        "response_cache_dir": RESPONSE_CACHE_DIR,
        "organization_id_configured": bool(MERAKI_ORG_ID),
        "api_key_configured": bool(MERAKI_API_KEY)
    }, indent=2)

@mcp.tool()
async def get_cached_response(filepath: str, offset: int = 0, limit: int = 10) -> str:
    """
    Retrieve a paginated slice of a cached response from a file

    IMPORTANT: This tool returns paginated data to avoid context overflow.
    For full data access, use command-line tools: cat <filepath> | jq

    Args:
        filepath: Path to the cached response file (from _full_response_cached field)
        offset: Starting index for pagination (default: 0)
        limit: Maximum number of items to return (default: 10, max: 100)

    Examples:
        get_cached_response(filepath="...", offset=0, limit=10)   # First 10 items
        get_cached_response(filepath="...", offset=10, limit=10)  # Next 10 items
        get_cached_response(filepath="...", offset=0, limit=100)  # First 100 items
    """
    try:
        # Enforce maximum limit
        if limit > 100:
            limit = 100

        # Validate path is inside cache directory before any file access
        try:
            _validate_cache_filepath(filepath)
        except ValueError as e:
            return json.dumps({
                "error": "Invalid filepath",
                "message": str(e)
            }, indent=2)

        data = load_response_from_file(filepath)
        if data is None:
            return json.dumps({
                "error": "Could not load cached response",
                "filepath": filepath
            }, indent=2)

        # Handle list pagination
        if isinstance(data, list):
            total_items = len(data)
            paginated_data = data[offset:offset + limit]

            return json.dumps({
                "_paginated": True,
                "_total_items": total_items,
                "_offset": offset,
                "_limit": limit,
                "_returned_items": len(paginated_data),
                "_has_more": (offset + limit) < total_items,
                "_next_offset": offset + limit if (offset + limit) < total_items else None,
                "_hints": {
                    "next_page": f"get_cached_response(filepath='{filepath}', offset={offset + limit}, limit={limit})" if (offset + limit) < total_items else "No more pages",
                    "full_data_cli": f"cat {filepath} | jq '.data'",
                    "search_cli": f"cat {filepath} | jq '.data[] | select(.field == \"value\")'",
                    "count_cli": f"cat {filepath} | jq '.data | length'"
                },
                "data": paginated_data
            }, indent=2)
        else:
            # Non-list data - check size and potentially truncate
            data_json = json.dumps(data)
            estimated_tokens = estimate_token_count(data_json)

            if estimated_tokens > MAX_RESPONSE_TOKENS:
                return json.dumps({
                    "_warning": "Response too large for MCP context",
                    "_estimated_tokens": estimated_tokens,
                    "_max_allowed_tokens": MAX_RESPONSE_TOKENS,
                    "_recommendation": "Use command-line tools to access this data",
                    "_hints": {
                        "view_all": f"cat {filepath} | jq '.data'",
                        "pretty_print": f"cat {filepath} | jq '.'",
                        "extract_field": f"cat {filepath} | jq '.data.fieldName'",
                        "search": f"grep 'search-term' {filepath}"
                    },
                    "_preview": str(data)[:500] + "..." if len(str(data)) > 500 else data
                }, indent=2)

            return json.dumps(data, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "filepath": filepath
        }, indent=2)

@mcp.tool()
async def list_cached_responses() -> str:
    """List all cached response files"""
    try:
        if not os.path.exists(RESPONSE_CACHE_DIR):
            return json.dumps({
                "message": "No cache directory found",
                "cache_dir": RESPONSE_CACHE_DIR
            }, indent=2)

        files = []
        for filename in os.listdir(RESPONSE_CACHE_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(RESPONSE_CACHE_DIR, filename)
                stat = os.stat(filepath)
                files.append({
                    "filename": filename,
                    "filepath": filepath,
                    "size_bytes": stat.st_size,
                    "size_kb": round(stat.st_size / 1024, 2),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        files.sort(key=lambda x: x['modified'], reverse=True)

        return json.dumps({
            "cache_dir": RESPONSE_CACHE_DIR,
            "total_files": len(files),
            "files": files,
            "hint": "Use get_cached_response(filepath='...') to retrieve full data"
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": str(e)
        }, indent=2)

@mcp.tool()
async def clear_cached_files(older_than_hours: int = 24) -> str:
    """
    Clear cached response files older than specified hours

    Args:
        older_than_hours: Delete files older than this many hours (default: 24)
    """
    try:
        if not os.path.exists(RESPONSE_CACHE_DIR):
            return json.dumps({
                "message": "No cache directory found",
                "cache_dir": RESPONSE_CACHE_DIR
            }, indent=2)

        now = datetime.now()
        deleted = []
        kept = []

        for filename in os.listdir(RESPONSE_CACHE_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(RESPONSE_CACHE_DIR, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                age_hours = (now - file_time).total_seconds() / 3600

                if age_hours > older_than_hours:
                    os.remove(filepath)
                    deleted.append({
                        "filename": filename,
                        "age_hours": round(age_hours, 2)
                    })
                else:
                    kept.append({
                        "filename": filename,
                        "age_hours": round(age_hours, 2)
                    })

        return json.dumps({
            "cache_dir": RESPONSE_CACHE_DIR,
            "deleted_count": len(deleted),
            "kept_count": len(kept),
            "deleted_files": deleted,
            "kept_files": kept
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "error": str(e)
        }, indent=2)

# Module-level ASGI app for external uvicorn invocation
app = mcp.streamable_http_app() if MCP_TRANSPORT in ("http", "streamable-http") else None

if __name__ == "__main__":
    transport = "streamable-http" if MCP_TRANSPORT == "http" else MCP_TRANSPORT
    print(f"Starting Meraki Magic MCP - Full API ({transport} transport)", file=sys.stderr)
    if transport in ("streamable-http", "sse"):
        print(f"Listening on {MCP_HOST}:{MCP_PORT}", file=sys.stderr)
    mcp.run(transport=transport)

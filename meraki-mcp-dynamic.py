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
import time
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from meraki_mcp_config import (
    CONFIRM_DESTRUCTIVE_ACTION_PARAM,
    get_meraki_base_url,
    get_meraki_caller,
    get_read_only_mode,
    guard_write_operation,
    is_read_only_operation,
    is_write_operation,
    pop_destructive_confirmation,
    to_json,
)

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
MERAKI_CALLER = get_meraki_caller()

if not MERAKI_API_KEY:
    print(
        "FATAL: MERAKI_API_KEY is not set. Set it in the MCP client env block or the process environment.",
        file=sys.stderr,
    )
    sys.exit(1)

ENABLE_CACHING = os.getenv("ENABLE_CACHING", "true").lower() == "true"
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))  # 5 minutes default
CACHE_MAX_ITEMS = int(os.getenv("CACHE_MAX_ITEMS", "500"))  # In-memory entries; 0 = unlimited
READ_ONLY_MODE = get_read_only_mode()

# Response size management (new)
MAX_RESPONSE_TOKENS = int(os.getenv("MAX_RESPONSE_TOKENS", "5000"))  # Max tokens in response
MAX_PER_PAGE = int(os.getenv("MAX_PER_PAGE", "100"))  # Max items per page for paginated endpoints
ENABLE_FILE_CACHING = os.getenv("ENABLE_FILE_CACHING", "true").lower() == "true"
_SCRIPT_DIR = Path(__file__).resolve().parent
_raw_cache_dir = os.getenv("RESPONSE_CACHE_DIR", ".meraki_cache")
RESPONSE_CACHE_DIR = str(Path(_raw_cache_dir) if Path(_raw_cache_dir).is_absolute() else _SCRIPT_DIR / _raw_cache_dir)

# Retention for cached response files; 0 disables the respective limit
RESPONSE_CACHE_MAX_AGE_HOURS = float(os.getenv("RESPONSE_CACHE_MAX_AGE_HOURS", "24"))
RESPONSE_CACHE_MAX_MB = float(os.getenv("RESPONSE_CACHE_MAX_MB", "100"))

# Size cap for the "_preview" of a truncated response (about half the token budget)
PREVIEW_BUDGET_CHARS = MAX_RESPONSE_TOKENS * 2
PREVIEW_MAX_ITEMS = 3

# Create cache directory if it doesn't exist
# Cached responses can contain sensitive configuration, so keep the directory private
if ENABLE_FILE_CACHING:
    Path(RESPONSE_CACHE_DIR).mkdir(mode=0o700, exist_ok=True)

# Initialize Meraki API client with optimizations
dashboard = meraki.DashboardAPI(
    api_key=MERAKI_API_KEY,
    base_url=MERAKI_BASE_URL,
    caller=MERAKI_CALLER,
    suppress_logging=True,
    maximum_retries=3,  # Auto-retry on failures
    wait_on_rate_limit=True  # Auto-wait on rate limits instead of failing
)

###################
# CACHING SYSTEM
###################

class SimpleCache:
    """In-memory cache with TTL and a size cap. Thread-safe via threading.Lock.

    Entries expire CACHE_TTL_SECONDS after they are stored. Expired entries are purged
    whenever a value is stored, and when the cache still exceeds CACHE_MAX_ITEMS the
    oldest entries are evicted, so memory use stays bounded on long-running servers.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.cache = {}  # insertion-ordered: oldest entry first
        self.timestamps = {}

    def _is_expired(self, key: str, now: float) -> bool:
        return now - self.timestamps[key] >= CACHE_TTL_SECONDS

    def _delete(self, key: str):
        del self.cache[key]
        del self.timestamps[key]

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        with self._lock:
            if key in self.cache:
                if not self._is_expired(key, time.monotonic()):
                    return self.cache[key]
                self._delete(key)
            return None

    def set(self, key: str, value: Any):
        """Set cached value, purging expired entries and enforcing the size cap"""
        with self._lock:
            now = time.monotonic()
            # Re-insert so the entry moves to the newest position
            if key in self.cache:
                self._delete(key)
            for stale in [k for k in self.cache if self._is_expired(k, now)]:
                self._delete(stale)
            self.cache[key] = value
            self.timestamps[key] = now
            if CACHE_MAX_ITEMS > 0:
                while len(self.cache) > CACHE_MAX_ITEMS:
                    self._delete(next(iter(self.cache)))

    def clear(self):
        """Clear all cache"""
        with self._lock:
            self.cache.clear()
            self.timestamps.clear()

    def invalidate(self, prefix: str):
        """Remove all cache entries whose key starts with the given prefix."""
        with self._lock:
            for k in [k for k in self.cache if k.startswith(prefix)]:
                self._delete(k)

    def stats(self) -> Dict:
        """Get cache statistics"""
        with self._lock:
            total_items = len(self.cache)
        return {
            "total_items": total_items,
            "max_items": CACHE_MAX_ITEMS,
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

    # Owner-only permissions: responses can include secrets such as SSID pre-shared keys
    fd = os.open(filepath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump({
            "cached_at": timestamp,
            "section": section,
            "method": method,
            "parameters": params,
            "data": data
        }, f, indent=2)

    prune_response_cache(keep=filepath)
    return filepath

def prune_response_cache(keep: Optional[str] = None) -> Dict[str, int]:
    """Delete cached response files beyond the configured retention.

    Removes files older than RESPONSE_CACHE_MAX_AGE_HOURS, then the oldest remaining
    files until the directory is within RESPONSE_CACHE_MAX_MB. The file named by
    `keep` (the response just written) is never removed. Runs at startup and after
    each write so the cache directory cannot grow without bound.
    """
    removed = {"expired": 0, "over_quota": 0}
    try:
        entries = []
        for entry in os.scandir(RESPONSE_CACHE_DIR):
            if entry.is_file(follow_symlinks=False) and entry.name.endswith('.json'):
                stat = entry.stat(follow_symlinks=False)
                entries.append((stat.st_mtime, stat.st_size, entry.path))
    except OSError:
        return removed

    def remove(path: str, reason: str) -> bool:
        if keep is not None and os.path.abspath(path) == os.path.abspath(keep):
            return False
        try:
            os.remove(path)
        except OSError:
            return False
        removed[reason] += 1
        return True

    entries.sort()  # oldest first
    remaining = []
    cutoff = time.time() - RESPONSE_CACHE_MAX_AGE_HOURS * 3600
    for mtime, size, path in entries:
        if RESPONSE_CACHE_MAX_AGE_HOURS > 0 and mtime < cutoff and remove(path, "expired"):
            continue
        remaining.append((mtime, size, path))

    if RESPONSE_CACHE_MAX_MB > 0:
        max_bytes = RESPONSE_CACHE_MAX_MB * 1024 * 1024
        total = sum(size for _, size, _ in remaining)
        for mtime, size, path in remaining:
            if total <= max_bytes:
                break
            if remove(path, "over_quota"):
                total -= size

    return removed

if ENABLE_FILE_CACHING:
    prune_response_cache()

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

def _truncate_value(value: Any, budget_chars: int) -> Any:
    """Return value unchanged if it serializes within budget_chars, else a short stand-in."""
    if len(json.dumps(value)) <= budget_chars:
        return value
    if isinstance(value, list):
        return f"<list of {len(value)} items - see cached file>"
    if isinstance(value, dict):
        return f"<object with {len(value)} keys - see cached file>"
    text = value if isinstance(value, str) else str(value)
    return text[:max(budget_chars - 20, 0)] + "... <truncated>"

def build_preview(data: Any, budget_chars: Optional[int] = None) -> Any:
    """Build a preview of data that serializes to roughly budget_chars at most.

    Lists keep up to PREVIEW_MAX_ITEMS leading items, dicts keep their leading keys;
    in both cases oversized values are replaced by a short stand-in so the preview
    stays bounded regardless of the shape of the response.
    """
    budget = PREVIEW_BUDGET_CHARS if budget_chars is None else budget_chars

    if isinstance(data, list):
        items = data[:PREVIEW_MAX_ITEMS]
        per_item = budget // max(len(items), 1)
        return [
            build_preview(item, per_item) if isinstance(item, dict) else _truncate_value(item, per_item)
            for item in items
        ]

    if isinstance(data, dict):
        if len(json.dumps(data)) <= budget:
            return data
        preview = {}
        remaining = max(budget - 40, 0)  # reserve room for the braces and "_omitted_keys"
        per_value = max(budget // PREVIEW_MAX_ITEMS, 1)
        for index, (key, value) in enumerate(data.items()):
            entry = _truncate_value(value, min(per_value, remaining))
            cost = len(json.dumps(key)) + len(json.dumps(entry)) + 2
            if cost > remaining:
                preview["_omitted_keys"] = len(data) - index
                break
            preview[key] = entry
            remaining -= cost
        return preview

    return _truncate_value(data, budget)

def create_truncated_response(data: Any, filepath: str, section: str, method: str, params: Dict) -> Dict:
    """Create a truncated response with metadata about the full cached result"""
    item_count = len(data) if isinstance(data, list) else 1
    preview = build_preview(data)

    response = {
        "_response_truncated": True,
        "_reason": f"Response too large (~{estimate_token_count(json.dumps(data))} tokens)",
        "_full_response_cached": filepath,
        "_total_items": item_count,
        "_showing": "preview" if isinstance(data, list) else "summary",
        "_preview": preview,
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
    if isinstance(data, dict):
        response["_keys"] = _truncate_value(list(data.keys()), PREVIEW_BUDGET_CHARS // 4)
    return response

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
    'campusGateway',
    'sensor',
    'sm',
    'insight',
    'licensing',
    'administered',
    'spaces',
    'wirelessController',
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

def _resolve_sdk_method(section: str, method: str):
    """Look up a public SDK method in an exposed section.

    Returns (callable, None) on success or (None, error_dict). Only sections listed in
    SDK_SECTIONS and public methods are reachable, so internals of the dashboard client
    (e.g. its raw HTTP session) cannot be invoked and bypass the write guards.
    """
    if not isinstance(section, str) or section not in SDK_SECTIONS or not hasattr(dashboard, section):
        return None, {
            "error": f"Invalid section '{section}'",
            "available_sections": [s for s in SDK_SECTIONS if hasattr(dashboard, s)]
        }

    section_obj = getattr(dashboard, section)

    if not isinstance(method, str) or method.startswith('_') or not hasattr(section_obj, method):
        return None, {
            "error": f"Method '{method}' not found in section '{section}'",
            "hint": "Use search_methods(keyword='...') or list_all_methods(section='...') to find valid methods"
        }

    method_func = getattr(section_obj, method)

    if not callable(method_func):
        return None, {"error": f"'{method}' is not callable"}

    return method_func, None

def _missing_required_params(section: str, method: str, params: dict) -> list:
    """Return the SDK method's required parameter names that are absent from params."""
    try:
        method_func, lookup_error = _resolve_sdk_method(section, method)
        if lookup_error:
            return []
        sig = inspect.signature(method_func)
    except (TypeError, ValueError):
        return []
    return [
        name for name, p in sig.parameters.items()
        if name != 'self'
        and p.default is inspect.Parameter.empty
        and p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        and name not in params
    ]

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
        # Validate section and method (exposed sections and public methods only)
        method_func, lookup_error = _resolve_sdk_method(section, method)
        if lookup_error:
            return to_json(lookup_error)

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
                # Annotate a copy so the stored entry is never modified
                if isinstance(cached, dict):
                    cached = {**cached, '_from_cache': True}
                return to_json(cached)

        # Call the method
        result = method_func(**params)

        # Invalidate cached read results for this section after any write operation
        if ENABLE_CACHING and is_write:
            cache.invalidate(section)

        # Check response size and handle large responses
        # Measure the same compact serialization that is returned to the client
        result_json = to_json(result)
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

            return to_json(truncated_response)

        # Normal response (small enough)
        response_data = result
        if pagination_limited and isinstance(response_data, dict):
            # Annotate a copy so the SDK's result object is never modified
            response_data = {
                **response_data,
                "_pagination_limited": True,
                "_pagination_message": f"Request modified: pagination limited to {MAX_PER_PAGE} items per page",
            }

        # Cache read results
        if ENABLE_CACHING and is_read:
            cache_key = create_cache_key(section, method, params)
            cache.set(cache_key, response_data)

        # Reuse the serialization from the size check unless the response was annotated
        return result_json if response_data is result else to_json(response_data)

    except meraki.exceptions.APIError as e:
        return to_json({
            "error": "Meraki API Error",
            "message": str(e),
            "status": getattr(e, 'status', 'unknown')
        })
    except TypeError as e:
        response = {
            "error": "Invalid parameters",
            "message": str(e),
            "hint": f"Use get_method_info(section='{section}', method='{method}') for parameter details"
        }
        missing = _missing_required_params(section, method, params)
        if missing:
            example = {name: "..." for name in missing}
            response["missing_required_parameters"] = missing
            response["received_parameters"] = sorted(params)
            response["hint"] = (
                "Pass method arguments inside the 'parameters' object; arguments given next to "
                "'section' and 'method' are ignored. Example: "
                f"call_meraki_api(section='{section}', method='{method}', parameters={json.dumps(example)})"
            )
        return to_json(response)
    except Exception as e:
        return to_json({
            "error": str(e),
            "type": type(e).__name__
        })

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

    Use search_methods(keyword=...) to find a method and get_method_info(section, method)
    for its parameters before calling it.

    Args:
        section: SDK section (organizations, networks, wireless, switch, appliance, camera, devices, sensor, sm, etc.)
        method: Method name (e.g., getOrganizationAdmins, updateNetworkWirelessSsid, getNetworkApplianceFirewallL3FirewallRules)
        parameters: Dict of the method's arguments (e.g., {"networkId": "L_123", "name": "MySSID"}).
            All method arguments, including path IDs such as serial or networkId, go inside this
            object; arguments placed next to section and method are ignored.

    Examples:
        call_meraki_api(section="organizations", method="getOrganizationAdmins", parameters={"organizationId": "123456"})
        call_meraki_api(section="wireless", method="updateNetworkWirelessSsid", parameters={"networkId": "L_123", "number": "0", "name": "NewSSID", "enabled": True})
        call_meraki_api(section="appliance", method="getNetworkApplianceFirewallL3FirewallRules", parameters={"networkId": "L_123"})
        call_meraki_api(section="devices", method="getDeviceLldpCdp", parameters={"serial": "Q2XX-XXXX-XXXX"})
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
async def getOrganizationAdmins(organizationId: Optional[str] = None) -> str:
    """Get organization administrators"""
    params = {}
    if organizationId:
        params['organizationId'] = organizationId
    return await call_meraki_method("organizations", "getOrganizationAdmins", **params)

@mcp.tool()
async def getOrganizationNetworks(organizationId: Optional[str] = None) -> str:
    """Get organization networks"""
    params = {}
    if organizationId:
        params['organizationId'] = organizationId
    return await call_meraki_method("organizations", "getOrganizationNetworks", **params)

@mcp.tool()
async def getOrganizationDevices(organizationId: Optional[str] = None) -> str:
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
async def getNetworkEvents(networkId: str, productType: Optional[str] = None, perPage: int = 100) -> str:
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
    name: Optional[str] = None,
    enabled: Optional[bool] = None,
    poeEnabled: Optional[bool] = None,
    type: Optional[str] = None,
    vlan: Optional[int] = None,
    voiceVlan: Optional[int] = None,
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

SEARCH_DEFAULT_LIMIT = 50
SEARCH_MAX_LIMIT = 200

@mcp.tool()
async def list_all_methods(section: Optional[str] = None) -> str:
    """
    List Meraki API methods. Prefer search_methods(keyword=...) to find a method.

    Without a section this returns only the section names and how many methods each
    has (the full list is roughly 10,000 tokens). Pass a section to list its methods.

    Args:
        section: Section to list (organizations, networks, wireless, switch, appliance, etc.)
    """
    if section:
        if section not in _METHOD_INDEX:
            return to_json({
                "error": f"Section '{section}' not found",
                "available_sections": list(_METHOD_INDEX.keys())
            })
        methods = _METHOD_INDEX[section]
        return to_json({
            "section": section,
            "methods": methods,
            "total_methods": len(methods),
            "usage": "Use call_meraki_api(section='...', method='...', parameters={...}) to call any method"
        })

    return to_json({
        "sections": {name: len(methods) for name, methods in _METHOD_INDEX.items()},
        "total_methods": sum(len(v) for v in _METHOD_INDEX.values()),
        "usage": (
            "Counts of methods per section. Use search_methods(keyword='...') to find a method, "
            "or list_all_methods(section='...') to list one section"
        )
    })

@mcp.tool()
async def search_methods(keyword: str, section: Optional[str] = None, limit: int = SEARCH_DEFAULT_LIMIT) -> str:
    """
    Search for Meraki API methods by keyword

    Args:
        keyword: One or more search terms; a method must contain all of them
            (e.g., 'firewall', 'ssid', 'wireless ssid', 'update switch port')
        section: Optional section to search within (e.g., 'wireless', 'appliance')
        limit: Maximum number of matches to return (default: 50, max: 200)
    """
    if section and section not in _METHOD_INDEX:
        return to_json({
            "error": f"Section '{section}' not found",
            "available_sections": list(_METHOD_INDEX.keys())
        })

    terms = keyword.lower().split()
    if not terms:
        return to_json({
            "error": "keyword must not be empty",
            "hint": "Use list_all_methods() to see the available sections"
        })

    limit = max(1, min(limit if isinstance(limit, int) else SEARCH_DEFAULT_LIMIT, SEARCH_MAX_LIMIT))
    sections = {section: _METHOD_INDEX[section]} if section else _METHOD_INDEX

    results = {}
    total_matches = 0
    returned = 0
    for section_name, methods in sections.items():
        matches = [m for m in methods if all(term in m.lower() for term in terms)]
        total_matches += len(matches)
        shown = matches[:limit - returned]
        if shown:
            results[section_name] = shown
            returned += len(shown)

    response = {
        "keyword": keyword,
        "results": results,
        "total_matches": total_matches,
        "usage": "Use call_meraki_api(section='...', method='...', parameters={...})"
    }
    if total_matches > returned:
        response["_truncated"] = True
        response["_returned"] = returned
        response["_hint"] = (
            f"Showing {returned} of {total_matches} matches. Add more terms to the keyword, "
            "pass section='...', or raise limit"
        )
    return to_json(response)

@mcp.tool()
async def get_method_info(section: str, method: str) -> str:
    """
    Get detailed parameter information for a method

    Args:
        section: SDK section (e.g., 'organizations', 'networks')
        method: Method name (e.g., 'getOrganizationAdmins')
    """
    try:
        method_func, lookup_error = _resolve_sdk_method(section, method)
        if lookup_error:
            return to_json(lookup_error)

        sig = inspect.signature(method_func)

        params = {}
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            params[param_name] = {
                "required": param.default == inspect.Parameter.empty,
                "default": None if param.default == inspect.Parameter.empty else str(param.default)
            }

        return to_json({
            "section": section,
            "method": method,
            "parameters": params,
            "docstring": inspect.getdoc(method_func),
            "usage_example": f'call_meraki_api(section="{section}", method="{method}", parameters={{...}})'
        })

    except Exception as e:
        return to_json({
            "error": str(e)
        })

@mcp.tool()
async def cache_stats() -> str:
    """Get cache statistics and configuration"""
    stats = cache.stats()
    stats['read_only_mode'] = READ_ONLY_MODE
    return to_json(stats)

@mcp.tool()
async def cache_clear() -> str:
    """Clear all cached data"""
    cache.clear()
    return to_json({
        "status": "success",
        "message": "Cache cleared successfully"
    })

@mcp.tool()
async def get_mcp_config() -> str:
    """Get MCP configuration"""
    return to_json({
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
        "meraki_caller": MERAKI_CALLER,
        "caching_enabled": ENABLE_CACHING,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "file_caching_enabled": ENABLE_FILE_CACHING,
        "max_response_tokens": MAX_RESPONSE_TOKENS,
        "max_per_page": MAX_PER_PAGE,
        "cache_max_items": CACHE_MAX_ITEMS,
        "response_cache_dir": RESPONSE_CACHE_DIR,
        "response_cache_max_age_hours": RESPONSE_CACHE_MAX_AGE_HOURS,
        "response_cache_max_mb": RESPONSE_CACHE_MAX_MB,
        "organization_id_configured": bool(MERAKI_ORG_ID),
        "api_key_configured": bool(MERAKI_API_KEY)
    })

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
            return to_json({
                "error": "Invalid filepath",
                "message": str(e)
            })

        data = load_response_from_file(filepath)
        if data is None:
            return to_json({
                "error": "Could not load cached response",
                "filepath": filepath
            })

        # Handle list pagination
        if isinstance(data, list):
            total_items = len(data)
            paginated_data = data[offset:offset + limit]

            return to_json({
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
            })
        else:
            # Non-list data - check size and potentially truncate
            data_json = json.dumps(data)
            estimated_tokens = estimate_token_count(data_json)

            if estimated_tokens > MAX_RESPONSE_TOKENS:
                return to_json({
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
                })

            return to_json(data)

    except Exception as e:
        return to_json({
            "error": str(e),
            "filepath": filepath
        })

@mcp.tool()
async def list_cached_responses() -> str:
    """List all cached response files"""
    try:
        if not os.path.exists(RESPONSE_CACHE_DIR):
            return to_json({
                "message": "No cache directory found",
                "cache_dir": RESPONSE_CACHE_DIR
            })

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

        return to_json({
            "cache_dir": RESPONSE_CACHE_DIR,
            "total_files": len(files),
            "files": files,
            "hint": "Use get_cached_response(filepath='...') to retrieve full data"
        })
    except Exception as e:
        return to_json({
            "error": str(e)
        })

@mcp.tool()
async def clear_cached_files(older_than_hours: int = 24) -> str:
    """
    Clear cached response files older than specified hours

    Args:
        older_than_hours: Delete files older than this many hours (default: 24)
    """
    try:
        if not os.path.exists(RESPONSE_CACHE_DIR):
            return to_json({
                "message": "No cache directory found",
                "cache_dir": RESPONSE_CACHE_DIR
            })

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

        return to_json({
            "cache_dir": RESPONSE_CACHE_DIR,
            "deleted_count": len(deleted),
            "kept_count": len(kept),
            "deleted_files": deleted,
            "kept_files": kept
        })
    except Exception as e:
        return to_json({
            "error": str(e)
        })

# Module-level ASGI app for external uvicorn invocation
app = mcp.streamable_http_app() if MCP_TRANSPORT in ("http", "streamable-http") else None

if __name__ == "__main__":
    transport = "streamable-http" if MCP_TRANSPORT == "http" else MCP_TRANSPORT
    print(f"Starting Meraki Magic MCP - Full API ({transport} transport)", file=sys.stderr)
    if transport in ("streamable-http", "sse"):
        print(f"Listening on {MCP_HOST}:{MCP_PORT}", file=sys.stderr)
    mcp.run(transport=transport)

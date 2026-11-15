#!/usr/bin/env python3
# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: MIT

"""
Inspection script to see which SDK methods the dynamic MCP can call
This script does NOT make any API calls - it only inspects the SDK structure
"""

import os
import meraki
import inspect
import re
from pathlib import Path
from meraki_mcp_config import SDK_SECTIONS, get_meraki_base_url

# Initialize SDK (with dummy key for inspection - won't make calls)
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY", "dummy_key")
dashboard = meraki.DashboardAPI(
    api_key=MERAKI_API_KEY,
    base_url=get_meraki_base_url(),
    suppress_logging=True,
)

print("=" * 100)
print("MERAKI MCP DYNAMIC TOOL INSPECTION")
print("=" * 100)
print("\nThis script inspects the Meraki SDK to show which methods call_meraki_api can reach.")
print("NO API CALLS ARE MADE - This is safe to run with your production API key.\n")

print("=" * 100)
print("METHOD COUNT BY SECTION")
print("=" * 100)

total_tools = 0
section_details = {}

for section_name in SDK_SECTIONS:
    if not hasattr(dashboard, section_name):
        continue

    section_obj = getattr(dashboard, section_name)
    methods = [m for m in dir(section_obj)
               if not m.startswith('_') and callable(getattr(section_obj, m))]

    section_details[section_name] = sorted(methods)
    total_tools += len(methods)

    print(f"{section_name:20} : {len(methods):4} methods")

print("=" * 100)
print(f"{'TOTAL':20} : {total_tools:4} methods")

# Show examples from each section
print("\n" + "=" * 100)
print("SAMPLE METHODS FROM EACH SECTION (first 5 per section)")
print("=" * 100)

for section_name, methods in section_details.items():
    print(f"\n{section_name.upper()}:")
    for method in methods[:5]:
        print(f"  • call_meraki_api(section='{section_name}', method='{method}', ...)")
    if len(methods) > 5:
        print(f"  ... and {len(methods) - 5} more")

# Show parameter inspection for a few example methods
print("\n" + "=" * 100)
print("EXAMPLE METHOD PARAMETER DETAILS")
print("=" * 100)

example_methods = [
    ('organizations', 'getOrganization'),
    ('networks', 'getNetworkClients'),
    ('wireless', 'updateNetworkWirelessSsid'),
    ('devices', 'rebootDevice'),
]

for section_name, method_name in example_methods:
    section_obj = getattr(dashboard, section_name)
    method = getattr(section_obj, method_name)

    print(f"\n{section_name}.{method_name}")
    print("-" * 100)

    # Get method signature
    sig = inspect.signature(method)
    params = []
    for param_name, param in sig.parameters.items():
        if param_name == 'self':
            continue
        required = param.default == inspect.Parameter.empty
        default_val = None if param.default == inspect.Parameter.empty else param.default
        params.append({
            'name': param_name,
            'required': required,
            'default': default_val
        })

    if params:
        print("  Parameters:")
        for p in params:
            req_str = "REQUIRED" if p['required'] else f"optional (default: {p['default']})"
            print(f"    - {p['name']}: {req_str}")
    else:
        print("  No parameters")

    # Get docstring
    docstring = inspect.getdoc(method)
    if docstring:
        print(f"  Description: {docstring[:200]}...")

# Search examples
print("\n" + "=" * 100)
print("SEARCH EXAMPLES")
print("=" * 100)

search_terms = ['firewall', 'vpn', 'client', 'alert', 'admin']

for term in search_terms:
    matches = []
    for section_name, methods in section_details.items():
        for method in methods:
            if term.lower() in method.lower():
                matches.append(f"{section_name}.{method}")

    print(f"\nSearch: '{term}' - Found {len(matches)} methods")
    for match in matches[:10]:
        print(f"  • {match}")
    if len(matches) > 10:
        print(f"  ... and {len(matches) - 10} more")

# Coverage comparison
print("\n" + "=" * 100)
print("COVERAGE COMPARISON")
print("=" * 100)

# Count the tools registered by the manual server from its source
manual_source = (Path(__file__).resolve().parent / "meraki-mcp.py").read_text()
manual_mcp_tools = len(re.findall(r"^@(?:mcp\.tool\(\)|threaded_tool)$", manual_source, flags=re.M))
dynamic_mcp_methods = total_tools

print(f"\nManual MCP (meraki-mcp.py):          {manual_mcp_tools:4} curated tools")
print(f"Dynamic MCP (meraki-mcp-dynamic.py): {dynamic_mcp_methods:4} SDK methods via call_meraki_api")

print("\n" + "=" * 100)
print("INSPECTION COMPLETE")
print("=" * 100)
print("\nNext steps:")
print("1. Review the tool counts and examples above")
print("2. Update your claude_desktop_config.json to use meraki-mcp-dynamic.py")
print("3. Restart Claude Desktop")
print("4. Test with helper tools first (list_all_methods, search_methods, get_method_info)")
print("5. Start with read-only operations before trying updates/deletes")

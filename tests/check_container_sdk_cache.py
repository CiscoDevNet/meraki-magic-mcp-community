"""Run inside the built image as its default user, with Docker networking disabled."""

import json
import os
import runpy
from pathlib import Path

import httpx
from meraki.config import SMART_FLOW_CACHE_PATH


def inventory_response(request):
    serial = request.url.path.rsplit("/", 1)[-1]
    return httpx.Response(200, json={"serial": serial})


def main():
    assert os.getuid() == 10001
    server = runpy.run_path("meraki-mcp-dynamic.py")
    session = server["dashboard"]._session
    session._client.close()
    with httpx.Client(transport=httpx.MockTransport(inventory_response)) as client:
        session._client = client
        # The pinned SDK flushes its rate-limit cache after learning 50 mappings.
        for index in range(51):
            serial = f"Q2XX-0000-{index:04d}"
            params = {"organizationId": str(1000 + index // 5), "serial": serial}
            result = server["_call_meraki_method_internal"]("organizations", "getOrganizationInventoryDevice", params)
            assert json.loads(result) == {"serial": serial}, result
    cache_path = Path(SMART_FLOW_CACHE_PATH)
    assert cache_path.is_relative_to(Path.home())
    assert cache_path.stat().st_size > 0


if __name__ == "__main__":
    main()

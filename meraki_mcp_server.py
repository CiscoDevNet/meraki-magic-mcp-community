# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: MIT

import sys

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from meraki_mcp_config import BearerTokenMiddleware, get_auth_token, http_security_warnings


class MerakiMCP(FastMCP):
    """Apply the same transport security to the exported app and FastMCP's launchers."""

    def _secure(self, app: Starlette) -> Starlette:
        token = get_auth_token()
        for warning in http_security_warnings(self.settings.host, token):
            print(warning, file=sys.stderr)
        if token:
            app.add_middleware(BearerTokenMiddleware, token=token)
        return app

    def sse_app(self, mount_path: str | None = None) -> Starlette:
        return self._secure(super().sse_app(mount_path))

    def streamable_http_app(self) -> Starlette:
        return self._secure(super().streamable_http_app())

    def http_app(self, transport: str) -> Starlette:
        return self.sse_app() if transport == "sse" else self.streamable_http_app()

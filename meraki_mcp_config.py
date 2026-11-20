# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: MIT

import hmac
import json
import os
from typing import Any, Callable, MutableMapping


DEFAULT_MERAKI_BASE_URL = "https://api.meraki.com/api/v1"
DEFAULT_MERAKI_CALLER = "MagicMCP CiscoDevNet"
CONFIRM_DESTRUCTIVE_ACTION_PARAM = "confirm_destructive_action"

# Meraki SDK sections exposed by the dynamic server and inspected by inspect_tools.py
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

READ_ONLY_PREFIXES = ("get", "list")

# Leading verbs of every non-read method in the Meraki SDK that have been reviewed.
# Classification fails closed: anything that is not a read is treated as a write
# whether or not its verb is listed here. The list exists so that
# tests/test_config_and_safety.py fails when an SDK upgrade introduces a new verb,
# prompting a review of whether it also belongs in DESTRUCTIVE_PREFIXES.
WRITE_PREFIXES = (
    "add",
    "assign",
    "attach",
    "batch",
    "bind",
    "blink",
    "bulk",
    "cancel",
    "certificates",
    "checkin",
    "claim",
    "clip",
    "clone",
    "combine",
    "commit",
    "connect",
    "create",
    "cycle",
    "declare",
    "defer",
    "delete",
    "detach",
    "disable",
    "disconnect",
    "dismiss",
    "enable",
    "exclusions",
    "generate",
    "httpsi",
    "install",
    "lock",
    "modify",
    "move",
    "preview",
    "protection",
    "provision",
    "publish",
    "reassign",
    "reboot",
    "recalculate",
    "refresh",
    "release",
    "remove",
    "renew",
    "reorder",
    "restore",
    "revoke",
    "rollbacks",
    "set",
    "shutdown",
    "split",
    "stop",
    "swap",
    "unbind",
    "unenroll",
    "uninstall",
    "update",
    "validate",
    "vmx",
    "wipe",
)
DESTRUCTIVE_PREFIXES = (
    "delete",
    "remove",
    "release",
    "wipe",
    "unenroll",
    "uninstall",
    "revoke",
    "detach",
)
# Bulk endpoints put the verb last, e.g. bulkOrganizationNetworksGroup...Delete
# and create...AssignmentsBulkDelete.
DESTRUCTIVE_SUFFIXES = ("Delete",)

_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off"}


def to_json(data: Any) -> str:
    """Serialize a tool response as compact JSON.

    Tool output is read by a model, not a person: indentation carries no information
    and costs roughly 40% more tokens on typical Meraki list responses.
    """
    return json.dumps(data, separators=(",", ":"))


def parse_bool(value: Any, default: bool = False) -> bool:
    """Parse common environment/tool boolean values."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    return default


def env_bool(name: str, default: bool = False) -> bool:
    return parse_bool(os.getenv(name), default)


def get_read_only_mode(default: bool = True) -> bool:
    """Return read-only mode, supporting READ_ONLY_MODE and READ_ONLY."""
    if os.getenv("READ_ONLY_MODE") is not None:
        return env_bool("READ_ONLY_MODE", default)
    if os.getenv("READ_ONLY") is not None:
        return env_bool("READ_ONLY", default)
    return default


def get_meraki_base_url() -> str:
    configured = os.getenv("MERAKI_BASE_URL", DEFAULT_MERAKI_BASE_URL).strip()
    return configured or DEFAULT_MERAKI_BASE_URL


def get_meraki_caller() -> str:
    configured = os.getenv("MERAKI_PYTHON_SDK_CALLER", "").strip()
    return configured or DEFAULT_MERAKI_CALLER


def is_read_only_operation(method_name: str) -> bool:
    normalized = method_name.lower()
    return any(normalized.startswith(prefix) for prefix in READ_ONLY_PREFIXES)


def is_write_operation(method_name: str) -> bool:
    """Treat every method that is not a known read as a write (fail closed)."""
    return not is_read_only_operation(method_name)


def is_destructive_operation(method_name: str) -> bool:
    if is_read_only_operation(method_name):
        return False
    normalized = method_name.lower()
    return any(normalized.startswith(prefix) for prefix in DESTRUCTIVE_PREFIXES) or method_name.endswith(
        DESTRUCTIVE_SUFFIXES
    )


def pop_destructive_confirmation(params: MutableMapping[str, Any]) -> bool:
    value = params.pop(CONFIRM_DESTRUCTIVE_ACTION_PARAM, False)
    return parse_bool(value, default=False)


def write_blocked_payload(method_name: str) -> dict[str, Any]:
    return {
        "error": "Write operation blocked - READ_ONLY_MODE is enabled",
        "method": method_name,
        "hint": "Set READ_ONLY_MODE=false in the MCP client env or process environment",
    }


def destructive_confirmation_required_payload(method_name: str) -> dict[str, Any]:
    return {
        "error": "Destructive operation requires explicit confirmation",
        "method": method_name,
        "confirmation_required": True,
        "confirmation_parameter": CONFIRM_DESTRUCTIVE_ACTION_PARAM,
        "hint": f"Set {CONFIRM_DESTRUCTIVE_ACTION_PARAM}=true for this call after verifying the target",
    }


def guard_write_operation(
    method_name: str,
    read_only_mode: bool,
    confirm_destructive_action: Any = False,
) -> str | None:
    if read_only_mode and is_write_operation(method_name):
        return to_json(write_blocked_payload(method_name))
    if is_destructive_operation(method_name) and not parse_bool(confirm_destructive_action, default=False):
        return to_json(destructive_confirmation_required_payload(method_name))
    return None


###################
# HTTP TRANSPORT SECURITY
###################

MCP_AUTH_TOKEN_ENV = "MCP_AUTH_TOKEN"
HTTP_TRANSPORTS = ("http", "streamable-http", "sse")
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
MIN_AUTH_TOKEN_LENGTH = 32


def get_auth_token() -> str | None:
    """Return the bearer token required by the HTTP transports, or None when unset."""
    token = os.getenv(MCP_AUTH_TOKEN_ENV, "").strip()
    return token or None


def normalize_transport(transport: str) -> str:
    """Map the MCP_TRANSPORT value to the name FastMCP uses."""
    return "streamable-http" if transport == "http" else transport


class BearerTokenMiddleware:
    """ASGI middleware that rejects HTTP requests without the configured bearer token.

    Every HTTP request must send ``Authorization: Bearer <token>``. Lifespan events
    pass through so the MCP session manager can start and stop normally.
    """

    def __init__(self, app: Callable, token: str):
        if not token:
            raise ValueError("token must not be empty")
        self.app = app
        self._token = token.encode()

    def _is_authorized(self, scope: dict) -> bool:
        for name, value in scope.get("headers") or []:
            if name.lower() == b"authorization":
                scheme, _, credentials = value.strip().partition(b" ")
                return scheme.lower() == b"bearer" and hmac.compare_digest(credentials.strip(), self._token)
        return False

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] not in ("http", "websocket") or self._is_authorized(scope):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return

        body = to_json({
            "error": "unauthorized",
            "message": f"Send 'Authorization: Bearer <token>' with the value of {MCP_AUTH_TOKEN_ENV}",
        }).encode()
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"www-authenticate", b'Bearer realm="meraki-magic-mcp"'),
            ],
        })
        await send({"type": "http.response.body", "body": body})


def http_security_warnings(host: str, token: str | None) -> list[str]:
    """Return warnings about an HTTP deployment's exposure, for printing at startup."""
    warnings = []
    if token is None and host not in LOOPBACK_HOSTS:
        warnings.append(
            f"WARNING: HTTP transport is bound to {host} without authentication. Anyone who can "
            f"reach this port can use the server with your Meraki API key. Set {MCP_AUTH_TOKEN_ENV} "
            "to require a bearer token, or bind MCP_HOST to 127.0.0.1. (In Docker, the default "
            "docker-compose.yml publishes the port on the host's loopback interface only.)"
        )
    if token is not None and len(token) < MIN_AUTH_TOKEN_LENGTH:
        warnings.append(
            f"WARNING: {MCP_AUTH_TOKEN_ENV} is shorter than {MIN_AUTH_TOKEN_LENGTH} characters. "
            "Generate a stronger one, e.g. with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return warnings


def serve_http(app: Callable, host: str, port: int) -> None:
    """Serve an ASGI app with uvicorn (the same server FastMCP uses for its HTTP transports)."""
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")

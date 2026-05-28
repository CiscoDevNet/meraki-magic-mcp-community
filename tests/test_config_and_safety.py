import importlib.util
import json
import os
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import meraki_mcp_config as config


ROOT = Path(__file__).resolve().parents[1]


class FakeFastMCP:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def tool(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def resource(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def streamable_http_app(self):
        return object()

    def run(self, *args, **kwargs):
        return None


class FakeSection:
    def __init__(self, section_name, calls):
        self.section_name = section_name
        self.calls = calls

    def __dir__(self):
        return [
            "deleteNetwork",
            "getNetwork",
            "removeNetworkDevices",
            "updateDeviceSwitchPort",
        ]

    def __getattr__(self, method_name):
        def method(*args, **kwargs):
            self.calls.append(
                {
                    "section": self.section_name,
                    "method": method_name,
                    "args": args,
                    "kwargs": kwargs,
                }
            )
            return {"section": self.section_name, "method": method_name, "kwargs": kwargs}

        setattr(self, method_name, method)
        return method


class FakeDashboardAPI:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        for section in [
            "organizations",
            "networks",
            "devices",
            "wireless",
            "switch",
            "appliance",
            "camera",
            "cellularGateway",
            "sensor",
            "sm",
            "insight",
            "licensing",
            "administered",
        ]:
            setattr(self, section, FakeSection(section, self.calls))
        FakeDashboardAPI.instances.append(self)


class FakeBaseModel:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def model_dump(self, exclude_none=False):
        if exclude_none:
            return {key: value for key, value in self.__dict__.items() if value is not None}
        return dict(self.__dict__)


def fake_field(default=None, default_factory=None, **kwargs):
    if default_factory is not None:
        return default_factory()
    return default


@contextmanager
def fake_runtime_modules():
    fake_meraki = types.ModuleType("meraki")
    fake_meraki.DashboardAPI = FakeDashboardAPI

    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None

    fake_mcp = types.ModuleType("mcp")
    fake_mcp_server = types.ModuleType("mcp.server")
    fake_fastmcp = types.ModuleType("mcp.server.fastmcp")
    fake_fastmcp.FastMCP = FakeFastMCP

    fake_pydantic = types.ModuleType("pydantic")
    fake_pydantic.BaseModel = FakeBaseModel
    fake_pydantic.Field = fake_field

    module_overrides = {
        "meraki": fake_meraki,
        "dotenv": fake_dotenv,
        "mcp": fake_mcp,
        "mcp.server": fake_mcp_server,
        "mcp.server.fastmcp": fake_fastmcp,
        "pydantic": fake_pydantic,
    }
    sentinel = object()
    originals = {name: sys.modules.get(name, sentinel) for name in module_overrides}
    FakeDashboardAPI.instances = []
    sys.modules.update(module_overrides)
    try:
        yield FakeDashboardAPI
    finally:
        for name, original in originals.items():
            if original is sentinel:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def load_script_module(filename, module_name):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class ConfigTests(unittest.TestCase):
    def test_read_only_defaults_to_true_and_supports_alias(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(config.get_read_only_mode())

        with patch.dict(os.environ, {"READ_ONLY": "false"}, clear=True):
            self.assertFalse(config.get_read_only_mode())

        with patch.dict(
            os.environ,
            {"READ_ONLY": "true", "READ_ONLY_MODE": "false"},
            clear=True,
        ):
            self.assertFalse(config.get_read_only_mode())

    def test_base_url_default_and_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config.DEFAULT_MERAKI_BASE_URL, config.get_meraki_base_url())

        with patch.dict(os.environ, {"MERAKI_BASE_URL": "https://api.meraki.cn/api/v1"}, clear=True):
            self.assertEqual("https://api.meraki.cn/api/v1", config.get_meraki_base_url())

        with patch.dict(os.environ, {"MERAKI_BASE_URL": "  "}, clear=True):
            self.assertEqual(config.DEFAULT_MERAKI_BASE_URL, config.get_meraki_base_url())

    def test_operation_classification(self):
        self.assertTrue(config.is_write_operation("createOrganizationNetwork"))
        self.assertTrue(config.is_write_operation("cycleDeviceSwitchPorts"))
        self.assertTrue(config.is_write_operation("generateDeviceCameraSnapshot"))
        self.assertTrue(config.is_write_operation("blinkDeviceLeds"))
        self.assertTrue(config.is_destructive_operation("deleteNetwork"))
        self.assertTrue(config.is_destructive_operation("removeNetworkDevices"))
        self.assertFalse(config.is_destructive_operation("updateNetwork"))


class DynamicServerSafetyTests(unittest.TestCase):
    def test_dynamic_dashboard_receives_configured_base_url(self):
        with patch.dict(
            os.environ,
            {
                "MERAKI_API_KEY": "dummy",
                "MERAKI_BASE_URL": "https://api.meraki.cn/api/v1",
            },
            clear=True,
        ), fake_runtime_modules() as dashboard_cls:
            load_script_module("meraki-mcp-dynamic.py", "test_dynamic_base_url")

        self.assertEqual("https://api.meraki.cn/api/v1", dashboard_cls.instances[0].kwargs["base_url"])

    def test_dynamic_blocks_writes_by_default(self):
        with patch.dict(os.environ, {"MERAKI_API_KEY": "dummy"}, clear=True), fake_runtime_modules():
            module = load_script_module("meraki-mcp-dynamic.py", "test_dynamic_read_only")
            response = json.loads(
                module._call_meraki_method_internal(
                    "networks",
                    "deleteNetwork",
                    {"networkId": "N_123"},
                )
            )

            self.assertEqual("Write operation blocked - READ_ONLY_MODE is enabled", response["error"])
            self.assertEqual([], module.dashboard.calls)

    def test_dynamic_requires_and_strips_destructive_confirmation(self):
        with patch.dict(
            os.environ,
            {"MERAKI_API_KEY": "dummy", "READ_ONLY_MODE": "false"},
            clear=True,
        ), fake_runtime_modules():
            module = load_script_module("meraki-mcp-dynamic.py", "test_dynamic_confirm")
            missing_confirmation = json.loads(
                module._call_meraki_method_internal(
                    "networks",
                    "deleteNetwork",
                    {"networkId": "N_123"},
                )
            )
            confirmed = json.loads(
                module._call_meraki_method_internal(
                    "networks",
                    "deleteNetwork",
                    {
                        "networkId": "N_123",
                        config.CONFIRM_DESTRUCTIVE_ACTION_PARAM: True,
                    },
                )
            )

            self.assertEqual(
                "Destructive operation requires explicit confirmation",
                missing_confirmation["error"],
            )
            self.assertEqual("deleteNetwork", confirmed["method"])
            self.assertNotIn(
                config.CONFIRM_DESTRUCTIVE_ACTION_PARAM,
                module.dashboard.calls[-1]["kwargs"],
            )


class ManualServerSafetyTests(unittest.TestCase):
    def test_manual_dashboard_receives_configured_base_url(self):
        with patch.dict(
            os.environ,
            {
                "MERAKI_API_KEY": "dummy",
                "MERAKI_BASE_URL": "https://api.meraki.cn/api/v1",
            },
            clear=True,
        ), fake_runtime_modules() as dashboard_cls:
            load_script_module("meraki-mcp.py", "test_manual_base_url")

        self.assertEqual("https://api.meraki.cn/api/v1", dashboard_cls.instances[0].kwargs["base_url"])

    def test_manual_destructive_tool_requires_write_mode_and_confirmation(self):
        with patch.dict(os.environ, {"MERAKI_API_KEY": "dummy"}, clear=True), fake_runtime_modules():
            read_only_module = load_script_module("meraki-mcp.py", "test_manual_read_only")
            read_only_response = json.loads(read_only_module.delete_network("N_123"))

        with patch.dict(
            os.environ,
            {"MERAKI_API_KEY": "dummy", "READ_ONLY_MODE": "false"},
            clear=True,
        ), fake_runtime_modules():
            write_module = load_script_module("meraki-mcp.py", "test_manual_confirm")
            missing_confirmation = json.loads(write_module.delete_network("N_123"))
            confirmed = write_module.delete_network("N_123", confirm_destructive_action=True)

            self.assertEqual(
                "Destructive operation requires explicit confirmation",
                missing_confirmation["error"],
            )
            self.assertEqual("Network N_123 deleted", confirmed)
            self.assertEqual("deleteNetwork", write_module.dashboard.calls[-1]["method"])

        self.assertEqual("Write operation blocked - READ_ONLY_MODE is enabled", read_only_response["error"])


if __name__ == "__main__":
    unittest.main()

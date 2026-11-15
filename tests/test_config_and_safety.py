import asyncio
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
    fake_meraki.exceptions = types.SimpleNamespace(APIError=type("APIError", (Exception,), {}))

    fake_mcp = types.ModuleType("mcp")
    fake_mcp_server = types.ModuleType("mcp.server")
    fake_fastmcp = types.ModuleType("mcp.server.fastmcp")
    fake_fastmcp.FastMCP = FakeFastMCP

    fake_pydantic = types.ModuleType("pydantic")
    fake_pydantic.BaseModel = FakeBaseModel
    fake_pydantic.Field = fake_field

    module_overrides = {
        "meraki": fake_meraki,
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
    def test_caller_default_and_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config.DEFAULT_MERAKI_CALLER, config.get_meraki_caller())

        with patch.dict(os.environ, {"MERAKI_PYTHON_SDK_CALLER": "InventoryTool ExampleOrg"}, clear=True):
            self.assertEqual("InventoryTool ExampleOrg", config.get_meraki_caller())

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
        self.assertTrue(config.is_write_operation("releaseFromOrganizationInventory"))
        self.assertTrue(config.is_destructive_operation("releaseFromOrganizationInventory"))
        self.assertFalse(config.is_destructive_operation("updateNetwork"))

    def test_unknown_verbs_are_treated_as_writes(self):
        for method in [
            "wipeNetworkSmDevices",
            "lockNetworkSmDevices",
            "shutdownNetworkSmDevices",
            "swapNetworkApplianceWarmSpare",
            "bulkUpdateOrganizationDevicesDetails",
            "revokeAdministeredIdentitiesMeApiKeys",
            "someFutureVerbOrganizationThing",
            "post",
            "put",
            "",
        ]:
            with self.subTest(method=method):
                self.assertTrue(config.is_write_operation(method))
                self.assertFalse(config.is_read_only_operation(method))
                self.assertIsNotNone(config.guard_write_operation(method, read_only_mode=True))

        for method in ["getNetwork", "getOrganizationDevices"]:
            with self.subTest(method=method):
                self.assertFalse(config.is_write_operation(method))
                self.assertIsNone(config.guard_write_operation(method, read_only_mode=True))

    def test_destructive_classification_covers_wipe_revoke_and_bulk_delete(self):
        for method in [
            "wipeNetworkSmDevices",
            "unenrollNetworkSmDevice",
            "uninstallNetworkSmDeviceApps",
            "revokeAdministeredIdentitiesMeApiKeys",
            "detachOrganizationSaseSites",
            "batchOrganizationSaseConnectorsDelete",
            "bulkOrganizationDevicesPacketCaptureCapturesDelete",
            "createOrganizationApplianceDnsLocalProfilesAssignmentsBulkDelete",
        ]:
            with self.subTest(method=method):
                self.assertTrue(config.is_destructive_operation(method))
                blocked = json.loads(config.guard_write_operation(method, read_only_mode=False))
                self.assertTrue(blocked["confirmation_required"])
                self.assertIsNone(config.guard_write_operation(method, False, True))

        for method in ["getNetworkSmDevices", "getOrganizationConfigTemplatesDelete", "lockNetworkSmDevices"]:
            with self.subTest(method=method):
                self.assertFalse(config.is_destructive_operation(method))


class SdkClassificationDriftTests(unittest.TestCase):
    """Run against the installed Meraki SDK so upgrades cannot silently add unreviewed verbs."""

    @staticmethod
    def _sdk_methods():
        import meraki

        dashboard = meraki.DashboardAPI(api_key="dummy", suppress_logging=True)
        for section_name in dir(dashboard):
            section = getattr(dashboard, section_name)
            if section_name.startswith("_") or not hasattr(section, "_session"):
                continue
            for method_name in dir(section):
                if not method_name.startswith("_") and callable(getattr(section, method_name)):
                    yield section_name, method_name

    def setUp(self):
        try:
            import meraki  # noqa: F401
        except ImportError:
            self.skipTest("Meraki SDK is not installed")

    def test_every_sdk_method_starts_with_a_reviewed_verb(self):
        known = config.READ_ONLY_PREFIXES + config.WRITE_PREFIXES
        unreviewed = sorted(
            f"{section}.{method}"
            for section, method in self._sdk_methods()
            if not any(
                method.startswith(prefix) and not method[len(prefix):len(prefix) + 1].islower()
                for prefix in known
            )
        )
        self.assertEqual(
            [],
            unreviewed,
            "New SDK verbs found. Add them to WRITE_PREFIXES in meraki_mcp_config.py "
            "(and DESTRUCTIVE_PREFIXES if they delete or wipe data).",
        )

    def test_sdk_delete_like_methods_require_confirmation(self):
        import re

        pattern = re.compile(r"Delete|Remove|Release|Wipe|Revoke|Unenroll|Uninstall")
        missed = sorted(
            f"{section}.{method}"
            for section, method in self._sdk_methods()
            if not config.is_read_only_operation(method)
            and pattern.search(method[0].upper() + method[1:])
            and not config.is_destructive_operation(method)
        )
        self.assertEqual([], missed)


class DynamicServerSafetyTests(unittest.TestCase):
    def test_inventory_release_requires_write_mode_and_confirmation(self):
        for read_only, confirmed, expected_error in [
            ("true", False, "Write operation blocked - READ_ONLY_MODE is enabled"),
            ("true", True, "Write operation blocked - READ_ONLY_MODE is enabled"),
            ("false", False, "Destructive operation requires explicit confirmation"),
            ("false", True, None),
        ]:
            with self.subTest(read_only=read_only, confirmed=confirmed), patch.dict(
                os.environ,
                {"MERAKI_API_KEY": "dummy", "READ_ONLY_MODE": read_only,
                 "ENABLE_FILE_CACHING": "false"},
                clear=True,
            ), fake_runtime_modules():
                module = load_script_module("meraki-mcp-dynamic.py", "test_dynamic_release")
                params = {"organizationId": "123", "serials": ["Q234-ABCD-5678"],
                          config.CONFIRM_DESTRUCTIVE_ACTION_PARAM: confirmed}
                response = json.loads(module._call_meraki_method_internal(
                    "organizations", "releaseFromOrganizationInventory", params))
                if expected_error:
                    self.assertEqual(expected_error, response["error"])
                    self.assertEqual([], module.dashboard.calls)
                else:
                    self.assertEqual("releaseFromOrganizationInventory", response["method"])
                    self.assertEqual(1, len(module.dashboard.calls))
                    self.assertEqual(
                        {"organizationId": "123", "serials": ["Q234-ABCD-5678"]},
                        module.dashboard.calls[0]["kwargs"],
                    )
                self.assertEqual(confirmed, params[config.CONFIRM_DESTRUCTIVE_ACTION_PARAM])

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
        self.assertEqual(config.DEFAULT_MERAKI_CALLER, dashboard_cls.instances[0].kwargs["caller"])

    def test_dynamic_dashboard_receives_caller_override(self):
        with patch.dict(
            os.environ,
            {"MERAKI_API_KEY": "dummy", "MERAKI_PYTHON_SDK_CALLER": "InventoryTool ExampleOrg"},
            clear=True,
        ), fake_runtime_modules() as dashboard_cls:
            load_script_module("meraki-mcp-dynamic.py", "test_dynamic_caller")
            self.assertEqual("InventoryTool ExampleOrg", dashboard_cls.instances[0].kwargs["caller"])

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


    def test_dynamic_blocks_unlisted_write_verbs_in_read_only_mode(self):
        with patch.dict(os.environ, {"MERAKI_API_KEY": "dummy"}, clear=True), fake_runtime_modules():
            module = load_script_module("meraki-mcp-dynamic.py", "test_dynamic_read_only_verbs")
            for method in ["wipeNetworkSmDevices", "lockNetworkSmDevices", "bulkUpdateOrganizationDevicesDetails"]:
                with self.subTest(method=method):
                    response = json.loads(
                        module._call_meraki_method_internal("sm", method, {"networkId": "N_123"})
                    )
                    self.assertEqual(
                        "Write operation blocked - READ_ONLY_MODE is enabled", response["error"]
                    )
            self.assertEqual([], module.dashboard.calls)

    def test_dynamic_rejects_internal_sections_and_private_methods(self):
        with patch.dict(
            os.environ,
            {"MERAKI_API_KEY": "dummy", "READ_ONLY_MODE": "false"},
            clear=True,
        ), fake_runtime_modules():
            module = load_script_module("meraki-mcp-dynamic.py", "test_dynamic_allowlist")
            session_calls = []

            def record(*args, **kwargs):
                session_calls.append((args, kwargs))
                return {"ok": True}

            module.dashboard._session = types.SimpleNamespace(post=record, put=record, get=record)
            module.dashboard.batch = types.SimpleNamespace(getSomething=record)
            module.dashboard.networks._private = record

            for section, method in [
                ("_session", "post"),
                ("_session", "put"),
                ("_session", "get"),
                ("batch", "getSomething"),
                ("__class__", "mro"),
                ("networks", "_private"),
                ("networks", "__init__"),
            ]:
                with self.subTest(section=section, method=method):
                    response = json.loads(
                        module._call_meraki_method_internal(section, method, {"url": "/organizations"})
                    )
                    self.assertIn("error", response)
                    info = json.loads(asyncio.run(module.get_method_info(section, method)))
                    self.assertIn("error", info)

            self.assertEqual([], session_calls)
            self.assertEqual([], module.dashboard.calls)

            allowed = json.loads(
                module._call_meraki_method_internal("networks", "getNetwork", {"networkId": "N_1"})
            )
            self.assertEqual("getNetwork", allowed["method"])


class DynamicServerTruncationTests(unittest.TestCase):
    def _load(self, name, cache_dir):
        return patch.dict(
            os.environ,
            {
                "MERAKI_API_KEY": "dummy",
                "MAX_RESPONSE_TOKENS": "500",
                "RESPONSE_CACHE_DIR": cache_dir,
            },
            clear=True,
        )

    def _call_with_result(self, result):
        import tempfile

        with tempfile.TemporaryDirectory() as cache_dir, self._load("x", cache_dir), fake_runtime_modules():
            module = load_script_module("meraki-mcp-dynamic.py", "test_dynamic_truncation")
            module.dashboard.networks = types.SimpleNamespace(getNetwork=lambda networkId: result)
            raw = module._call_meraki_method_internal("networks", "getNetwork", {"networkId": "N_1"})
            response = json.loads(raw)
            cached = None
            if response.get("_response_truncated"):
                cached = module.load_response_from_file(response["_full_response_cached"])
            return module, raw, response, cached

    def assert_bounded(self, module, raw, response, cached, result):
        self.assertTrue(response["_response_truncated"])
        self.assertEqual(result, cached)
        preview_chars = len(json.dumps(response["_preview"]))
        self.assertLessEqual(preview_chars, module.PREVIEW_BUDGET_CHARS)
        self.assertLess(len(raw), len(json.dumps(result)))

    def test_large_dict_response_is_actually_truncated(self):
        result = {f"key{i}": "v" * 100 for i in range(400)}
        module, raw, response, cached = self._call_with_result(result)
        self.assert_bounded(module, raw, response, cached, result)
        self.assertEqual("v" * 100, response["_preview"]["key0"])
        self.assertGreater(response["_preview"]["_omitted_keys"], 0)

    def test_dict_with_one_huge_value_is_truncated(self):
        result = {"name": "net", "items": [{"id": i, "pad": "x" * 50} for i in range(500)]}
        module, raw, response, cached = self._call_with_result(result)
        self.assert_bounded(module, raw, response, cached, result)
        self.assertEqual("net", response["_preview"]["name"])
        self.assertEqual("<list of 500 items - see cached file>", response["_preview"]["items"])
        self.assertEqual(["name", "items"], response["_keys"])

    def test_short_list_of_huge_items_is_truncated(self):
        result = [{"id": i, "blob": "x" * 5000} for i in range(2)]
        module, raw, response, cached = self._call_with_result(result)
        self.assert_bounded(module, raw, response, cached, result)
        self.assertEqual(2, response["_total_items"])
        self.assertEqual(0, response["_preview"][0]["id"])

    def test_long_list_keeps_first_items_intact(self):
        result = [{"serial": f"Q2XX-{i:04d}", "name": f"ap{i}"} for i in range(300)]
        module, raw, response, cached = self._call_with_result(result)
        self.assert_bounded(module, raw, response, cached, result)
        self.assertEqual(result[:3], response["_preview"])
        self.assertEqual(300, response["_total_items"])

    def test_small_response_is_returned_unchanged(self):
        result = {"id": "N_1", "name": "small"}
        _, _, response, _ = self._call_with_result(result)
        self.assertEqual(result, response)


class DynamicServerParameterTests(unittest.TestCase):
    def test_missing_required_parameter_explains_parameters_object(self):
        with patch.dict(os.environ, {"MERAKI_API_KEY": "dummy", "ENABLE_FILE_CACHING": "false"},
                        clear=True), fake_runtime_modules():
            module = load_script_module("meraki-mcp-dynamic.py", "test_dynamic_missing_param")
            module.dashboard.devices = types.SimpleNamespace(
                getDeviceLldpCdp=lambda serial: {"serial": serial}
            )

            missing = json.loads(module._call_meraki_method_internal(
                "devices", "getDeviceLldpCdp", {}))
            ok = json.loads(module._call_meraki_method_internal(
                "devices", "getDeviceLldpCdp", {"serial": "Q2XX-AAAA-BBBB"}))

        self.assertEqual("Invalid parameters", missing["error"])
        self.assertEqual(["serial"], missing["missing_required_parameters"])
        self.assertEqual([], missing["received_parameters"])
        self.assertIn('parameters={"serial": "..."}', missing["hint"])
        self.assertEqual({"serial": "Q2XX-AAAA-BBBB"}, ok)


@contextmanager
def fake_meraki_module():
    fake_meraki = types.ModuleType("meraki")
    fake_meraki.DashboardAPI = FakeDashboardAPI
    fake_meraki.exceptions = types.SimpleNamespace(APIError=type("APIError", (Exception,), {}))
    sentinel = object()
    original = sys.modules.get("meraki", sentinel)
    sys.modules["meraki"] = fake_meraki
    try:
        yield
    finally:
        if original is sentinel:
            sys.modules.pop("meraki", None)
        else:
            sys.modules["meraki"] = original


def fastmcp_available():
    try:
        import mcp.server.fastmcp  # noqa: F401
    except ImportError:
        return False
    return True


@unittest.skipUnless(fastmcp_available(), "mcp.server.fastmcp is not installed")
class ToolSchemaTests(unittest.TestCase):
    def test_null_default_arguments_accept_null(self):
        for filename in ["meraki-mcp.py", "meraki-mcp-dynamic.py"]:
            with self.subTest(filename=filename), patch.dict(
                os.environ, {"MERAKI_API_KEY": "dummy", "ENABLE_FILE_CACHING": "false"}, clear=True
            ), fake_meraki_module():
                module = load_script_module(filename, f"test_schema_{filename.replace('-', '_')}")
                for tool in module.mcp._tool_manager.list_tools():
                    for name, prop in tool.parameters.get("properties", {}).items():
                        if "default" in prop and prop["default"] is None:
                            types_allowed = [prop.get("type")] + [
                                option.get("type") for option in prop.get("anyOf", [])
                            ]
                            self.assertIn("null", types_allowed, f"{tool.name}.{name}")

    def test_explicit_null_reaches_tool(self):
        with patch.dict(
            os.environ, {"MERAKI_API_KEY": "dummy", "ENABLE_FILE_CACHING": "false"}, clear=True
        ), fake_meraki_module():
            module = load_script_module("meraki-mcp-dynamic.py", "test_schema_null_call")
            asyncio.run(module.mcp.call_tool("getOrganizationNetworks", {"organizationId": None}))

        self.assertEqual("getOrganizationNetworks", module.dashboard.calls[-1]["method"])


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
        self.assertEqual(config.DEFAULT_MERAKI_CALLER, dashboard_cls.instances[0].kwargs["caller"])

    def test_manual_dashboard_receives_caller_override(self):
        with patch.dict(
            os.environ,
            {"MERAKI_API_KEY": "dummy", "MERAKI_PYTHON_SDK_CALLER": "InventoryTool ExampleOrg"},
            clear=True,
        ), fake_runtime_modules() as dashboard_cls:
            load_script_module("meraki-mcp.py", "test_manual_caller")
            self.assertEqual("InventoryTool ExampleOrg", dashboard_cls.instances[0].kwargs["caller"])

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

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
    fake_server = types.ModuleType("meraki_mcp_server")
    fake_server.MerakiMCP = FakeFastMCP
    fake_fastmcp.FastMCP = FakeFastMCP

    fake_pydantic = types.ModuleType("pydantic")
    fake_pydantic.BaseModel = FakeBaseModel
    fake_pydantic.Field = fake_field

    module_overrides = {
        "meraki": fake_meraki,
        "meraki_mcp_server": fake_server,
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

    def test_serialized_budget_includes_escape_sequences_parameters_and_cache_metadata(self):
        rows = ['🟢\n"\\' * 3000]
        for budget in (7, 50, 500, 5000):
            with self.subTest(budget=budget), dynamic_module(
                "test_serialized_budget", MAX_RESPONSE_TOKENS=str(budget)
            ) as (module, directory):
                module.dashboard.networks.getNetwork = lambda networkId, perPage: rows
                params = {"networkId": "a" * 30000, "perPage": 5000}
                for _ in range(2):
                    text = module._call_meraki_method_internal("networks", "getNetwork", params)
                    self.assertLessEqual(len(text), 4 * budget)
                    summary = json.loads(text)
                    self.assertTrue(summary["_response_truncated"])
                    if budget >= 50:
                        self.assertEqual(rows, module.load_response_from_file(summary["_full_response_cached"]))
                    if budget >= 500:
                        self.assertIn("_preview", summary)
                files = json.loads(asyncio.run(module.list_cached_responses()))["files"]
                self.assertEqual(1, len(files))
                self.assertEqual(rows, module.load_response_from_file(files[0]["filepath"]))

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


class DocumentationTests(unittest.TestCase):
    """Catch the doc drift that has happened before: renamed tools and stale counts."""

    STALE = [
        "list_available_tools",
        "search_tools",
        "get_tool_info",
        "organizations_getOrganization",
        "networks_getNetwork",
        "update_meraki.py",
        "804",
        "40 curated",
        "40 hand-coded",
    ]

    def test_docs_do_not_mention_removed_tools_or_old_counts(self):
        found = []
        for path in sorted(ROOT.glob("*.md")) + [ROOT / "entrypoint.sh", ROOT / "inspect_tools.py"]:
            text = path.read_text()
            found += [f"{path.name}: {term}" for term in self.STALE if term in text]
        self.assertEqual([], found)

    def test_documented_tool_counts_match_the_servers(self):
        import re

        manual = (ROOT / "meraki-mcp.py").read_text()
        manual_tools = len(re.findall(r"^@(?:mcp\.tool\(\)|threaded_tool)$", manual, flags=re.M))
        dynamic = (ROOT / "meraki-mcp-dynamic.py").read_text()
        dynamic_tools = len(re.findall(r"^@mcp\.tool\(\)$", dynamic, flags=re.M))

        self.assertIn(f"**{manual_tools} curated tools**", (ROOT / "README.md").read_text())
        comparison = (ROOT / "COMPARISON.md").read_text()
        self.assertIn(f"{manual_tools} hand-written tools", comparison)
        self.assertIn(f"{dynamic_tools} tools:", comparison)

    def test_sdk_sections_cover_every_section_of_the_installed_sdk(self):
        try:
            import meraki
        except ImportError:
            self.skipTest("Meraki SDK is not installed")

        dashboard = meraki.DashboardAPI(api_key="dummy", suppress_logging=True)
        sdk_sections = {
            name for name in dir(dashboard)
            if not name.startswith("_") and hasattr(getattr(dashboard, name), "_session")
        }
        self.assertEqual([], sorted(sdk_sections - set(config.SDK_SECTIONS)))
        self.assertEqual([], sorted(set(config.SDK_SECTIONS) - sdk_sections))


class DependencyLockTests(unittest.TestCase):
    """requirements.txt is the lockfile generated from pyproject.toml; keep them in step."""

    @classmethod
    def setUpClass(cls):
        import tomllib

        try:
            from packaging.requirements import Requirement
            from packaging.utils import canonicalize_name
        except ImportError:
            raise unittest.SkipTest("packaging is not installed")

        cls.canonicalize_name = staticmethod(canonicalize_name)
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        cls.project = project
        cls.direct = [Requirement(spec) for spec in project["dependencies"]]
        cls.lock_text = (ROOT / "requirements.txt").read_text()
        cls.locked = {}
        for line in cls.lock_text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                requirement = Requirement(line)
                cls.locked[canonicalize_name(requirement.name)] = requirement

    def test_lockfile_is_generated_from_pyproject(self):
        self.assertIn("uv pip compile pyproject.toml", self.lock_text.splitlines()[1])

    def test_every_locked_package_is_pinned_to_one_version(self):
        unpinned = sorted(
            name for name, requirement in self.locked.items()
            if [spec.operator for spec in requirement.specifier] != ["=="]
        )
        self.assertEqual([], unpinned)

    def test_direct_dependencies_are_locked_within_their_allowed_range(self):
        for requirement in self.direct:
            name = self.canonicalize_name(requirement.name)
            with self.subTest(dependency=name):
                self.assertIn(name, self.locked)
                pinned = next(iter(self.locked[name].specifier)).version
                self.assertTrue(
                    requirement.specifier.contains(pinned, prereleases=True),
                    f"requirements.txt pins {name}=={pinned}, outside '{requirement.specifier}' "
                    "from pyproject.toml; regenerate the lockfile",
                )

    def test_project_metadata_is_filled_in(self):
        self.assertNotIn("Add your description", self.project["description"])
        self.assertEqual((ROOT / ".python-version").read_text().strip(),
                         self.project["requires-python"].lstrip(">="))


@contextmanager
def dynamic_module(name, **env):
    """Load the dynamic server with fake SDK modules and a temporary cache directory."""
    import tempfile

    with tempfile.TemporaryDirectory() as cache_dir:
        environ = {"MERAKI_API_KEY": "dummy", "RESPONSE_CACHE_DIR": cache_dir}
        environ.update(env)
        with patch.dict(os.environ, environ, clear=True), fake_runtime_modules():
            yield load_script_module("meraki-mcp-dynamic.py", name), Path(cache_dir)


class MemoryCacheBoundTests(unittest.TestCase):
    def test_cache_evicts_oldest_entries_beyond_the_cap(self):
        with dynamic_module("test_cache_cap", CACHE_MAX_ITEMS="3") as (module, _):
            cache = module.SimpleCache()
            for i in range(5):
                cache.set(f"k{i}", i)
            self.assertEqual(["k2", "k3", "k4"], list(cache.cache))
            self.assertEqual(list(cache.cache), list(cache.timestamps))
            self.assertIsNone(cache.get("k0"))
            self.assertEqual(4, cache.get("k4"))

            cache.set("k2", "refreshed")
            cache.set("k5", 5)
            self.assertEqual(["k4", "k2", "k5"], list(cache.cache))
            self.assertEqual(3, cache.stats()["total_items"])
            self.assertEqual(3, cache.stats()["max_items"])

    def test_expired_entries_are_purged_when_storing(self):
        with dynamic_module("test_cache_expiry", CACHE_TTL_SECONDS="100") as (module, _):
            cache = module.SimpleCache()
            with patch.object(module.time, "monotonic", return_value=1000.0):
                cache.set("old1", 1)
                cache.set("old2", 2)
            with patch.object(module.time, "monotonic", return_value=1099.0):
                self.assertEqual(1, cache.get("old1"))
            with patch.object(module.time, "monotonic", return_value=1100.0):
                self.assertIsNone(cache.get("old1"))
                cache.set("new", 3)
                self.assertEqual(["new"], list(cache.cache))
                self.assertEqual(["new"], list(cache.timestamps))

    def test_zero_cap_means_unlimited(self):
        with dynamic_module("test_cache_unlimited", CACHE_MAX_ITEMS="0") as (module, _):
            cache = module.SimpleCache()
            for i in range(1000):
                cache.set(f"k{i}", i)
            self.assertEqual(1000, cache.stats()["total_items"])


class FileCacheRetentionTests(unittest.TestCase):
    @staticmethod
    def _write(directory, label, size, age_hours):
        """Create an authentic legacy response with a known size and modification time."""
        import hashlib
        import time

        timestamp = "20250119_143022"
        params = {"networkId": label}
        digest = hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]
        path = directory / f"networks_getNetwork_{digest}_{timestamp}.json"
        envelope = {"cached_at": timestamp, "section": "networks", "method": "getNetwork",
                    "parameters": params, "data": ""}
        content = json.dumps(envelope, indent=2)
        path.write_text(content.ljust(size), encoding="utf-8")
        stamp = time.time() - age_hours * 3600
        os.utime(path, (stamp, stamp))
        return path

    def test_startup_removes_files_older_than_the_max_age(self):
        import tempfile

        with tempfile.TemporaryDirectory() as cache_dir:
            directory = Path(cache_dir)
            old = self._write(directory, "old.json", 10, age_hours=30)
            fresh = self._write(directory, "fresh.json", 10, age_hours=1)
            other = directory / "project-settings.json"
            other.write_text('{"theme":"light"}')
            lookalike = directory / "networks_getNetwork_12345678_20250119_143022.json"
            lookalike.write_text('{"data":"user settings"}')
            for path in (other, lookalike):
                os.utime(path, (0, 0))
            with patch.dict(
                os.environ,
                {"MERAKI_API_KEY": "dummy", "RESPONSE_CACHE_DIR": cache_dir},
                clear=True,
            ), fake_runtime_modules():
                module = load_script_module("meraki-mcp-dynamic.py", "test_file_cache_startup")
            self.assertFalse(old.exists())
            self.assertTrue(fresh.exists())
            listed = json.loads(asyncio.run(module.list_cached_responses()))["files"]
            self.assertEqual([fresh.name], [item["filename"] for item in listed])
            cleared = json.loads(asyncio.run(module.clear_cached_files(older_than_hours=0)))
            self.assertEqual(1, cleared["deleted_count"])
            self.assertTrue(other.exists())
            self.assertTrue(lookalike.exists())

    def test_size_quota_removes_oldest_files_first(self):
        with dynamic_module(
            "test_file_cache_quota", RESPONSE_CACHE_MAX_MB="0.001", RESPONSE_CACHE_MAX_AGE_HOURS="0"
        ) as (module, directory):
            oldest = self._write(directory, "a.json", 500, age_hours=50)
            middle = self._write(directory, "b.json", 500, age_hours=5)
            newest = self._write(directory, "c.json", 500, age_hours=1)

            unrelated = directory / "inventory.json"
            unrelated.write_text(json.dumps({"notes": "x" * 3000}))
            removed = module.prune_response_cache()
            self.assertTrue(unrelated.exists())

            self.assertEqual({"expired": 0, "over_quota": 1}, removed)
            self.assertFalse(oldest.exists())
            self.assertTrue(middle.exists())
            self.assertTrue(newest.exists())

    def test_limits_of_zero_disable_pruning(self):
        with dynamic_module(
            "test_file_cache_disabled", RESPONSE_CACHE_MAX_MB="0", RESPONSE_CACHE_MAX_AGE_HOURS="0"
        ) as (module, directory):
            old = self._write(directory, "a.json", 5000, age_hours=5000)
            self.assertEqual({"expired": 0, "over_quota": 0}, module.prune_response_cache())
            self.assertTrue(old.exists())

    def test_repeat_read_regenerates_file_evicted_by_quota(self):
        from unittest.mock import Mock

        with dynamic_module("test_file_cache_refetch", MAX_RESPONSE_TOKENS="100",
                            RESPONSE_CACHE_MAX_MB="0.002") as (module, directory):
            get_network = Mock(side_effect=lambda networkId: {"id": networkId, "data": "x" * 1800})
            module.dashboard.networks.getNetwork = get_network

            def read(network):
                return json.loads(module._call_meraki_method_internal(
                    "networks", "getNetwork", {"networkId": network}))

            first = read("A")
            read("B")
            self.assertFalse(Path(first["_full_response_cached"]).exists())
            renewed = read("A")
            self.assertNotIn("_from_cache", renewed)
            self.assertEqual("A", module.load_response_from_file(renewed["_full_response_cached"])["id"])
            self.assertEqual(renewed["_full_response_cached"], read("A")["_full_response_cached"])
            self.assertEqual(3, get_network.call_count)

    def test_unwritable_cache_directory_disables_file_caching_instead_of_crashing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as parent:
            blocker = Path(parent) / "not-a-directory"
            blocker.write_text("x")
            with patch.dict(
                os.environ,
                {"MERAKI_API_KEY": "dummy", "MAX_RESPONSE_TOKENS": "50",
                 "RESPONSE_CACHE_DIR": str(blocker / "cache")},
                clear=True,
            ), fake_runtime_modules():
                module = load_script_module("meraki-mcp-dynamic.py", "test_file_cache_unwritable")
                self.assertFalse(module.ENABLE_FILE_CACHING)
                rows = [{"serial": f"Q2XX-{i:04d}"} for i in range(200)]
                module.dashboard.networks = types.SimpleNamespace(getNetworkDevices=lambda networkId: rows)
                response = json.loads(module._call_meraki_method_internal(
                    "networks", "getNetworkDevices", {"networkId": "N_1"}))
                self.assertEqual(rows, response)
                self.assertFalse(json.loads(asyncio.run(module.get_mcp_config()))["file_caching_enabled"])

    def test_existing_unwritable_cache_directory_disables_file_caching(self):
        if os.name != "posix" or os.geteuid() == 0:
            self.skipTest("needs a non-root POSIX user to observe directory permissions")
        import tempfile

        with tempfile.TemporaryDirectory() as parent:
            cache_dir = Path(parent) / "cache"
            cache_dir.mkdir(mode=0o500)
            try:
                with patch.dict(os.environ, {"MERAKI_API_KEY": "dummy", "RESPONSE_CACHE_DIR": str(cache_dir)},
                                clear=True), fake_runtime_modules():
                    module = load_script_module("meraki-mcp-dynamic.py", "test_file_cache_readonly_dir")
                    self.assertFalse(module.ENABLE_FILE_CACHING)
            finally:
                cache_dir.chmod(0o700)

    def test_failed_save_returns_the_full_response(self):
        with dynamic_module("test_file_cache_save_fails", MAX_RESPONSE_TOKENS="50") as (module, _):
            rows = [{"serial": f"Q2XX-{i:04d}"} for i in range(200)]
            module.dashboard.networks = types.SimpleNamespace(getNetworkDevices=lambda networkId: rows)
            with patch.object(module, "save_response_to_file", side_effect=PermissionError("denied")):
                response = json.loads(module._call_meraki_method_internal(
                    "networks", "getNetworkDevices", {"networkId": "N_1"}))
        self.assertEqual(rows, response)

    def test_saved_response_is_private_and_survives_its_own_prune(self):
        with dynamic_module(
            "test_file_cache_save", RESPONSE_CACHE_MAX_MB="0.0001", MAX_RESPONSE_TOKENS="50"
        ) as (module, directory):
            stale = self._write(directory, "stale.json", 2000, age_hours=2)
            rows = [{"serial": f"Q2XX-{i:04d}"} for i in range(200)]
            module.dashboard.networks = types.SimpleNamespace(getNetworkDevices=lambda networkId: rows)

            response = json.loads(module._call_meraki_method_internal(
                "networks", "getNetworkDevices", {"networkId": "N_1"}))

            saved = Path(response["_full_response_cached"])
            self.assertTrue(saved.exists())
            self.assertFalse(stale.exists())
            self.assertEqual(rows, module.load_response_from_file(str(saved)))
            if os.name == "posix":
                self.assertEqual(0o600, saved.stat().st_mode & 0o777)


class DiscoveryToolTests(unittest.TestCase):
    INDEX = {
        "wireless": ["getNetworkWirelessSsid", "getNetworkWirelessSsids", "updateNetworkWirelessSsid"],
        "switch": ["getDeviceSwitchPorts", "updateDeviceSwitchPort"],
        "appliance": [f"getNetworkApplianceThing{i}" for i in range(120)],
    }

    @contextmanager
    def _module(self, name):
        with dynamic_module(name) as (module, _):
            module._METHOD_INDEX = self.INDEX
            yield module

    def test_list_all_methods_without_section_returns_counts_only(self):
        with self._module("test_discovery_summary") as module:
            summary = json.loads(asyncio.run(module.list_all_methods()))
            section = json.loads(asyncio.run(module.list_all_methods("switch")))
            missing = json.loads(asyncio.run(module.list_all_methods("nope")))

        self.assertEqual({"wireless": 3, "switch": 2, "appliance": 120}, summary["sections"])
        self.assertEqual(125, summary["total_methods"])
        self.assertIn("search_methods", summary["usage"])
        self.assertEqual(self.INDEX["switch"], section["methods"])
        self.assertEqual(2, section["total_methods"])
        self.assertIn("error", missing)

    def test_search_requires_all_terms_and_can_filter_by_section(self):
        with self._module("test_discovery_search") as module:
            both = json.loads(asyncio.run(module.search_methods("update SSID")))
            ports = json.loads(asyncio.run(module.search_methods("port")))
            scoped = json.loads(asyncio.run(module.search_methods("get", section="switch")))
            empty = json.loads(asyncio.run(module.search_methods("   ")))
            bad_section = json.loads(asyncio.run(module.search_methods("get", section="nope")))

        self.assertEqual({"wireless": ["updateNetworkWirelessSsid"]}, both["results"])
        self.assertEqual(1, both["total_matches"])
        self.assertNotIn("_truncated", both)
        self.assertEqual({"switch": self.INDEX["switch"]}, ports["results"])
        self.assertEqual({"switch": ["getDeviceSwitchPorts"]}, scoped["results"])
        self.assertIn("error", empty)
        self.assertIn("error", bad_section)

    def test_search_results_are_capped_and_report_the_total(self):
        with self._module("test_discovery_limit") as module:
            default = json.loads(asyncio.run(module.search_methods("get")))
            small = json.loads(asyncio.run(module.search_methods("get", limit=3)))
            huge = json.loads(asyncio.run(module.search_methods("get", limit=100000)))

        def count(response):
            return sum(len(v) for v in response["results"].values())

        self.assertEqual(123, default["total_matches"])
        self.assertEqual(module.SEARCH_DEFAULT_LIMIT, count(default))
        self.assertTrue(default["_truncated"])
        self.assertEqual(50, default["_returned"])
        self.assertEqual({"wireless": ["getNetworkWirelessSsid", "getNetworkWirelessSsids"],
                          "switch": ["getDeviceSwitchPorts"]}, small["results"])
        self.assertEqual(123, count(huge))
        self.assertNotIn("_truncated", huge)


class CompactOutputTests(unittest.TestCase):
    def test_to_json_is_compact_and_round_trips(self):
        data = {"a": [1, 2, {"b": None}], "c": "x y", "d": True}
        text = config.to_json(data)
        self.assertEqual('{"a":[1,2,{"b":null}],"c":"x y","d":true}', text)
        self.assertEqual(data, json.loads(text))

    def test_guard_payloads_are_compact(self):
        blocked = config.guard_write_operation("deleteNetwork", read_only_mode=True)
        self.assertNotIn("\n", blocked)
        self.assertEqual("deleteNetwork", json.loads(blocked)["method"])

    def test_dynamic_responses_are_compact_and_within_the_token_budget(self):
        rows = [{"serial": f"Q2XX-{i:04d}", "name": f"ap{i}", "tags": ["a", "b"]} for i in range(40)]
        compact_chars = len(config.to_json(rows))
        # Budget sits between the compact and the indented size of this response
        self.assertLess(compact_chars, len(json.dumps(rows, indent=2)) - 400)
        budget_tokens = compact_chars // 4 + 50
        with patch.dict(
            os.environ,
            {"MERAKI_API_KEY": "dummy", "ENABLE_FILE_CACHING": "true",
             "MAX_RESPONSE_TOKENS": str(budget_tokens)},
            clear=True,
        ), fake_runtime_modules():
            import tempfile

            with tempfile.TemporaryDirectory() as cache_dir, patch.dict(
                os.environ, {"RESPONSE_CACHE_DIR": cache_dir}
            ):
                module = load_script_module("meraki-mcp-dynamic.py", "test_dynamic_compact")
                module.dashboard.networks = types.SimpleNamespace(getNetworkDevices=lambda networkId: rows)
                raw = module._call_meraki_method_internal(
                    "networks", "getNetworkDevices", {"networkId": "N_1"})
                error = module._call_meraki_method_internal("nope", "getX", {})
                info = asyncio.run(module.get_mcp_config())

        self.assertEqual(rows, json.loads(raw))
        self.assertEqual(config.to_json(rows), raw)
        self.assertLessEqual(module.estimate_token_count(raw), budget_tokens)
        for text in (raw, error, info):
            self.assertNotIn("\n", text)

    def test_manual_responses_are_compact(self):
        with patch.dict(
            os.environ, {"MERAKI_API_KEY": "dummy", "MERAKI_ORG_ID": "1"}, clear=True
        ), fake_runtime_modules():
            module = load_script_module("meraki-mcp.py", "test_manual_compact")
            module.dashboard.networks.getNetwork = lambda network_id: {"id": network_id, "tags": ["a"]}
            raw = module.get_network_details("N_1")
        self.assertEqual('{"id":"N_1","tags":["a"]}', raw)


class HttpAuthTests(unittest.TestCase):
    TOKEN = "t" * 40

    @staticmethod
    def _call(middleware, scope):
        """Run an ASGI app on a scope; return (sent messages, whether the inner app ran)."""
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        asyncio.run(middleware(scope, receive, send))
        return sent

    def _middleware(self):
        calls = []

        async def inner(scope, receive, send):
            calls.append(scope["type"])
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        return config.BearerTokenMiddleware(inner, self.TOKEN), calls

    def _http(self, *headers):
        return {"type": "http", "method": "POST", "path": "/mcp", "headers": list(headers)}

    def test_requests_without_the_right_token_are_rejected(self):
        for headers in [
            (),
            ((b"authorization", b"Bearer wrong"),),
            ((b"authorization", b"Basic " + self.TOKEN.encode()),),
            ((b"authorization", self.TOKEN.encode()),),
            ((b"authorization", b"Bearer " + self.TOKEN.encode() + b"x"),),
            ((b"x-api-key", self.TOKEN.encode()),),
        ]:
            with self.subTest(headers=headers):
                middleware, calls = self._middleware()
                sent = self._call(middleware, self._http(*headers))
                self.assertEqual([], calls)
                self.assertEqual(401, sent[0]["status"])
                self.assertIn((b"www-authenticate", b'Bearer realm="meraki-magic-mcp"'), sent[0]["headers"])
                self.assertEqual("unauthorized", json.loads(sent[1]["body"])["error"])

    def test_requests_with_the_token_reach_the_app(self):
        for value in [b"Bearer ", b"bearer ", b"BEARER  "]:
            with self.subTest(value=value):
                middleware, calls = self._middleware()
                sent = self._call(middleware, self._http((b"Authorization", value + self.TOKEN.encode())))
                self.assertEqual(["http"], calls)
                self.assertEqual(200, sent[0]["status"])

    def test_lifespan_passes_through_and_websockets_are_closed(self):
        middleware, calls = self._middleware()
        self._call(middleware, {"type": "lifespan"})
        self.assertEqual(["lifespan"], calls)

        middleware, calls = self._middleware()
        sent = self._call(middleware, {"type": "websocket", "path": "/mcp", "headers": []})
        self.assertEqual([], calls)
        self.assertEqual([{"type": "websocket.close", "code": 1008}], sent)

    def test_empty_token_is_rejected(self):
        with self.assertRaises(ValueError):
            config.BearerTokenMiddleware(lambda *args: None, "")

    def test_auth_token_is_read_from_the_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(config.get_auth_token())
        with patch.dict(os.environ, {"MCP_AUTH_TOKEN": "   "}, clear=True):
            self.assertIsNone(config.get_auth_token())
        with patch.dict(os.environ, {"MCP_AUTH_TOKEN": " abc "}, clear=True):
            self.assertEqual("abc", config.get_auth_token())

    def test_security_warnings(self):
        self.assertEqual([], config.http_security_warnings("127.0.0.1", None))
        self.assertEqual([], config.http_security_warnings("0.0.0.0", self.TOKEN))
        exposed = config.http_security_warnings("0.0.0.0", None)
        self.assertEqual(1, len(exposed))
        self.assertIn("without authentication", exposed[0])
        weak = config.http_security_warnings("127.0.0.1", "short")
        self.assertEqual(1, len(weak))
        self.assertIn("shorter than", weak[0])

    def test_both_launchers_secure_http_and_sse_for_each_server(self):
        if not fastmcp_available():
            self.skipTest("mcp is not installed")
        from fastmcp.cli.run import run_v1_server_async
        from starlette.testclient import TestClient

        initialize = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                       "clientInfo": {"name": "test", "version": "1"}},
        }
        accept = {"Accept": "application/json, text/event-stream"}
        for filename in ("meraki-mcp.py", "meraki-mcp-dynamic.py"):
            for transport in ("http", "sse"):
                for launcher in ("module", "cli"):
                    with self.subTest(filename=filename, transport=transport, launcher=launcher), patch.dict(
                        os.environ,
                        {"MERAKI_API_KEY": "dummy", "MCP_AUTH_TOKEN": self.TOKEN,
                         "MCP_TRANSPORT": transport if launcher == "module" else "stdio",
                         "ENABLE_FILE_CACHING": "false"}, clear=True
                    ), fake_meraki_module():
                        module = load_script_module(filename, "test_transport_server")
                        if launcher == "cli":
                            # Exercise FastMCP's real launcher up to handing its ASGI app to uvicorn.
                            with patch("uvicorn.Server.serve", autospec=True) as serve:
                                asyncio.run(run_v1_server_async(module.mcp, transport=transport))
                            app = serve.await_args.args[0].config.app
                        else:
                            app = module.app
                        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
                            if transport == "http":
                                self.assertEqual(401, client.post("/mcp", json=initialize, headers=accept).status_code)
                                client.headers["Authorization"] = f"Bearer {self.TOKEN}"
                                response = client.post("/mcp", json=initialize, headers=accept)
                                self.assertEqual(200, response.status_code)
                                self.assertIn('"serverInfo"', response.text)
                            else:
                                self.assertEqual(401, client.get("/sse").status_code)
                                self.assertEqual(401, client.post("/messages/").status_code)
                                client.headers["Authorization"] = f"Bearer {self.TOKEN}"
                                # The SSE message handler requires a session ID after authentication.
                                self.assertEqual(400, client.post("/messages/").status_code)


class DeploymentDefaultsTests(unittest.TestCase):
    def test_container_runs_as_an_unprivileged_user(self):
        import re

        dockerfile = (ROOT / "Dockerfile").read_text()
        users = re.findall(r"^USER\s+(\S+)", dockerfile, flags=re.M)
        self.assertTrue(users, "Dockerfile must set USER")
        self.assertNotIn(users[-1], ("root", "0"))
        self.assertIn("meraki_mcp_config.py", dockerfile)

    def test_compose_publishes_on_loopback_by_default_and_passes_the_token(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        self.assertIn('"${MCP_PUBLISH_HOST:-127.0.0.1}:8000:8000"', compose)
        self.assertIn("MCP_AUTH_TOKEN: ${MCP_AUTH_TOKEN:-}", compose)
        for name, default in (("RESPONSE_CACHE_MAX_AGE_HOURS", 24), ("RESPONSE_CACHE_MAX_MB", 100)):
            self.assertIn(f"{name}: ${{{name}:-{default}}}", compose)

    def test_documented_docker_run_commands_publish_on_loopback(self):
        import re

        install = (ROOT / "INSTALL.md").read_text()
        self.assertEqual([], re.findall(r"-p 8000:8000", install))


class ManualServerThreadingTests(unittest.TestCase):
    def test_every_manual_tool_is_registered_as_async(self):
        if not fastmcp_available():
            self.skipTest("mcp is not installed")
        with patch.dict(os.environ, {"MERAKI_API_KEY": "dummy"}, clear=True), fake_meraki_module():
            module = load_script_module("meraki-mcp.py", "test_manual_async_tools")
            tools = module.mcp._tool_manager.list_tools()
            self.assertGreater(len(tools), 50)
            blocking = sorted(tool.name for tool in tools if not tool.is_async)
            self.assertEqual([], blocking)

    def test_sync_tool_runs_off_the_event_loop_thread(self):
        import threading

        if not fastmcp_available():
            self.skipTest("mcp is not installed")
        with patch.dict(os.environ, {"MERAKI_API_KEY": "dummy"}, clear=True), fake_meraki_module():
            module = load_script_module("meraki-mcp.py", "test_manual_threaded_call")
            sdk_threads = []

            def get_network(network_id):
                sdk_threads.append(threading.get_ident())
                return {"id": network_id}

            module.dashboard.networks.getNetwork = get_network

            async def call():
                loop_thread = threading.get_ident()
                result = await module.mcp.call_tool("get_network_details", {"network_id": "N_1"})
                return loop_thread, result

            loop_thread, result = asyncio.run(call())

        self.assertEqual(1, len(sdk_threads))
        self.assertNotEqual(loop_thread, sdk_threads[0])
        self.assertIn("N_1", json.dumps(result, default=str))
        # The function stays directly callable and synchronous
        self.assertEqual({"id": "N_2"}, json.loads(module.get_network_details("N_2")))


class DynamicServerCacheTests(unittest.TestCase):
    def test_cache_hit_does_not_modify_the_stored_entry(self):
        with patch.dict(
            os.environ, {"MERAKI_API_KEY": "dummy", "ENABLE_FILE_CACHING": "false"}, clear=True
        ), fake_runtime_modules():
            module = load_script_module("meraki-mcp-dynamic.py", "test_dynamic_cache_copy")
            result = {"id": "N_1", "name": "net"}
            calls = []
            module.dashboard.networks = types.SimpleNamespace(
                getNetwork=lambda networkId: calls.append(networkId) or result
            )

            first = json.loads(module._call_meraki_method_internal("networks", "getNetwork", {"networkId": "N_1"}))
            second = json.loads(module._call_meraki_method_internal("networks", "getNetwork", {"networkId": "N_1"}))
            third = json.loads(module._call_meraki_method_internal("networks", "getNetwork", {"networkId": "N_1"}))

            self.assertEqual(["N_1"], calls)
            self.assertEqual({"id": "N_1", "name": "net"}, first)
            self.assertEqual({"id": "N_1", "name": "net", "_from_cache": True}, second)
            self.assertEqual(second, third)
            self.assertEqual({"id": "N_1", "name": "net"}, result)
            self.assertEqual([{"id": "N_1", "name": "net"}], list(module.cache.cache.values()))

    def test_pagination_notice_does_not_modify_the_sdk_result(self):
        with patch.dict(
            os.environ, {"MERAKI_API_KEY": "dummy", "ENABLE_FILE_CACHING": "false"}, clear=True
        ), fake_runtime_modules():
            module = load_script_module("meraki-mcp-dynamic.py", "test_dynamic_pagination_copy")
            result = {"items": [1, 2, 3]}
            seen = []
            module.dashboard.networks = types.SimpleNamespace(
                getNetworkEvents=lambda networkId, perPage: seen.append(perPage) or result
            )

            response = json.loads(module._call_meraki_method_internal(
                "networks", "getNetworkEvents", {"networkId": "N_1", "perPage": 5000}))
            cached = json.loads(module._call_meraki_method_internal(
                "networks", "getNetworkEvents", {"networkId": "N_1", "perPage": 5000}))

            self.assertEqual([module.MAX_PER_PAGE], seen)
            self.assertTrue(response["_pagination_limited"])
            self.assertEqual([1, 2, 3], response["items"])
            self.assertTrue(cached["_pagination_limited"])
            self.assertTrue(cached["_from_cache"])
            self.assertEqual({"items": [1, 2, 3]}, result)


class ManualServerSdkCompatibilityTests(unittest.TestCase):
    def test_every_manual_tool_calls_a_method_the_installed_sdk_provides(self):
        import re

        try:
            import meraki
        except ImportError:
            self.skipTest("Meraki SDK is not installed")

        dashboard = meraki.DashboardAPI(api_key="dummy", suppress_logging=True)
        source = (ROOT / "meraki-mcp.py").read_text()
        calls = set(re.findall(r"dashboard\.(\w+)\.(\w+)", source))
        self.assertGreater(len(calls), 50)
        missing = sorted(
            f"{section}.{method}"
            for section, method in calls
            if not callable(getattr(getattr(dashboard, section, None), method, None))
        )
        self.assertEqual([], missing)

    def test_guarded_method_names_exist_in_the_installed_sdk(self):
        import re

        try:
            import meraki
        except ImportError:
            self.skipTest("Meraki SDK is not installed")

        dashboard = meraki.DashboardAPI(api_key="dummy", suppress_logging=True)
        sdk_methods = {
            method
            for section in dir(dashboard)
            if not section.startswith("_") and hasattr(getattr(dashboard, section), "_session")
            for method in dir(getattr(dashboard, section))
        }
        source = (ROOT / "meraki-mcp.py").read_text()
        guarded = set(re.findall(r'_guard_write\("(\w+)"', source))
        self.assertEqual([], sorted(guarded - sdk_methods))


class ManualServerFixedToolTests(unittest.TestCase):
    def _load(self, name, env=None):
        environ = {"MERAKI_API_KEY": "dummy", "READ_ONLY_MODE": "false"}
        environ.update(env or {})
        return patch.dict(os.environ, environ, clear=True)

    def test_device_status_and_uplink_filter_org_wide_results_by_serial(self):
        with self._load("a", {"MERAKI_ORG_ID": "111"}), fake_runtime_modules():
            module = load_script_module("meraki-mcp.py", "test_manual_device_status")
            rows = [{"serial": "Q2XX-OTHER", "status": "offline"}, {"serial": "Q2XX-1", "status": "online"}]
            seen = []

            def fake(organization_id, **kwargs):
                seen.append((organization_id, kwargs))
                return rows

            module.dashboard.organizations.getOrganizationDevicesStatuses = fake
            module.dashboard.organizations.getOrganizationUplinksStatuses = fake

            self.assertEqual(rows[1], json.loads(module.get_device_status("Q2XX-1")))
            self.assertEqual(rows[1], json.loads(module.get_device_uplink("Q2XX-1", org_id="222")))
            missing = json.loads(module.get_device_uplink("Q2XX-NONE"))

        self.assertEqual(("111", {"total_pages": "all", "serials": ["Q2XX-1"]}), seen[0])
        self.assertEqual("222", seen[1][0])
        self.assertEqual("Q2XX-NONE", missing["serial"])
        self.assertIn("error", missing)

    def test_device_status_looks_up_organization_when_not_configured(self):
        with self._load("b"), fake_runtime_modules():
            module = load_script_module("meraki-mcp.py", "test_manual_device_org_lookup")
            module.dashboard.devices.getDevice = lambda serial: {"serial": serial, "networkId": "N_1"}
            module.dashboard.networks.getNetwork = lambda network_id: {"id": network_id, "organizationId": "999"}
            seen = []
            module.dashboard.organizations.getOrganizationDevicesStatuses = (
                lambda organization_id, **kwargs: seen.append(organization_id) or [{"serial": "Q2XX-1"}]
            )
            self.assertEqual({"serial": "Q2XX-1"}, json.loads(module.get_device_status("Q2XX-1")))
        self.assertEqual(["999"], seen)

    def test_remaining_fixed_tools_call_current_sdk_methods(self):
        with self._load("c", {"MERAKI_ORG_ID": "111"}), fake_runtime_modules():
            module = load_script_module("meraki-mcp.py", "test_manual_fixed_tools")
            module.get_organization_status()
            module.get_switch_vlans("N_1")
            module.get_security_center("N_1")
            module.create_switch_vlan("N_1", 20, "Voice", subnet="10.0.20.0/24", appliance_ip="10.0.20.1")
            calls = module.dashboard.calls

        self.assertEqual(
            [
                ("organizations", "getOrganizationDevicesStatusesOverview"),
                ("appliance", "getNetworkApplianceVlans"),
                ("appliance", "getNetworkApplianceSecurityEvents"),
                ("appliance", "createNetworkApplianceVlan"),
            ],
            [(call["section"], call["method"]) for call in calls],
        )
        self.assertEqual({"timespan": 86400, "perPage": 100}, calls[2]["kwargs"])
        self.assertEqual(("N_1", "20", "Voice"), calls[3]["args"])
        self.assertEqual({"subnet": "10.0.20.0/24", "applianceIp": "10.0.20.1"}, calls[3]["kwargs"])

    def test_create_vlan_is_blocked_in_read_only_mode(self):
        with self._load("d", {"READ_ONLY_MODE": "true"}), fake_runtime_modules():
            module = load_script_module("meraki-mcp.py", "test_manual_vlan_read_only")
            response = json.loads(module.create_switch_vlan("N_1", 20, "Voice"))
            self.assertEqual("Write operation blocked - READ_ONLY_MODE is enabled", response["error"])
            self.assertEqual([], module.dashboard.calls)


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

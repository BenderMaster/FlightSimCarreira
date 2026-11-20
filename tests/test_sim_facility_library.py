import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from aerocarreira.airport_facilities import FIELDS
from aerocarreira.sim_facilities import (
    FACILITY_API_EXPORTS,
    connection_class,
    resolve_facility_simconnect_dll,
)


class FakeLibrary:
    def __init__(self, exports):
        self.exports = set(exports)

    def __getattr__(self, name):
        if name in self.exports:
            return FakeFunction()
        raise AttributeError(name)


class FakeFunction:
    def __init__(self):
        self.calls = []
        self.restype = None
        self.argtypes = None

    def __call__(self, *args):
        self.calls.append(args)
        return 0


class FacilityDllResolutionTests(unittest.TestCase):
    def test_prefers_sdk_dll_with_both_facility_exports_over_legacy_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "legacy" / "SimConnect.dll"
            legacy.parent.mkdir()
            legacy.touch()
            sdk_root = root / "MSFS SDK"
            sdk_dll = sdk_root / "SimConnect SDK" / "lib" / "SimConnect.dll"
            sdk_dll.parent.mkdir(parents=True)
            sdk_dll.touch()

            def loader(path):
                if Path(path) == legacy:
                    return FakeLibrary({"SimConnect_RequestFacilitiesList"})
                return FakeLibrary(FACILITY_API_EXPORTS)

            selected = resolve_facility_simconnect_dll(
                environ={
                    "FLIGHTSIM_SIMCONNECT_DLL": str(legacy),
                    "MSFS_SDK": str(sdk_root),
                },
                library_loader=loader,
            )
            self.assertEqual(selected, str(sdk_dll))

    def test_accepts_explicit_compatible_dll_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            explicit = Path(tmp) / "SimConnect.dll"
            explicit.touch()
            selected = resolve_facility_simconnect_dll(
                environ={"FLIGHTSIM_SIMCONNECT_DLL": str(explicit)},
                library_loader=lambda _path: FakeLibrary(FACILITY_API_EXPORTS),
            )
            self.assertEqual(selected, str(explicit))

    def test_returns_none_when_no_candidate_exports_facility_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "old.dll"
            old.touch()
            selected = resolve_facility_simconnect_dll(
                environ={"FLIGHTSIM_SIMCONNECT_DLL": str(old)},
                library_loader=lambda _path: FakeLibrary(
                    {"SimConnect_RequestFacilitiesList"}
                ),
            )
            self.assertIsNone(selected)


class FacilityConnectionTests(unittest.TestCase):
    def test_selected_sdk_dll_opens_connection_and_sends_facility_requests(self):
        class FakeSimConnect:
            def __init__(self, auto_connect=True, library_path=None):
                self.library_path = library_path
                self.hSimConnect = object()
                self.dll = SimpleNamespace(
                    SimConnect=SimpleNamespace(
                        SimConnect_RequestFacilitiesList=FakeFunction(),
                        SimConnect_AddToFacilityDefinition=FakeFunction(),
                        SimConnect_RequestFacilityData=FakeFunction(),
                    )
                )

        fake_module = types.ModuleType("SimConnect")
        fake_module.SimConnect = FakeSimConnect
        sdk_path = r"C:\MSFS SDK\SimConnect SDK\lib\SimConnect.dll"
        with patch.dict(sys.modules, {"SimConnect": fake_module}):
            with patch(
                "aerocarreira.sim_facilities.resolve_facility_simconnect_dll",
                return_value=sdk_path,
            ):
                connection_type = connection_class()
                connection = connection_type(Mock())
        self.assertEqual(connection.library_path, sdk_path)
        self.assertTrue(connection.request_airport_detail("SBRF"))
        raw = connection.dll.SimConnect
        self.assertEqual(len(raw.SimConnect_AddToFacilityDefinition.calls), len(FIELDS))
        self.assertEqual(len(raw.SimConnect_RequestFacilityData.calls), 1)

    def test_missing_facility_exports_returns_actionable_error_not_attribute_trace(self):
        class LegacySimConnect:
            def __init__(self, auto_connect=True, library_path=None):
                self.library_path = library_path
                self.hSimConnect = object()
                self.dll = SimpleNamespace(
                    SimConnect=SimpleNamespace(
                        SimConnect_RequestFacilitiesList=FakeFunction()
                    )
                )

        fake_module = types.ModuleType("SimConnect")
        fake_module.SimConnect = LegacySimConnect
        errors = []
        with patch.dict(sys.modules, {"SimConnect": fake_module}):
            with patch(
                "aerocarreira.sim_facilities.resolve_facility_simconnect_dll",
                return_value=None,
            ):
                connection = connection_class()(Mock())
        connection.detail_callbacks = (lambda *_: None, lambda _icao, error: errors.append(error))
        self.assertFalse(connection.request_airport_detail("SBRF"))
        self.assertEqual(len(errors), 1)
        self.assertIn("SDK do MSFS 2020 versão 0.19.0 ou superior", errors[0])
        self.assertIn("FLIGHTSIM_SIMCONNECT_DLL", errors[0])


if __name__ == "__main__":
    unittest.main()

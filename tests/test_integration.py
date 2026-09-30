"""Bundling and configuration regressions against real Home Assistant APIs."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.netizen_ble import async_setup_entry
from custom_components.netizen_ble.config_flow import (
    NetizenBLEConfigFlow,
    NetizenBLEOptionsFlow,
)
from custom_components.netizen_ble.device import NetizenBLEDevice
from custom_components.netizen_ble.settings import connection_settings, verification_code

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components/netizen_ble"
ADDRESS = "B8:E3:EC:45:CC:F2"


def test_all_integration_library_imports_are_bundled():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    assert not any("petnetizen" in requirement for requirement in manifest["requirements"])
    for path in COMPONENT.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module == "petnetizen_feeder":
                assert node.level == 1, path
    wrapper = NetizenBLEDevice(ADDRESS)
    assert wrapper._device.__class__.__module__.startswith(
        "custom_components.netizen_ble.petnetizen_feeder."
    )
    assert wrapper._device.verification_code is None
    assert wrapper._device._protocol.auto_sync_time is False


def test_old_entry_default_does_not_enable_verification():
    assert verification_code({"verification_code": "00000000"}) is None
    assert verification_code({"verification_code": "01020304"}) is None
    assert verification_code({"use_verification_code": True}) == "00000000"


@pytest.mark.parametrize("code", ["2413", "0000000Z", "00 00 00 00"])
def test_invalid_verification_is_rejected_only_when_enabled(code):
    assert verification_code({"verification_code": code}) is None
    with pytest.raises(ValueError):
        connection_settings({"use_verification_code": True, "verification_code": code})


async def test_manual_setup_defaults_to_no_verification(tmp_path):
    flow = NetizenBLEConfigFlow()
    flow.hass = HomeAssistant(str(tmp_path))
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = Mock()
    form = await flow.async_step_manual()
    values = form["data_schema"]({"address": ADDRESS})
    assert values["use_verification_code"] is False
    result = await flow.async_step_manual(values)
    assert result["type"] == "create_entry"
    assert verification_code(result["data"]) is None
    assert result["data"]["auto_sync_time"] is False


async def test_manual_setup_rejects_short_pin(tmp_path):
    flow = NetizenBLEConfigFlow()
    flow.hass = HomeAssistant(str(tmp_path))
    result = await flow.async_step_manual(
        {"address": ADDRESS, "use_verification_code": True, "verification_code": "2413"}
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_verification_code"}


async def test_options_preserve_unrelated_values_and_allow_explicit_code(monkeypatch, tmp_path):
    entry = SimpleNamespace(
        data={"address": ADDRESS, "verification_code": "00000000"},
        options={"unrelated_option": 12},
    )
    monkeypatch.setattr(NetizenBLEOptionsFlow, "config_entry", property(lambda self: entry))
    flow = NetizenBLEOptionsFlow()
    flow.hass = HomeAssistant(str(tmp_path))
    result = await flow.async_step_init(
        {
            "use_verification_code": True,
            "verification_code": "aabbccdd",
            "auto_sync_time": True,
        }
    )
    assert result["type"] == "create_entry"
    assert result["data"]["unrelated_option"] == 12
    assert verification_code(result["data"]) == "AABBCCDD"
    assert result["data"]["auto_sync_time"] is True


@pytest.mark.parametrize(
    "options,expected_code",
    [
        ({}, None),
        ({"use_verification_code": True, "verification_code": "11223344"}, "11223344"),
    ],
)
async def test_setup_passes_selected_verification_to_device(monkeypatch, options, expected_code):
    import custom_components.netizen_ble as integration

    client = Mock()
    device = Mock()
    device.connect = AsyncMock(return_value=True)
    device.disconnect = AsyncMock()
    create_device = Mock(return_value=device)
    coordinator = Mock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    ble_device = Mock()
    monkeypatch.setattr(integration, "NetizenBLEDevice", create_device)
    monkeypatch.setattr(integration, "NetizenBLECoordinator", Mock(return_value=coordinator))
    monkeypatch.setattr(integration, "device_source", Mock(return_value=None))
    monkeypatch.setattr(integration, "establish_connection", AsyncMock(return_value=client))
    monkeypatch.setattr(
        integration.bluetooth,
        "async_discovered_service_info",
        Mock(return_value=[SimpleNamespace(address=ADDRESS, device=ble_device)]),
    )
    hass = Mock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = Mock()
    entry.data = {"address": ADDRESS, "verification_code": "00000000"}
    entry.options = options
    entry.entry_id = "feeder"
    entry.title = "Feeder"
    assert await async_setup_entry(hass, entry)
    assert create_device.call_args.kwargs["verification_code"] == expected_code
    assert create_device.call_args.kwargs["auto_sync_time"] is False
    device.connect.assert_awaited_once_with(ble_client=client)
    entry.add_update_listener.assert_called_once_with(integration._async_reload_entry)

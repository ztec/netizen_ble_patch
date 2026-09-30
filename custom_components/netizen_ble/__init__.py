"""Pet Netizen BLE integration (feeder devices via petnetizen_feeder library)."""

from __future__ import annotations

import asyncio
import logging
from time import monotonic as _monotonic

import voluptuous as vol
from bleak import BleakClient
from bleak_retry_connector import device_source, establish_connection, get_device
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_ID,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_AUTO_SYNC_TIME,
    CONF_DEVICE_TYPE,
    DOMAIN,
)
from .coordinator import (
    PROXY_RESTART_COOLDOWN_S,
    NetizenBLECoordinator,
    find_proxy_restart_entity,
)
from .device import NetizenBLEDevice
from .settings import connection_settings, verification_code

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.TIME,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Netizen BLE from a config entry (feeder via petnetizen_feeder)."""
    address = entry.data[CONF_ADDRESS].upper().replace("-", ":")
    if len(address) == 12 and ":" not in address:
        address = ":".join(address[i : i + 2] for i in range(0, 12, 2))
    settings = connection_settings({**entry.data, **entry.options})
    device_type = entry.data.get(CONF_DEVICE_TYPE)

    # Prefer a local Bluetooth adapter over ESPHome proxies: the feeder's
    # firmware is incompatible with the ESPHome proxy's ESP32 BLE stack
    # (start_notify causes the device to disconnect with HCI error 19).
    # Iterate all discovered service infos for this address and pick one
    # from a local adapter (device_source returns None for local adapters).
    ble_device = None
    for service_info in bluetooth.async_discovered_service_info(hass, connectable=True):
        if service_info.address.upper() != address:
            continue
        if not device_source(service_info.device):
            ble_device = service_info.device
            _LOGGER.debug("Using local adapter for %s", address)
            break
        if ble_device is None:
            ble_device = service_info.device  # keep first found as fallback

    if ble_device is None:
        ble_device = bluetooth.async_ble_device_from_address(hass, address, True)
    if ble_device is None:
        ble_device = await get_device(address)
    if ble_device is None:
        raise ConfigEntryNotReady(f"BLE device {address} not found by any scanner")

    if device_source(ble_device):
        _LOGGER.warning(
            "No local adapter found for %s, falling back to proxy %s — "
            "connection may fail; add a local Bluetooth adapter for reliability",
            address,
            device_source(ble_device),
        )

    entry_title = entry.title

    async def _create_ble_connection() -> BleakClient:
        """Obtain a fresh BleakClient via HA's Bluetooth stack.

        Called by the library's ``ensure_connected()`` whenever the feeder
        connection drops and needs to be re-established.
        """
        dev = None
        for si in bluetooth.async_discovered_service_info(hass, connectable=True):
            if si.address.upper() != address:
                continue
            if not device_source(si.device):
                dev = si.device
                break
            if dev is None:
                dev = si.device
        if dev is None:
            dev = bluetooth.async_ble_device_from_address(hass, address, True)
        if dev is None:
            raise RuntimeError(f"BLE device {address} not found by any scanner")
        return await establish_connection(BleakClient, dev, entry_title)

    device = NetizenBLEDevice(
        address,
        verification_code=verification_code(settings),
        device_type=device_type,
        connection_factory=_create_ble_connection,
        auto_sync_time=settings[CONF_AUTO_SYNC_TIME],
    )

    max_setup_attempts = 3
    for attempt in range(1, max_setup_attempts + 1):
        ble_client = None
        try:
            ble_client = await establish_connection(BleakClient, ble_device, entry_title)
            if await device.connect(ble_client=ble_client):
                break
            try:
                await ble_client.disconnect()
            except Exception:
                pass
        except Exception as exc:
            _LOGGER.debug(
                "Connection attempt %d/%d for %s raised: %s",
                attempt,
                max_setup_attempts,
                address,
                exc,
            )
            if ble_client is not None:
                try:
                    await ble_client.disconnect()
                except Exception:
                    pass
        if attempt < max_setup_attempts:
            _LOGGER.warning(
                "Connection attempt %d/%d for %s failed, retrying in 5s",
                attempt,
                max_setup_attempts,
                address,
            )
            await asyncio.sleep(5.0)
        else:
            # All setup attempts exhausted.  If we're going through a proxy the
            # ESP32 NimBLE stack may have gotten into a stuck state where CCCD
            # writes always trigger HCI error 19.  Restarting the proxy clears
            # this — but only once per cooldown period to avoid restart loops.
            proxy_mac = device_source(ble_device)
            if proxy_mac:
                restart_timestamps: dict = hass.data.setdefault(
                    f"{DOMAIN}_proxy_restart_timestamps", {}
                )
                now = _monotonic()
                last = restart_timestamps.get(proxy_mac, 0.0)
                if (now - last) >= PROXY_RESTART_COOLDOWN_S:
                    restart_entity = find_proxy_restart_entity(hass, proxy_mac)
                    if restart_entity:
                        _LOGGER.warning(
                            "Restarting BLE proxy (%s) via %s — feeder %s "
                            "unreachable after %d setup attempts",
                            proxy_mac,
                            restart_entity,
                            address,
                            max_setup_attempts,
                        )
                        try:
                            await hass.services.async_call(
                                "button",
                                "press",
                                {"entity_id": restart_entity},
                                blocking=True,
                            )
                        except Exception as exc:
                            _LOGGER.warning("Failed to restart BLE proxy: %s", exc)
                    else:
                        _LOGGER.warning(
                            "Feeder %s unreachable — proxy restart button not found "
                            "for %s; restart the proxy manually",
                            address,
                            proxy_mac,
                        )
                    restart_timestamps[proxy_mac] = now
            raise ConfigEntryNotReady(
                f"Could not connect to feeder {address} after {max_setup_attempts} attempts"
            )

    coordinator = NetizenBLECoordinator(
        hass,
        device,
        proxy_source_mac=device_source(ble_device),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def _async_stop(_: Event) -> None:
        await device.disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop))
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    async def async_set_feed_plan(call) -> None:
        """Service: set_feed_plan(device_id, schedule). schedule: list of {weekdays, time, portions, enabled}."""
        device_id = call.data.get(CONF_DEVICE_ID)
        schedule = call.data.get("schedule", [])
        if not device_id or not schedule:
            _LOGGER.warning("set_feed_plan requires device_id and schedule")
            return
        dev_reg = dr.async_get(hass)
        device_entry = dev_reg.async_get(device_id)
        if not device_entry:
            _LOGGER.warning("Device %s not found", device_id)
            return
        for _entry_id, coord in list(hass.data.get(DOMAIN, {}).items()):
            if not isinstance(coord, NetizenBLECoordinator):
                continue
            if (DOMAIN, coord.device.address) in device_entry.identifiers:
                await coord.device.set_feed_plan(schedule)
                await coord.async_request_refresh()
                return
        _LOGGER.warning("Netizen BLE device not found for device_id %s", device_id)

    hass.services.async_register(
        DOMAIN,
        "set_feed_plan",
        async_set_feed_plan,
        vol.Schema(
            {
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required("schedule"): [
                    vol.Schema(
                        {
                            vol.Required("weekdays"): [str],
                            vol.Required("time"): str,
                            vol.Optional("portions", default=1): vol.All(int, vol.Range(0, 15)),
                            vol.Optional("enabled", default=True): bool,
                        }
                    )
                ],
            }
        ),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: NetizenBLECoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_unload()
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply updated verification and clock-sync options."""
    await hass.config_entries.async_reload(entry.entry_id)

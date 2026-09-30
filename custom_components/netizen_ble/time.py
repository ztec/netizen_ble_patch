"""Netizen BLE time entities (Do Not Disturb start/end)."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetizenBLECoordinator

TIME_ENTITIES: list[TimeEntityDescription] = [
    TimeEntityDescription(
        key="dnd_start",
        translation_key="dnd_start",
        icon="mdi:bell-sleep-outline",
    ),
    TimeEntityDescription(
        key="dnd_end",
        translation_key="dnd_end",
        icon="mdi:bell-outline",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE time entities."""
    coordinator: NetizenBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, device.address)},
        "name": entry.title or device.name,
        "manufacturer": "Pet Netizen",
        "model": device.get_state("device_name") or "Feeder",
    }
    async_add_entities([NetizenBLETime(coordinator, device_info, desc) for desc in TIME_ENTITIES])


class NetizenBLETime(CoordinatorEntity[NetizenBLECoordinator], TimeEntity):
    """Netizen BLE time entity for DND start/end time."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        device_info: DeviceInfo,
        description: TimeEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._device = coordinator.device
        self._attr_device_info = device_info
        self.entity_description = description
        self._attr_unique_id = f"{self._device.address}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def available(self) -> bool:
        return self.coordinator.reachable

    @property
    def native_value(self) -> time | None:
        data = self.coordinator.data or {}
        time_str = data.get(self.entity_description.key)
        if not time_str:
            return None
        try:
            hour, minute = (int(x) for x in time_str.split(":"))
            return time(hour, minute)
        except (ValueError, AttributeError):
            return None

    async def async_set_value(self, value: time) -> None:
        data = self.coordinator.data or {}
        key = self.entity_description.key
        new_time = f"{value.hour:02d}:{value.minute:02d}"
        if key == "dnd_start":
            await self._device.set_do_not_disturb(
                enabled=data.get("dnd_enabled", False),
                start_time=new_time,
                end_time=data.get("dnd_end", "08:00"),
            )
        elif key == "dnd_end":
            await self._device.set_do_not_disturb(
                enabled=data.get("dnd_enabled", False),
                start_time=data.get("dnd_start", "22:00"),
                end_time=new_time,
            )
        self.coordinator.hass.async_create_task(self.coordinator.async_request_refresh())

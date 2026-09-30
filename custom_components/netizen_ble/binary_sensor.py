"""Netizen BLE binary sensor entities."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetizenBLECoordinator

BINARY_SENSORS: list[BinarySensorEntityDescription] = [
    BinarySensorEntityDescription(
        key="fault",
        translation_key="fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE binary sensors."""
    coordinator: NetizenBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, device.address)},
        "name": entry.title or device.name,
        "manufacturer": "Pet Netizen",
        "model": device.get_state("device_name") or "Feeder",
    }
    entities = [NetizenBLEBinarySensor(coordinator, device_info, desc) for desc in BINARY_SENSORS]
    async_add_entities(entities)


class NetizenBLEBinarySensor(CoordinatorEntity[NetizenBLECoordinator], BinarySensorEntity):
    """Netizen BLE binary sensor."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        device_info: DeviceInfo,
        description: BinarySensorEntityDescription,
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
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        if self.entity_description.key == "fault":
            code = data.get("fault_code")
            if code is None:
                return None
            return code != 0
        return None

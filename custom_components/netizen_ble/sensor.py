"""Netizen BLE sensor entities (feed plan)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetizenBLECoordinator

SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="feed_plan",
        translation_key="feed_plan",
        icon="mdi:calendar-clock",
    ),
    SensorEntityDescription(
        key="next_feeding",
        translation_key="next_feeding",
        icon="mdi:food-drumstick-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="firmware_version",
        translation_key="firmware_version",
        icon="mdi:chip",
    ),
    SensorEntityDescription(
        key="fault_status",
        translation_key="fault_status",
        icon="mdi:alert-circle-outline",
    ),
    SensorEntityDescription(
        key="feeding_status",
        translation_key="feeding_status",
        icon="mdi:food-variant",
    ),
    SensorEntityDescription(
        key="last_feed_time",
        translation_key="last_feed_time",
        icon="mdi:history",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
]

TC02_SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="tc02_auto_countdown_remaining",
        translation_key="tc02_auto_countdown_remaining",
        icon="mdi:timer-sand",
        native_unit_of_measurement="min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

_FEEDER_ONLY_SENSORS = {"feed_plan", "next_feeding", "feeding_status", "last_feed_time"}

_WEEKDAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _next_feeding(slots: list[dict]) -> tuple[datetime | None, dict | None]:
    """Return (next_datetime, slot) for the earliest upcoming enabled feeding."""
    now = dt_util.now()
    best_dt: datetime | None = None
    best_slot: dict | None = None

    for day_offset in range(8):  # today + 7 days ahead
        check_dt = now + timedelta(days=day_offset)
        check_weekday = check_dt.weekday()  # 0=Mon … 6=Sun

        for slot in slots:
            if not slot.get("enabled", True):
                continue
            weekdays = slot.get("weekdays") or []
            slot_weekdays = {_WEEKDAY_MAP.get(d.lower(), -1) for d in weekdays}
            if check_weekday not in slot_weekdays:
                continue

            time_str = slot.get("time", "00:00")
            try:
                hour, minute = (int(x) for x in time_str.split(":"))
            except (ValueError, AttributeError):
                continue

            candidate = check_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                continue
            if best_dt is None or candidate < best_dt:
                best_dt = candidate
                best_slot = slot

    return best_dt, best_slot


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE sensors."""
    coordinator: NetizenBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, device.address)},
        "name": entry.title or device.name,
        "manufacturer": "Pet Netizen",
        "model": device.get_state("device_name") or "Feeder",
    }
    is_tc02 = device.device_type == "tc02"
    active = [desc for desc in SENSORS if not (is_tc02 and desc.key in _FEEDER_ONLY_SENSORS)]
    if is_tc02:
        active += TC02_SENSORS
    entities = [NetizenBLESensor(coordinator, device_info, desc) for desc in active]
    async_add_entities(entities)


class NetizenBLESensor(CoordinatorEntity[NetizenBLECoordinator], SensorEntity):
    """Netizen BLE sensor."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        device_info: DeviceInfo,
        description: SensorEntityDescription,
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
    def native_value(self) -> str | int | datetime | None:
        data = self.coordinator.data or {}
        key = self.entity_description.key
        if key == "feed_plan":
            slots = data.get("feed_plan_slots") or []
            return len(slots)
        if key == "next_feeding":
            slots = data.get("feed_plan_slots") or []
            next_dt, _ = _next_feeding(slots)
            return next_dt
        if key == "firmware_version":
            return data.get("device_version") or None
        if key == "fault_status":
            code = data.get("fault_code")
            if code is None:
                return None
            return "ok" if code == 0 else f"fault_{code}"
        if key == "feeding_status":
            return data.get("feeding_status") or None
        if key == "last_feed_time":
            result = data.get("last_feed_result")
            if not result or not isinstance(result, dict):
                return None
            ts = result.get("timestamp")
            if not ts:
                return None
            try:
                naive = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                return dt_util.as_local(naive)
            except (ValueError, TypeError):
                return None
        if key == "tc02_auto_countdown_remaining":
            v = data.get("tc02_auto_countdown_remaining")
            return int(v) if v is not None else None
        return data.get(key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose schedule slots / device info in attributes."""
        data = self.coordinator.data or {}
        attrs: dict[str, Any] = {}
        key = self.entity_description.key
        if key == "feed_plan" and "feed_plan_slots" in data:
            attrs["slots"] = data["feed_plan_slots"]
        if key == "next_feeding":
            slots = data.get("feed_plan_slots") or []
            _, slot = _next_feeding(slots)
            if slot:
                attrs["portions"] = slot.get("portions", 1)
                attrs["weekdays"] = slot.get("weekdays", [])
                attrs["time"] = slot.get("time", "")
        if key == "firmware_version" and data.get("device_name"):
            attrs["device_name"] = data["device_name"]
        if key == "last_feed_time":
            result = data.get("last_feed_result")
            if isinstance(result, dict):
                attrs.update({k: v for k, v in result.items() if k != "timestamp"})
        return attrs

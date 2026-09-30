"""Netizen BLE switch entities (child lock, prompt sound, manual feed)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetizenBLECoordinator

SWITCHES: list[SwitchEntityDescription] = [
    SwitchEntityDescription(key="manual_feed", translation_key="manual_feed", icon="mdi:food"),
    SwitchEntityDescription(key="child_lock", translation_key="child_lock", icon="mdi:lock"),
    SwitchEntityDescription(
        key="prompt_sound", translation_key="prompt_sound", icon="mdi:volume-high"
    ),
    SwitchEntityDescription(key="led", translation_key="led", icon="mdi:led-on"),
    SwitchEntityDescription(
        key="atmosphere_light", translation_key="atmosphere_light", icon="mdi:lightbulb"
    ),
    SwitchEntityDescription(key="auto_lock", translation_key="auto_lock", icon="mdi:lock-clock"),
    SwitchEntityDescription(
        key="do_not_disturb", translation_key="do_not_disturb", icon="mdi:bell-sleep"
    ),
    SwitchEntityDescription(key="long_ring", translation_key="long_ring", icon="mdi:bell-ring"),
]

CP01B_SWITCHES: list[SwitchEntityDescription] = [
    SwitchEntityDescription(
        key="cp01b_sound", translation_key="cp01b_sound", icon="mdi:volume-medium"
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netizen BLE switches."""
    coordinator: NetizenBLECoordinator = hass.data[DOMAIN][entry.entry_id]
    device = coordinator.device
    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, device.address)},
        "name": entry.title or device.name,
        "manufacturer": "Pet Netizen",
        "model": device.get_state("device_name") or "Feeder",
    }
    is_tc02 = device.device_type == "tc02"
    feeder_only = {"manual_feed"}
    active = [desc for desc in SWITCHES if not (is_tc02 and desc.key in feeder_only)]
    if device.device_type == "cp01b":
        active += CP01B_SWITCHES
    entities = [
        NetizenBLESwitch(coordinator, device_info, desc, is_feed=(desc.key == "manual_feed"))
        for desc in active
    ]
    async_add_entities(entities)


class NetizenBLESwitch(CoordinatorEntity[NetizenBLECoordinator], SwitchEntity):
    """Netizen BLE switch (child lock, prompt sound, or manual feed trigger)."""

    def __init__(
        self,
        coordinator: NetizenBLECoordinator,
        device_info: DeviceInfo,
        description: SwitchEntityDescription,
        *,
        is_feed: bool = False,
    ) -> None:
        super().__init__(coordinator)
        self._device = coordinator.device
        self._attr_device_info = device_info
        self.entity_description = description
        self._attr_unique_id = f"{self._device.address}_{description.key}"
        self._attr_has_entity_name = True
        self._is_feed = is_feed

    @property
    def available(self) -> bool:
        return self.coordinator.reachable

    def _state_key(self) -> str:
        return self.entity_description.key

    @property
    def is_on(self) -> bool | None:
        if self._is_feed:
            return None  # momentary action
        data = self.coordinator.data or {}
        key = self._state_key()
        if key == "do_not_disturb":
            return data.get("dnd_enabled")
        if key == "cp01b_sound":
            return data.get("cp01b_prompt_sound")
        return data.get(key)

    async def _set_state(self, enabled: bool) -> None:
        key = self._state_key()
        if key == "child_lock":
            await self._device.set_child_lock(enabled)
        elif key == "prompt_sound":
            await self._device.set_prompt_sound(enabled)
        elif key == "led":
            await self._device.set_led(enabled)
        elif key == "atmosphere_light":
            await self._device.set_atmosphere_light(enabled)
        elif key == "auto_lock":
            await self._device.set_auto_lock(enabled)
        elif key == "do_not_disturb":
            data = self.coordinator.data or {}
            await self._device.set_do_not_disturb(
                enabled,
                start_time=data.get("dnd_start", "22:00"),
                end_time=data.get("dnd_end", "08:00"),
            )
        elif key == "long_ring":
            await self._device.set_long_ring(enabled)
        elif key == "cp01b_sound":
            await self._device.set_cp01b_prompt_sound(enabled)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self._is_feed:
            portions = getattr(self.coordinator, "_feed_portions", 1) or 1
            await self._device.trigger_feed(portions=portions)
            return
        await self._set_state(True)
        self.coordinator.hass.async_create_task(self.coordinator.async_request_refresh())

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._is_feed:
            return
        await self._set_state(False)
        self.coordinator.hass.async_create_task(self.coordinator.async_request_refresh())

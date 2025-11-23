"""Oasis device number entity."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OasisDeviceConfigEntry, setup_platform_from_coordinator
from .entity import OasisDeviceEntity
from .pyoasiscontrol import OasisDevice
from .pyoasiscontrol.device import (
    BALL_SPEED_MAX,
    BALL_SPEED_MIN,
    LED_SPEED_MAX,
    LED_SPEED_MIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OasisDeviceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oasis device numbers using config entry."""

    def make_entities(new_devices: list[OasisDevice]):
        return [
            OasisDeviceNumberEntity(entry.runtime_data, device, descriptor)
            for device in new_devices
            for descriptor in DESCRIPTORS
        ]

    setup_platform_from_coordinator(entry, async_add_entities, make_entities)


DESCRIPTORS = {
    NumberEntityDescription(
        key="ball_speed",
        translation_key="ball_speed",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.SLIDER,
        native_max_value=BALL_SPEED_MAX,
        native_min_value=BALL_SPEED_MIN,
    ),
    NumberEntityDescription(
        key="led_speed",
        translation_key="led_speed",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.SLIDER,
        native_max_value=LED_SPEED_MAX,
        native_min_value=LED_SPEED_MIN,
    ),
}


class OasisDeviceNumberEntity(OasisDeviceEntity, NumberEntity):
    """Oasis device number entity."""

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the number."""
        return getattr(self.device, self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        value = int(value)
        if self.entity_description.key == "ball_speed":
            await self.device.async_set_ball_speed(value)
        elif self.entity_description.key == "led_speed":
            await self.device.async_set_led(led_speed=value)

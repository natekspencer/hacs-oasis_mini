"""Oasis Mini number entity."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OasisMiniConfigEntry
from .entity import OasisMiniEntity
from .pyoasismini import BALL_SPEED_MAX, BALL_SPEED_MIN, LED_SPEED_MAX, LED_SPEED_MIN


class OasisMiniNumberEntity(OasisMiniEntity, NumberEntity):
    """Oasis Mini number entity."""

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the number."""
        return getattr(self.device, self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.key == "ball_speed":
            await self.device.async_set_ball_speed(value)
        elif self.entity_description.key == "led_speed":
            await self.device.async_set_led(led_speed=value)
        await self.coordinator.async_request_refresh()


DESCRIPTORS = {
    NumberEntityDescription(
        key="ball_speed",
        name="Ball speed",
        mode=NumberMode.SLIDER,
        native_max_value=BALL_SPEED_MAX,
        native_min_value=BALL_SPEED_MIN,
    ),
    NumberEntityDescription(
        key="led_speed",
        name="LED speed",
        mode=NumberMode.SLIDER,
        native_max_value=LED_SPEED_MAX,
        native_min_value=LED_SPEED_MIN,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OasisMiniConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oasis Mini numbers using config entry."""
    async_add_entities(
        [
            OasisMiniNumberEntity(entry.runtime_data, descriptor)
            for descriptor in DESCRIPTORS
        ]
    )

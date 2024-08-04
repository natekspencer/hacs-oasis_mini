"""Oasis Mini light entity."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import (
    brightness_to_value,
    color_rgb_to_hex,
    rgb_hex_to_rgb_list,
    value_to_brightness,
)

from . import OasisMiniConfigEntry
from .entity import OasisMiniEntity
from .pyoasismini import LED_EFFECTS


class OasisMiniLightEntity(OasisMiniEntity, LightEntity):
    """Oasis Mini light entity."""

    _attr_supported_features = LightEntityFeature.EFFECT

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        scale = (1, self.device.max_brightness)
        return value_to_brightness(scale, self.device.brightness)

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self.effect in (
            "Rainbow",
            "Glitter",
            "Confetti",
            "BPM",
            "Juggle",
        ):
            return ColorMode.BRIGHTNESS
        return ColorMode.RGB

    @property
    def effect(self) -> str:
        """Return the current effect."""
        return LED_EFFECTS.get(self.device.led_effect)

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return list(LED_EFFECTS.values())

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.device.brightness > 0

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the rgb color value [int, int, int]."""
        return rgb_hex_to_rgb_list(self.device.color.replace("#", ""))

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return {ColorMode.RGB}

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.device.async_set_led(brightness=0)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if brightness := kwargs.get(ATTR_BRIGHTNESS):
            scale = (1, self.device.max_brightness)
            brightness = math.ceil(brightness_to_value(scale, brightness))
        else:
            brightness = self.device.brightness or 100

        if color := kwargs.get(ATTR_RGB_COLOR):
            color = f"#{color_rgb_to_hex(*color)}"

        if led_effect := kwargs.get(ATTR_EFFECT):
            led_effect = next(
                (k for k, v in LED_EFFECTS.items() if v == led_effect), None
            )

        await self.device.async_set_led(
            brightness=brightness, color=color, led_effect=led_effect
        )
        await self.coordinator.async_request_refresh()


DESCRIPTOR = LightEntityDescription(key="led", name="LED")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OasisMiniConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oasis Mini lights using config entry."""
    async_add_entities([OasisMiniLightEntity(entry.runtime_data, DESCRIPTOR)])

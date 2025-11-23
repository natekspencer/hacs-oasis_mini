"""Oasis device button entity."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Awaitable, Callable

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OasisDeviceConfigEntry, setup_platform_from_coordinator
from .entity import OasisDeviceEntity
from .helpers import add_and_play_track
from .pyoasiscontrol import OasisDevice
from .pyoasiscontrol.const import TRACKS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OasisDeviceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oasis device button using config entry."""

    def make_entities(new_devices: list[OasisDevice]):
        return [
            OasisDeviceButtonEntity(entry.runtime_data, device, descriptor)
            for device in new_devices
            for descriptor in DESCRIPTORS
        ]

    setup_platform_from_coordinator(entry, async_add_entities, make_entities)


async def play_random_track(device: OasisDevice) -> None:
    """Play random track."""
    track = random.choice(list(TRACKS))
    try:
        await add_and_play_track(device, track)
    except TimeoutError as err:
        raise HomeAssistantError("Timeout adding track to queue") from err


@dataclass(frozen=True, kw_only=True)
class OasisDeviceButtonEntityDescription(ButtonEntityDescription):
    """Oasis device button entity description."""

    press_fn: Callable[[OasisDevice], Awaitable[None]]


DESCRIPTORS = (
    OasisDeviceButtonEntityDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda device: device.async_reboot(),
    ),
    OasisDeviceButtonEntityDescription(
        key="random_track",
        translation_key="random_track",
        press_fn=play_random_track,
    ),
    OasisDeviceButtonEntityDescription(
        key="sleep",
        translation_key="sleep",
        press_fn=lambda device: device.async_sleep(),
    ),
)


class OasisDeviceButtonEntity(OasisDeviceEntity, ButtonEntity):
    """Oasis device button entity."""

    entity_description: OasisDeviceButtonEntityDescription

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.device)

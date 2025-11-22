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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OasisDeviceConfigEntry
from .coordinator import OasisDeviceCoordinator
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
    coordinator: OasisDeviceCoordinator = entry.runtime_data
    async_add_entities(
        OasisDeviceButtonEntity(coordinator, device, descriptor)
        for device in coordinator.data
        for descriptor in DESCRIPTORS
    )


async def play_random_track(device: OasisDevice) -> None:
    """Play random track."""
    track = random.choice(list(TRACKS))
    await add_and_play_track(device, track)


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

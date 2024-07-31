"""Oasis Mini button entity."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Awaitable, Callable

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity
from .helpers import add_and_play_track
from .pyoasismini import OasisMini
from .pyoasismini.const import TRACKS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Oasis Mini button using config entry."""
    coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OasisMiniButtonEntity(coordinator, entry, descriptor)
            for descriptor in DESCRIPTORS
        ]
    )


async def play_random_track(device: OasisMini) -> None:
    """Play random track."""
    track = int(random.choice(list(TRACKS)))
    await add_and_play_track(device, track)


@dataclass(frozen=True, kw_only=True)
class OasisMiniButtonEntityDescription(ButtonEntityDescription):
    """Oasis Mini button entity description."""

    press_fn: Callable[[OasisMini], Awaitable[None]]


DESCRIPTORS = (
    OasisMiniButtonEntityDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda device: device.async_reboot(),
    ),
    OasisMiniButtonEntityDescription(
        key="random_track",
        name="Play random track",
        press_fn=play_random_track,
    ),
)


class OasisMiniButtonEntity(OasisMiniEntity, ButtonEntity):
    """Oasis Mini button entity."""

    entity_description: OasisMiniButtonEntityDescription

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.device)
        await self.coordinator.async_request_refresh()

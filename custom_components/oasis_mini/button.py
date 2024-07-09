"""Oasis Mini button entity."""

from __future__ import annotations

from typing import Any, Coroutine

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity
from .pyoasismini.const import TRACKS


class OasisMiniButtonEntity(OasisMiniEntity, ButtonEntity):
    """Oasis Mini button entity."""

    async def async_press(self) -> None:
        """Press the button."""
        await self.device.async_reboot()


DESCRIPTOR = ButtonEntityDescription(
    key="reboot", device_class=ButtonDeviceClass.RESTART
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Oasis Mini button using config entry."""
    coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OasisMiniButtonEntity(coordinator, entry, DESCRIPTOR)])

"""Oasis device switch entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OasisDeviceConfigEntry, setup_platform_from_coordinator
from .entity import OasisDeviceEntity
from .pyoasiscontrol import OasisDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OasisDeviceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oasis device switchs using config entry."""

    def make_entities(new_devices: list[OasisDevice]):
        return [
            OasisDeviceSwitchEntity(entry.runtime_data, device, descriptor)
            for device in new_devices
            for descriptor in DESCRIPTORS
        ]

    setup_platform_from_coordinator(entry, async_add_entities, make_entities)


DESCRIPTORS = {
    SwitchEntityDescription(
        key="auto_clean",
        translation_key="auto_clean",
        entity_category=EntityCategory.CONFIG,
    ),
}


class OasisDeviceSwitchEntity(OasisDeviceEntity, SwitchEntity):
    """Oasis device switch entity."""

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return bool(getattr(self.device, self.entity_description.key))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.device.async_set_auto_clean(False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.device.async_set_auto_clean(True)

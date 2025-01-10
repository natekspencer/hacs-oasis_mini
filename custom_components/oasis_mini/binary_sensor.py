"""Oasis Mini binary sensor entity."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OasisMiniConfigEntry
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OasisMiniConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oasis Mini sensors using config entry."""
    coordinator: OasisMiniCoordinator = entry.runtime_data
    async_add_entities(
        OasisMiniBinarySensorEntity(coordinator, descriptor)
        for descriptor in DESCRIPTORS
    )


DESCRIPTORS = {
    BinarySensorEntityDescription(
        key="busy",
        translation_key="busy",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="wifi_connected",
        translation_key="wifi_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}


class OasisMiniBinarySensorEntity(OasisMiniEntity, BinarySensorEntity):
    """Oasis Mini binary sensor entity."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return getattr(self.device, self.entity_description.key)

"""Oasis Mini sensor entity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity
from .pyoasismini import OasisMini


@dataclass(frozen=True, kw_only=True)
class OasisMiniSensorEntityDescription(SensorEntityDescription):
    """Oasis Mini sensor entity description."""

    lookup_fn: Callable[[OasisMini], Any] | None = None


class OasisMiniSensorEntity(OasisMiniEntity, SensorEntity):
    """Oasis Mini sensor entity."""

    entity_description: OasisMiniSensorEntityDescription | SensorEntityDescription

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the sensor."""
        if lookup_fn := getattr(self.entity_description, "lookup_fn", None):
            return lookup_fn(self.device)
        return getattr(self.device, self.entity_description.key)


DESCRIPTORS = {
    SensorEntityDescription(
        key="download_progress",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        name="Download progress",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    OasisMiniSensorEntityDescription(
        key="playlist",
        name="Playlist",
        lookup_fn=lambda device: ",".join(map(str, device.playlist)),
    ),
}

OTHERS = {
    SensorEntityDescription(
        key=key,
        name=key.replace("_", " ").capitalize(),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    )
    for key in (
        "busy",
        "error",
        "led_color_id",
        "status",
        "wifi_connected",
    )
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Oasis Mini sensors using config entry."""
    coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OasisMiniSensorEntity(coordinator, entry, descriptor)
            for descriptor in DESCRIPTORS | OTHERS
        ]
    )

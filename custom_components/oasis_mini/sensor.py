"""Oasis Mini sensor entity."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Oasis Mini sensors using config entry."""
    coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OasisMiniSensorEntity(coordinator, entry, descriptor)
            for descriptor in DESCRIPTORS
        ]
    )


DESCRIPTORS = {
    SensorEntityDescription(
        key="download_progress",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        name="Download progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
} | {
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


class OasisMiniSensorEntity(OasisMiniEntity, SensorEntity):
    """Oasis Mini sensor entity."""

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the sensor."""
        return getattr(self.device, self.entity_description.key)

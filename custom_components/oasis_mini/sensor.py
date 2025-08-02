"""Oasis Mini sensor entity."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
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
    entities = [
        OasisMiniSensorEntity(coordinator, descriptor) for descriptor in DESCRIPTORS
    ]
    if coordinator.device.access_token:
        entities.extend(
            OasisMiniSensorEntity(coordinator, descriptor)
            for descriptor in CLOUD_DESCRIPTORS
        )
    async_add_entities(entities)


DESCRIPTORS = {
    SensorEntityDescription(
        key="download_progress",
        translation_key="download_progress",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
} | {
    SensorEntityDescription(
        key=key,
        translation_key=key,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    )
    for key in ("error", "led_color_id", "status")
}

CLOUD_DESCRIPTORS = (
    SensorEntityDescription(
        key="drawing_progress",
        translation_key="drawing_progress",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
)


class OasisMiniSensorEntity(OasisMiniEntity, SensorEntity):
    """Oasis Mini sensor entity."""

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the sensor."""
        return getattr(self.device, self.entity_description.key)

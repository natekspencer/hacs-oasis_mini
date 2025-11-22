"""Oasis device sensor entity."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OasisDeviceConfigEntry
from .coordinator import OasisDeviceCoordinator
from .entity import OasisDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OasisDeviceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oasis device sensors using config entry."""
    coordinator: OasisDeviceCoordinator = entry.runtime_data
    entities = [
        OasisDeviceSensorEntity(coordinator, device, descriptor)
        for device in coordinator.data
        for descriptor in DESCRIPTORS
    ]
    entities.extend(
        OasisDeviceSensorEntity(coordinator, device, descriptor)
        for device in coordinator.data
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
    # for key in ("error_message", "led_color_id", "status")
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


class OasisDeviceSensorEntity(OasisDeviceEntity, SensorEntity):
    """Oasis device sensor entity."""

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the sensor."""
        return getattr(self.device, self.entity_description.key)

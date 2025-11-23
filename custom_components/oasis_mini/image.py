"""Oasis device image entity."""

from __future__ import annotations

from homeassistant.components.image import Image, ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED

from . import OasisDeviceConfigEntry
from .coordinator import OasisDeviceCoordinator
from .entity import OasisDeviceEntity
from .pyoasiscontrol import OasisDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OasisDeviceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oasis device image using config entry."""
    coordinator: OasisDeviceCoordinator = entry.runtime_data
    async_add_entities(
        OasisDeviceImageEntity(coordinator, device, IMAGE)
        for device in coordinator.data
    )


IMAGE = ImageEntityDescription(key="image", name=None)


class OasisDeviceImageEntity(OasisDeviceEntity, ImageEntity):
    """Oasis device image entity."""

    _attr_content_type = "image/svg+xml"
    _track_id: int | None = None
    _progress: int = 0

    def __init__(
        self,
        coordinator: OasisDeviceCoordinator,
        device: OasisDevice,
        description: ImageEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, device, description)
        ImageEntity.__init__(self, coordinator.hass)
        self._handle_coordinator_update()

    def image(self) -> bytes | None:
        """Return bytes of image."""
        if not self._cached_image:
            self._cached_image = Image(self.content_type, self.device.create_svg())
        return self._cached_image.content

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = self.device
        if (
            self._track_id != device.track_id or self._progress != device.progress
        ) and (device.status == "playing" or self._cached_image is None):
            self._attr_image_last_updated = self.coordinator.last_updated
            self._track_id = device.track_id
            self._progress = device.progress
            self._cached_image = None
            if device.track and device.track.get("svg_content"):
                self._attr_image_url = UNDEFINED
            else:
                self._attr_image_url = device.track_image_url

        if self.hass:
            super()._handle_coordinator_update()

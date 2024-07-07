"""Oasis Mini image entity."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity
from .pyoasismini.utils import draw_svg

IMAGE = ImageEntityDescription(key="image", name=None)


class OasisMiniImageEntity(OasisMiniEntity, ImageEntity):
    """Oasis Mini image entity."""

    _attr_content_type = "image/svg+xml"

    def __init__(
        self,
        coordinator: OasisMiniCoordinator,
        entry_id: str,
        description: ImageEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entry_id, description)
        ImageEntity.__init__(self, coordinator.hass)

    @property
    def image_last_updated(self) -> datetime | None:
        """The time when the image was last updated."""
        return self.coordinator.last_updated

    def image(self) -> bytes | None:
        """Return bytes of image."""
        return draw_svg(
            self.device._current_track_details,
            self.device.progress,
            "1",
        )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Oasis Mini camera using config entry."""
    coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.device.access_token:
        async_add_entities([OasisMiniImageEntity(coordinator, entry, IMAGE)])

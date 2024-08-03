"""Oasis Mini image entity."""

from __future__ import annotations

from homeassistant.components.image import Image, ImageEntity, ImageEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity
from .pyoasismini.const import TRACKS
from .pyoasismini.utils import draw_svg

IMAGE = ImageEntityDescription(key="image", name=None)


class OasisMiniImageEntity(OasisMiniEntity, ImageEntity):
    """Oasis Mini image entity."""

    _attr_content_type = "image/svg+xml"
    _track_id: int | None = None
    _progress: int = 0

    def __init__(
        self,
        coordinator: OasisMiniCoordinator,
        entry_id: str,
        description: ImageEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entry_id, description)
        ImageEntity.__init__(self, coordinator.hass)
        self._handle_coordinator_update()

    def image(self) -> bytes | None:
        """Return bytes of image."""
        if not self._cached_image:
            self._cached_image = Image(
                self.content_type, draw_svg(self.device.track, self._progress, "1")
            )
        return self._cached_image.content

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._track_id != self.device.track_id or (
            self._progress != self.device.progress and self.device.access_token
        ):
            self._attr_image_last_updated = self.coordinator.last_updated
            self._track_id = self.device.track_id
            self._progress = self.device.progress
            self._cached_image = None
            if self.device.track and self.device.track.get("svg_content"):
                self._attr_image_url = UNDEFINED
            else:
                self._attr_image_url = (
                    f"https://app.grounded.so/uploads/{track['image']}"
                    if (
                        track := (self.device.track or TRACKS.get(self.device.track_id))
                    )
                    and "image" in track
                    else None
                )

        if self.hass:
            super()._handle_coordinator_update()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Oasis Mini camera using config entry."""
    coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OasisMiniImageEntity(coordinator, entry, IMAGE)])

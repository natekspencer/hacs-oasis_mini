"""Oasis Mini select entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity
from .pyoasismini.const import TRACKS


class OasisMiniSelectEntity(OasisMiniEntity, SelectEntity):
    """Oasis Mini select entity."""

    def __init__(
        self,
        coordinator: OasisMiniCoordinator,
        entry: ConfigEntry[Any],
        description: EntityDescription,
    ) -> None:
        """Construct an Oasis Mini select entity."""
        super().__init__(coordinator, entry, description)
        self._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.device.async_change_track(self.options.index(option))
        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        options = [
            TRACKS.get(str(track), {}).get("name", str(track))
            for track in self.device.playlist
        ]
        self._attr_options = options
        self._attr_current_option = options[self.device.playlist_index]
        if self.hass:
            return super()._handle_coordinator_update()


DESCRIPTOR = SelectEntityDescription(key="playlist", name="Playlist")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Oasis Mini select using config entry."""
    coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OasisMiniSelectEntity(coordinator, entry, DESCRIPTOR)])

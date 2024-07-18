"""Oasis Mini select entity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity
from .pyoasismini import AUTOPLAY_MAP, OasisMini
from .pyoasismini.const import TRACKS


@dataclass(frozen=True, kw_only=True)
class OasisMiniSelectEntityDescription(SelectEntityDescription):
    """Oasis Mini select entity description."""

    select_fn: Callable[[OasisMini, int], Awaitable[None]]
    update_handler: Callable[[OasisMiniSelectEntity], None] | None = None


class OasisMiniSelectEntity(OasisMiniEntity, SelectEntity):
    """Oasis Mini select entity."""

    entity_description: OasisMiniSelectEntityDescription

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
        await self.entity_description.select_fn(self.device, self.options.index(option))
        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if update_handler := self.entity_description.update_handler:
            update_handler(self)
        else:
            self._attr_current_option = getattr(
                self.device, self.entity_description.key
            )
        if self.hass:
            return super()._handle_coordinator_update()


def playlist_update_handler(entity: OasisMiniSelectEntity) -> None:
    """Handle playlist updates."""
    # pylint: disable=protected-access
    options = [
        TRACKS.get(str(track), {}).get("name", str(track))
        for track in entity.device.playlist
    ]
    entity._attr_options = options
    index = min(entity.device.playlist_index, len(options) - 1)
    entity._attr_current_option = options[index]


DESCRIPTORS = (
    OasisMiniSelectEntityDescription(
        key="playlist",
        name="Playlist",
        select_fn=lambda device, option: device.async_change_track(option),
        update_handler=playlist_update_handler,
    ),
    OasisMiniSelectEntityDescription(
        key="autoplay",
        name="Autoplay",
        options=list(AUTOPLAY_MAP.values()),
        select_fn=lambda device, option: device.async_set_autoplay(option),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Oasis Mini select using config entry."""
    coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OasisMiniSelectEntity(coordinator, entry, descriptor)
            for descriptor in DESCRIPTORS
        ]
    )

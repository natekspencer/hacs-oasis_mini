"""Oasis Mini select entity."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OasisMiniConfigEntry
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity
from .pyoasismini import AUTOPLAY_MAP, OasisMini
from .pyoasismini.const import TRACKS


@dataclass(frozen=True, kw_only=True)
class OasisMiniSelectEntityDescription(SelectEntityDescription):
    """Oasis Mini select entity description."""

    current_value: Callable[[OasisMini], Any]
    select_fn: Callable[[OasisMini, int], Awaitable[None]]
    update_handler: Callable[[OasisMiniSelectEntity], None] | None = None


class OasisMiniSelectEntity(OasisMiniEntity, SelectEntity):
    """Oasis Mini select entity."""

    entity_description: OasisMiniSelectEntityDescription
    _current_value: Any | None = None

    def __init__(
        self,
        coordinator: OasisMiniCoordinator,
        description: EntityDescription,
    ) -> None:
        """Construct an Oasis Mini select entity."""
        super().__init__(coordinator, description)
        self._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.device, self.options.index(option))
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        new_value = self.entity_description.current_value(self.device)
        if self._current_value == new_value:
            return
        self._current_value = new_value
        if update_handler := self.entity_description.update_handler:
            update_handler(self)
        else:
            self._attr_current_option = getattr(
                self.device, self.entity_description.key
            )
        if self.hass:
            return super()._handle_coordinator_update()


def playlists_update_handler(entity: OasisMiniSelectEntity) -> None:
    """Handle playlists updates."""
    # pylint: disable=protected-access
    device = entity.device
    counts = defaultdict(int)
    options = []
    current_option: str | None = None
    for playlist in device.playlists:
        name = playlist["name"]
        counts[name] += 1
        if counts[name] > 1:
            name = f"{name} ({counts[name]})"
        options.append(name)
        if device.playlist == [pattern["id"] for pattern in playlist["patterns"]]:
            current_option = name
    entity._attr_options = options
    entity._attr_current_option = current_option


def queue_update_handler(entity: OasisMiniSelectEntity) -> None:
    """Handle queue updates."""
    # pylint: disable=protected-access
    device = entity.device
    counts = defaultdict(int)
    options = []
    for track in device.playlist:
        name = device._playlist.get(track, {}).get(
            "name",
            TRACKS.get(track, {"id": track, "name": f"Unknown Title (#{track})"}).get(
                "name",
                device.track["name"]
                if device.track and device.track["id"] == track
                else str(track),
            ),
        )
        counts[name] += 1
        if counts[name] > 1:
            name = f"{name} ({counts[name]})"
        options.append(name)
    entity._attr_options = options
    index = min(device.playlist_index, len(options) - 1)
    entity._attr_current_option = options[index] if options else None


DESCRIPTORS = (
    OasisMiniSelectEntityDescription(
        key="autoplay",
        translation_key="autoplay",
        options=list(AUTOPLAY_MAP.values()),
        current_value=lambda device: device.autoplay,
        select_fn=lambda device, option: device.async_set_autoplay(option),
    ),
    OasisMiniSelectEntityDescription(
        key="queue",
        translation_key="queue",
        current_value=lambda device: (device.playlist.copy(), device.playlist_index),
        select_fn=lambda device, option: device.async_change_track(option),
        update_handler=queue_update_handler,
    ),
)
CLOUD_DESCRIPTORS = (
    OasisMiniSelectEntityDescription(
        key="playlists",
        translation_key="playlist",
        current_value=lambda device: (device.playlists, device.playlist.copy()),
        select_fn=lambda device, option: device.async_set_playlist(
            [pattern["id"] for pattern in device.playlists[option]["patterns"]]
        ),
        update_handler=playlists_update_handler,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OasisMiniConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oasis Mini select using config entry."""
    coordinator: OasisMiniCoordinator = entry.runtime_data
    entities = [
        OasisMiniSelectEntity(coordinator, descriptor) for descriptor in DESCRIPTORS
    ]
    if coordinator.device.access_token:
        entities.extend(
            OasisMiniSelectEntity(coordinator, descriptor)
            for descriptor in CLOUD_DESCRIPTORS
        )
    async_add_entities(entities)

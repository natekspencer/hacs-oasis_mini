"""Oasis device select entity."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OasisDeviceConfigEntry, setup_platform_from_coordinator
from .coordinator import OasisDeviceCoordinator
from .entity import OasisDeviceEntity
from .pyoasiscontrol import OasisDevice
from .pyoasiscontrol.const import AUTOPLAY_MAP, TRACKS

AUTOPLAY_MAP_LIST = list(AUTOPLAY_MAP)


def playlists_update_handler(entity: OasisDeviceSelectEntity) -> None:
    """Handle playlists updates."""
    # pylint: disable=protected-access
    device = entity.device
    counts = defaultdict(int)
    options = []
    current_option: str | None = None
    for playlist in device._cloud.playlists:
        name = playlist["name"]
        counts[name] += 1
        if counts[name] > 1:
            name = f"{name} ({counts[name]})"
        options.append(name)
        if device.playlist == [pattern["id"] for pattern in playlist["patterns"]]:
            current_option = name
    entity._attr_options = options
    entity._attr_current_option = current_option


def queue_update_handler(entity: OasisDeviceSelectEntity) -> None:
    """Handle queue updates."""
    # pylint: disable=protected-access
    device = entity.device
    counts = defaultdict(int)
    options = []
    for track in device.playlist:
        name = device.playlist_details.get(track, {}).get(
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OasisDeviceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oasis device select using config entry."""

    def make_entities(new_devices: list[OasisDevice]):
        return [
            OasisDeviceSelectEntity(entry.runtime_data, device, descriptor)
            for device in new_devices
            for descriptor in DESCRIPTORS
        ]

    setup_platform_from_coordinator(entry, async_add_entities, make_entities)


@dataclass(frozen=True, kw_only=True)
class OasisDeviceSelectEntityDescription(SelectEntityDescription):
    """Oasis device select entity description."""

    current_value: Callable[[OasisDevice], Any]
    select_fn: Callable[[OasisDevice, int], Awaitable[None]]
    update_handler: Callable[[OasisDeviceSelectEntity], None] | None = None


DESCRIPTORS = (
    OasisDeviceSelectEntityDescription(
        key="autoplay",
        translation_key="autoplay",
        entity_category=EntityCategory.CONFIG,
        options=AUTOPLAY_MAP_LIST,
        current_value=lambda device: str(device.autoplay),
        select_fn=lambda device, index: (
            device.async_set_autoplay(AUTOPLAY_MAP_LIST[index])
        ),
    ),
    OasisDeviceSelectEntityDescription(
        key="playlists",
        translation_key="playlist",
        current_value=lambda device: (device._cloud.playlists, device.playlist.copy()),
        select_fn=lambda device, index: device.async_set_playlist(
            [pattern["id"] for pattern in device._cloud.playlists[index]["patterns"]]
        ),
        update_handler=playlists_update_handler,
    ),
    OasisDeviceSelectEntityDescription(
        key="queue",
        translation_key="queue",
        current_value=lambda device: (device.playlist.copy(), device.playlist_index),
        select_fn=lambda device, index: device.async_change_track(index),
        update_handler=queue_update_handler,
    ),
)


class OasisDeviceSelectEntity(OasisDeviceEntity, SelectEntity):
    """Oasis device select entity."""

    entity_description: OasisDeviceSelectEntityDescription
    _current_value: Any | None = None

    def __init__(
        self,
        coordinator: OasisDeviceCoordinator,
        device: OasisDevice,
        description: EntityDescription,
    ) -> None:
        """Construct an Oasis device select entity."""
        super().__init__(coordinator, device, description)
        self._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.device, self.options.index(option))

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
            self._attr_current_option = str(
                getattr(self.device, self.entity_description.key)
            )
        if self.hass:
            return super()._handle_coordinator_update()

"""Oasis Mini media player entity."""

from __future__ import annotations

from datetime import datetime
import math

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity

BRIGHTNESS_SCALE = (1, 200)


class OasisMiniMediaPlayerEntity(OasisMiniEntity, MediaPlayerEntity):
    """Oasis Mini media player entity."""

    _attr_media_image_remotely_accessible = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.REPEAT_SET
    )

    @property
    def media_content_type(self) -> MediaType:
        """Content type of current playing media."""
        return MediaType.IMAGE

    @property
    def media_duration(self) -> int:
        """Duration of current playing media in seconds."""
        if (
            track_details := self.device._current_track_details
        ) and "reduced_svg_content" in track_details:
            return track_details["reduced_svg_content"].get("1")
        return math.ceil(self.media_position / 0.99)

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if (
            track_details := self.device._current_track_details
        ) and "image" in track_details:
            return f"https://app.grounded.so/uploads/{track_details['image']}"
        return None

    @property
    def media_position(self) -> int:
        """Position of current playing media in seconds."""
        return self.device.progress

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When was the position of the current playing media valid."""
        return self.coordinator.last_updated

    @property
    def media_title(self) -> str:
        """Title of current playing media."""
        if track_details := self.device._current_track_details:
            return track_details.get("name", self.device.current_track_id)
        return f"Unknown Title (#{self.device.current_track_id})"

    @property
    def repeat(self) -> RepeatMode:
        """Return current repeat mode."""
        if self.device.repeat_playlist:
            return RepeatMode.ALL
        return RepeatMode.OFF

    @property
    def state(self) -> MediaPlayerState:
        """State of the player."""
        status_code = self.device.status_code
        if status_code in (3, 13):
            return MediaPlayerState.BUFFERING
        if status_code in (2, 5):
            return MediaPlayerState.PAUSED
        if status_code == 4:
            return MediaPlayerState.PLAYING
        return MediaPlayerState.STANDBY

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.device.async_pause()
        await self.coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.device.async_play()
        await self.coordinator.async_request_refresh()

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self.device.async_set_repeat_playlist(
            repeat != RepeatMode.OFF
            and not (repeat == RepeatMode.ONE and self.repeat == RepeatMode.ALL)
        )
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if (index := self.device.playlist_index + 1) >= len(self.device.playlist):
            index = 0
        return await self.device.async_change_track(index)


DESCRIPTOR = MediaPlayerEntityDescription(key="oasis_mini", name=None)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Oasis Mini media_players using config entry."""
    coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OasisMiniMediaPlayerEntity(coordinator, entry, DESCRIPTOR)])

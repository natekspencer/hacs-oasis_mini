"""Oasis Mini media player entity."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity
from .pyoasismini.const import TRACKS

_LOGGER = logging.getLogger(__name__)


class OasisMiniMediaPlayerEntity(OasisMiniEntity, MediaPlayerEntity):
    """Oasis Mini media player entity."""

    _attr_media_image_remotely_accessible = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.MEDIA_ENQUEUE
        | MediaPlayerEntityFeature.CLEAR_PLAYLIST
        | MediaPlayerEntityFeature.REPEAT_SET
    )

    @property
    def media_content_type(self) -> MediaType:
        """Content type of current playing media."""
        return MediaType.IMAGE

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        if (track := self.device.track) and "reduced_svg_content" in track:
            return track["reduced_svg_content"].get("1")
        return None

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        if not (track := self.device.track):
            track = TRACKS.get(self.device.track_id)
        if track and "image" in track:
            return f"https://app.grounded.so/uploads/{track['image']}"
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
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if not self.device.track_id:
            return None
        if not (track := self.device.track):
            track = TRACKS.get(self.device.track_id, {})
        return track.get("name", f"Unknown Title (#{self.device.track_id})")

    @property
    def repeat(self) -> RepeatMode:
        """Return current repeat mode."""
        return RepeatMode.ALL if self.device.repeat_playlist else RepeatMode.OFF

    @property
    def state(self) -> MediaPlayerState:
        """State of the player."""
        status_code = self.device.status_code
        if self.device.error or status_code in (9, 11):
            return MediaPlayerState.OFF
        if status_code == 2:
            return MediaPlayerState.IDLE
        if status_code in (3, 13):
            return MediaPlayerState.BUFFERING
        if status_code == 4:
            return MediaPlayerState.PLAYING
        if status_code == 5:
            return MediaPlayerState.PAUSED
        if status_code == 15:
            return MediaPlayerState.ON
        return MediaPlayerState.IDLE

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.device.async_pause()
        await self.coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.device.async_play()
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.device.async_stop()
        await self.coordinator.async_request_refresh()

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self.device.async_set_repeat_playlist(
            repeat != RepeatMode.OFF
            and not (repeat == RepeatMode.ONE and self.repeat == RepeatMode.ALL)
        )
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if (index := self.device.playlist_index - 1) < 0:
            index = len(self.device.playlist) - 1
        await self.device.async_change_track(index)
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if (index := self.device.playlist_index + 1) >= len(self.device.playlist):
            index = 0
        await self.device.async_change_track(index)
        await self.coordinator.async_request_refresh()

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        **kwargs: Any,
    ) -> None:
        """Play a piece of media."""
        if media_id not in map(str, TRACKS):
            media_id = next(
                (
                    id
                    for id, info in TRACKS.items()
                    if info["name"].lower() == media_id.lower()
                ),
                media_id,
            )
        try:
            track = int(media_id)
        except ValueError as err:
            raise ServiceValidationError(f"Invalid media: {media_id}") from err

        device = self.device
        enqueue = MediaPlayerEnqueue.NEXT if not enqueue else enqueue
        if enqueue == MediaPlayerEnqueue.REPLACE:
            await device.async_set_playlist([track])
        else:
            await device.async_add_track_to_playlist(track)

        if enqueue in (MediaPlayerEnqueue.NEXT, MediaPlayerEnqueue.PLAY):
            # Move track to next item in the playlist
            if (index := (len(device.playlist) - 1)) != device.playlist_index:
                if index != (
                    _next := min(device.playlist_index + 1, len(device.playlist) - 1)
                ):
                    await device.async_move_track(index, _next)
                if enqueue == MediaPlayerEnqueue.PLAY:
                    await device.async_change_track(_next)

        if (
            enqueue in (MediaPlayerEnqueue.PLAY, MediaPlayerEnqueue.REPLACE)
            and device.status_code != 4
        ):
            await device.async_play()

        await self.coordinator.async_request_refresh()

    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        await self.device.async_clear_playlist()
        await self.coordinator.async_request_refresh()


DESCRIPTOR = MediaPlayerEntityDescription(key="oasis_mini", name=None)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Oasis Mini media_players using config entry."""
    coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OasisMiniMediaPlayerEntity(coordinator, entry, DESCRIPTOR)])

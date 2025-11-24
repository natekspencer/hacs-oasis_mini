"""Oasis device media player entity."""

from __future__ import annotations

from datetime import datetime
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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OasisDeviceConfigEntry, setup_platform_from_coordinator
from .const import DOMAIN
from .entity import OasisDeviceEntity
from .helpers import get_track_id
from .pyoasiscontrol import OasisDevice


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: OasisDeviceConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oasis device media_players using config entry."""

    def make_entities(new_devices: list[OasisDevice]):
        """
        Create media player entities for the given Oasis devices.

        Parameters:
            new_devices (list[OasisDevice]): Devices to wrap as media player entities.

        Returns:
            list[OasisDeviceMediaPlayerEntity]: Media player entities corresponding to each device.
        """
        return [
            OasisDeviceMediaPlayerEntity(entry.runtime_data, device, DESCRIPTOR)
            for device in new_devices
        ]

    setup_platform_from_coordinator(entry, async_add_entities, make_entities)


DESCRIPTOR = MediaPlayerEntityDescription(key="oasis_mini", name=None)


class OasisDeviceMediaPlayerEntity(OasisDeviceEntity, MediaPlayerEntity):
    """Oasis device media player entity."""

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
        if (track := self.device.track) and "reduced_svg_content_new" in track:
            return track["reduced_svg_content_new"]
        return None

    @property
    def media_image_url(self) -> str | None:
        """
        URL of the image representing the currently playing media.

        Returns:
            The image URL as a string, or `None` if no image is available.
        """
        return self.device.track_image_url

    @property
    def media_position(self) -> int:
        """
        Playback position of the current media in seconds.

        Returns:
            int: Position in seconds of the currently playing media.
        """
        return self.device.progress

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When was the position of the current playing media valid."""
        return self.coordinator.last_updated

    @property
    def media_title(self) -> str | None:
        """
        Provide the title of the currently playing track.

        Returns:
            str | None: The track title, or None if no title is available.
        """
        return self.device.track_name

    @property
    def repeat(self) -> RepeatMode:
        """
        Get the current repeat mode for the device.

        Returns:
            `RepeatMode.ALL` if the device is configured to repeat the playlist, `RepeatMode.OFF` otherwise.
        """
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

    def abort_if_busy(self) -> None:
        """Abort if the device is currently busy."""
        if self.device.busy:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="device_busy",
                translation_placeholders={"name": self._friendly_name_internal()},
            )

    async def async_media_pause(self) -> None:
        """
        Pause playback on the device.

        Raises:
            ServiceValidationError: If the device is busy and cannot accept commands.
        """
        self.abort_if_busy()
        await self.device.async_pause()

    async def async_media_play(self) -> None:
        """
        Start playback on the device.

        Raises:
            ServiceValidationError: If the device is currently busy.
        """
        self.abort_if_busy()
        await self.device.async_play()

    async def async_media_stop(self) -> None:
        """
        Stop playback on the Oasis device.

        Raises:
            ServiceValidationError: If the device is currently busy.
        """
        self.abort_if_busy()
        await self.device.async_stop()

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """
        Set the device playlist repeat behavior.

        Enables or disables looping of the playlist according to the provided RepeatMode:
        - RepeatMode.OFF disables playlist repeat.
        - RepeatMode.ALL enables playlist repeat for the entire playlist.
        - RepeatMode.ONE enables single-track repeat, except when the device is currently repeating the entire playlist; in that case the playlist repeat is disabled to preserve single-track semantics.

        Parameters:
            repeat (RepeatMode): The desired repeat mode to apply to the device playlist.
        """
        await self.device.async_set_repeat_playlist(
            repeat != RepeatMode.OFF
            and not (repeat == RepeatMode.ONE and self.repeat == RepeatMode.ALL)
        )

    async def async_media_previous_track(self) -> None:
        """
        Move playback to the previous track in the device's playlist, wrapping to the last track when currently at the first.

        Raises:
            ServiceValidationError: If the device is busy.
        """
        self.abort_if_busy()
        if (index := self.device.playlist_index - 1) < 0:
            index = len(self.device.playlist) - 1
        await self.device.async_change_track(index)

    async def async_media_next_track(self) -> None:
        """
        Advance the device to the next track in its playlist, wrapping to the first track when at the end.

        Raises:
            ServiceValidationError: if the device is busy.
        """
        self.abort_if_busy()
        if (index := self.device.playlist_index + 1) >= len(self.device.playlist):
            index = 0
        await self.device.async_change_track(index)

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Play or enqueue one or more Oasis tracks on the device.

        Validates the media type and parses one or more track identifiers from `media_id`, then updates the device playlist according to `enqueue`. Depending on the enqueue mode the method can replace the playlist, append tracks, move appended tracks to the next play position, and optionally start playback.

        Parameters:
            media_type (MediaType | str): The media type being requested.
            media_id (str): A comma-separated string of track identifiers.
            enqueue (MediaPlayerEnqueue | None): How to insert the tracks into the playlist; if omitted defaults to NEXT.

        Raises:
            ServiceValidationError: If the device is busy, if `media_type` is a playlist (playlists are unsupported), or if `media_id` does not contain any valid track identifiers.
        """
        self.abort_if_busy()
        if media_type == MediaType.PLAYLIST:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="playlists_unsupported"
            )
        else:
            track = list(filter(None, map(get_track_id, media_id.split(","))))
            if not track:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_media",
                    translation_placeholders={"media": media_id},
                )

        device = self.device
        enqueue = MediaPlayerEnqueue.NEXT if not enqueue else enqueue
        if enqueue == MediaPlayerEnqueue.REPLACE:
            await device.async_set_playlist(track)
        else:
            await device.async_add_track_to_playlist(track)

        if enqueue in (MediaPlayerEnqueue.NEXT, MediaPlayerEnqueue.PLAY):
            # Move track to next item in the playlist
            new_tracks = 1 if isinstance(track, int) else len(track)
            if (index := (len(device.playlist) - new_tracks)) != device.playlist_index:
                if index != (
                    _next := min(
                        device.playlist_index + 1, len(device.playlist) - new_tracks
                    )
                ):
                    await device.async_move_track(index, _next)
                if enqueue == MediaPlayerEnqueue.PLAY:
                    await device.async_change_track(_next)

        if (
            enqueue in (MediaPlayerEnqueue.PLAY, MediaPlayerEnqueue.REPLACE)
            and device.status_code != 4
        ):
            await device.async_play()

    async def async_clear_playlist(self) -> None:
        """
        Clear the device's playlist.

        Raises:
            ServiceValidationError: If the device is busy and cannot accept commands.
        """
        self.abort_if_busy()
        await self.device.async_clear_playlist()

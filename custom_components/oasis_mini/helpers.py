"""Helpers for the Oasis Mini integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST

from .pyoasismini import TRACKS, OasisMini

_LOGGER = logging.getLogger(__name__)


def create_client(data: dict[str, Any]) -> OasisMini:
    """Create a Oasis Mini local client."""
    return OasisMini(data[CONF_HOST], data.get(CONF_ACCESS_TOKEN))


async def add_and_play_track(device: OasisMini, track: int) -> None:
    """Add and play a track."""
    if track not in device.playlist:
        await device.async_add_track_to_playlist(track)

    # Move track to next item in the playlist and then select it
    if (index := device.playlist.index(track)) != device.playlist_index:
        if index != (_next := min(device.playlist_index + 1, len(device.playlist) - 1)):
            await device.async_move_track(index, _next)
        await device.async_change_track(_next)

    if device.status_code != 4:
        await device.async_play()


def get_track_id(track: str) -> int | None:
    """Get a track id.

    `track` can be either an id or title
    """
    track = track.lower().strip()
    if track not in map(str, TRACKS):
        track = next(
            (id for id, info in TRACKS.items() if info["name"].lower() == track), track
        )

    try:
        return int(track)
    except ValueError:
        _LOGGER.warning("Invalid track: %s", track)
        return None

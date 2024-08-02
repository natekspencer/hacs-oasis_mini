"""Helpers for the Oasis Mini integration."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST

from .pyoasismini import OasisMini


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

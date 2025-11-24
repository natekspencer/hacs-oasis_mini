"""Helpers for the Oasis devices integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .pyoasiscontrol import OasisCloudClient, OasisDevice
from .pyoasiscontrol.const import STATUS_PLAYING, TRACKS

_LOGGER = logging.getLogger(__name__)


def create_client(hass: HomeAssistant, data: dict[str, Any]) -> OasisCloudClient:
    """
    Create an Oasis cloud client configured with the Home Assistant HTTP session and access token.

    Parameters:
        hass (HomeAssistant): Home Assistant instance used to obtain the shared HTTP client session.
        data (dict[str, Any]): Configuration mapping; the function reads the `CONF_ACCESS_TOKEN` key for the cloud access token.

    Returns:
        An `OasisCloudClient` initialized with the Home Assistant HTTP session and the configured access token.
    """
    session = async_get_clientsession(hass)
    return OasisCloudClient(session=session, access_token=data.get(CONF_ACCESS_TOKEN))


async def add_and_play_track(device: OasisDevice, track: int) -> None:
    """
    Ensure a track is present in the device playlist, position it as the next item, select it, and start playback if necessary.

    Adds the specified track to the device playlist if missing, waits up to 10 seconds for the track to appear, moves it to be the next item after the current playlist index if needed, selects that track, and starts playback when the device is not already playing.

    Parameters:
        device (OasisDevice): The target Oasis device.
        track (int): The track id to add and play.

    Raises:
        TimeoutError: If the operation does not complete within 10 seconds.
    """
    async with asyncio.timeout(10):
        if track not in device.playlist:
            await device.async_add_track_to_playlist(track)

        # Wait for device state to reflect the newly added track
        while track not in device.playlist:
            await asyncio.sleep(0.1)

        # Ensure the track is positioned immediately after the current track and select it
        if (index := device.playlist.index(track)) != device.playlist_index:
            # Calculate the position after the current track
            if index != (
                _next := min(device.playlist_index + 1, len(device.playlist) - 1)
            ):
                await device.async_move_track(index, _next)
            await device.async_change_track(_next)

        if device.status_code != STATUS_PLAYING:
            await device.async_play()


def get_track_id(track: str) -> int | None:
    """
    Convert a track identifier or title to its integer track id.

    Parameters:
        track: A track reference, either a numeric id as a string or a track title.

    Returns:
        The integer track id if the input is a valid id or matches a known title, `None` if the input is invalid.
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

"""Helpers for the Oasis devices integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import async_timeout

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .pyoasiscontrol import OasisCloudClient, OasisDevice
from .pyoasiscontrol.const import TRACKS

_LOGGER = logging.getLogger(__name__)


def create_client(hass: HomeAssistant, data: dict[str, Any]) -> OasisCloudClient:
    """Create a Oasis cloud client."""
    session = async_get_clientsession(hass)
    return OasisCloudClient(session=session, access_token=data.get(CONF_ACCESS_TOKEN))


async def add_and_play_track(device: OasisDevice, track: int) -> None:
    """Add and play a track."""
    async with async_timeout.timeout(10):
        if track not in device.playlist:
            await device.async_add_track_to_playlist(track)

        while track not in device.playlist:
            await asyncio.sleep(0.1)

        # Move track to next item in the playlist and then select it
        if (index := device.playlist.index(track)) != device.playlist_index:
            if index != (
                _next := min(device.playlist_index + 1, len(device.playlist) - 1)
            ):
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

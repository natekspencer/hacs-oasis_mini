"""Oasis HTTP client (per-device)."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession

from ..device import OasisDevice
from .transport import OasisClientProtocol

_LOGGER = logging.getLogger(__name__)


class OasisHttpClient(OasisClientProtocol):
    """HTTP-based Oasis transport.

    This client is typically used per-device (per host/IP).
    It implements the OasisClientProtocol so OasisDevice can delegate
    all commands through it.
    """

    def __init__(self, host: str, session: ClientSession | None = None) -> None:
        self._host = host
        self._session: ClientSession | None = session
        self._owns_session: bool = session is None

    @property
    def session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession()
            self._owns_session = True
        return self._session

    async def async_close(self) -> None:
        """Close owned session."""
        if self._session and not self._session.closed and self._owns_session:
            await self._session.close()

    @property
    def url(self) -> str:
        # These devices are plain HTTP, no TLS
        return f"http://{self._host}/"

    async def _async_request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Low-level HTTP helper."""
        session = self.session
        _LOGGER.debug(
            "%s %s",
            method,
            session._build_url(url).update_query(  # pylint: disable=protected-access
                kwargs.get("params"),
            ),
        )
        resp = await session.request(method, url, **kwargs)

        if resp.status == 200:
            if resp.content_type == "text/plain":
                return await resp.text()
            if resp.content_type == "application/json":
                return await resp.json()
            return None

        resp.raise_for_status()

    async def _async_get(self, **kwargs: Any) -> str | None:
        return await self._async_request("GET", self.url, **kwargs)

    async def _async_command(self, **kwargs: Any) -> str | None:
        result = await self._async_get(**kwargs)
        _LOGGER.debug("Result: %s", result)
        return result

    async def async_get_mac_address(self, device: OasisDevice) -> str | None:
        """Fetch MAC address via HTTP GETMAC."""
        try:
            mac = await self._async_get(params={"GETMAC": ""})
            if isinstance(mac, str):
                return mac.strip()
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Failed to get MAC address via HTTP for %s", device.serial_number
            )
        return None

    async def async_send_ball_speed_command(
        self,
        device: OasisDevice,
        speed: int,
    ) -> None:
        await self._async_command(params={"WRIOASISSPEED": speed})

    async def async_send_led_command(
        self,
        device: OasisDevice,
        led_effect: str,
        color: str,
        led_speed: int,
        brightness: int,
    ) -> None:
        payload = f"{led_effect};0;{color};{led_speed};{brightness}"
        await self._async_command(params={"WRILED": payload})

    async def async_send_sleep_command(self, device: OasisDevice) -> None:
        await self._async_command(params={"CMDSLEEP": ""})

    async def async_send_move_job_command(
        self,
        device: OasisDevice,
        from_index: int,
        to_index: int,
    ) -> None:
        await self._async_command(params={"MOVEJOB": f"{from_index};{to_index}"})

    async def async_send_change_track_command(
        self,
        device: OasisDevice,
        index: int,
    ) -> None:
        await self._async_command(params={"CMDCHANGETRACK": index})

    async def async_send_add_joblist_command(
        self,
        device: OasisDevice,
        tracks: list[int],
    ) -> None:
        # The old code passed the list directly; if the device expects CSV:
        await self._async_command(params={"ADDJOBLIST": ",".join(map(str, tracks))})

    async def async_send_set_playlist_command(
        self,
        device: OasisDevice,
        playlist: list[int],
    ) -> None:
        await self._async_command(params={"WRIJOBLIST": ",".join(map(str, playlist))})
        # optional: optimistic state update
        device.update_from_status_dict({"playlist": playlist})

    async def async_send_set_repeat_playlist_command(
        self,
        device: OasisDevice,
        repeat: bool,
    ) -> None:
        await self._async_command(params={"WRIREPEATJOB": 1 if repeat else 0})

    async def async_send_set_autoplay_command(
        self,
        device: OasisDevice,
        option: str,
    ) -> None:
        await self._async_command(params={"WRIWAITAFTER": option})

    async def async_send_upgrade_command(
        self,
        device: OasisDevice,
        beta: bool,
    ) -> None:
        await self._async_command(params={"CMDUPGRADE": 1 if beta else 0})

    async def async_send_play_command(self, device: OasisDevice) -> None:
        await self._async_command(params={"CMDPLAY": ""})

    async def async_send_pause_command(self, device: OasisDevice) -> None:
        await self._async_command(params={"CMDPAUSE": ""})

    async def async_send_stop_command(self, device: OasisDevice) -> None:
        await self._async_command(params={"CMDSTOP": ""})

    async def async_send_reboot_command(self, device: OasisDevice) -> None:
        await self._async_command(params={"CMDBOOT": ""})

    async def async_get_status(self, device: OasisDevice) -> None:
        """Fetch status via GETSTATUS and update the device."""
        raw_status = await self._async_get(params={"GETSTATUS": ""})
        if raw_status is None:
            return

        _LOGGER.debug("Status for %s: %s", device.serial_number, raw_status)
        device.update_from_status_string(raw_status)

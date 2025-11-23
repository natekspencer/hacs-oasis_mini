from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..device import OasisDevice


@runtime_checkable
class OasisClientProtocol(Protocol):
    """Transport/client interface for an Oasis device.

    Concrete implementations:
    - MQTT client (remote connection)
    - HTTP client (direct LAN)
    """

    async def async_get_mac_address(self, device: OasisDevice) -> str | None: ...

    async def async_send_auto_clean_command(
        self, device: OasisDevice, auto_clean: bool
    ) -> None: ...

    async def async_send_ball_speed_command(
        self,
        device: OasisDevice,
        speed: int,
    ) -> None: ...

    async def async_send_led_command(
        self,
        device: OasisDevice,
        led_effect: str,
        color: str,
        led_speed: int,
        brightness: int,
    ) -> None: ...

    async def async_send_sleep_command(self, device: OasisDevice) -> None: ...

    async def async_send_move_job_command(
        self,
        device: OasisDevice,
        from_index: int,
        to_index: int,
    ) -> None: ...

    async def async_send_change_track_command(
        self,
        device: OasisDevice,
        index: int,
    ) -> None: ...

    async def async_send_add_joblist_command(
        self,
        device: OasisDevice,
        tracks: list[int],
    ) -> None: ...

    async def async_send_set_playlist_command(
        self,
        device: OasisDevice,
        playlist: list[int],
    ) -> None: ...

    async def async_send_set_repeat_playlist_command(
        self,
        device: OasisDevice,
        repeat: bool,
    ) -> None: ...

    async def async_send_set_autoplay_command(
        self,
        device: OasisDevice,
        option: str,
    ) -> None: ...

    async def async_send_upgrade_command(
        self,
        device: OasisDevice,
        beta: bool,
    ) -> None: ...

    async def async_send_play_command(self, device: OasisDevice) -> None: ...

    async def async_send_pause_command(self, device: OasisDevice) -> None: ...

    async def async_send_stop_command(self, device: OasisDevice) -> None: ...

    async def async_send_reboot_command(self, device: OasisDevice) -> None: ...

    async def async_get_all(self, device: OasisDevice) -> None: ...

    async def async_get_status(self, device: OasisDevice) -> None: ...

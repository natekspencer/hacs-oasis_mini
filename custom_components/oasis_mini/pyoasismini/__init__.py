"""Oasis Mini API client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Final
from urllib.parse import urljoin

from aiohttp import ClientResponseError, ClientSession

from .const import TRACKS
from .utils import _bit_to_bool, _parse_int, decrypt_svg_content

_LOGGER = logging.getLogger(__name__)

STATUS_CODE_MAP = {
    0: "booting",  # maybe?
    2: "stopped",
    3: "centering",
    4: "playing",
    5: "paused",
    6: "sleeping",
    9: "error",
    11: "updating",
    13: "downloading",
    14: "busy",
    15: "live",
}

AUTOPLAY_MAP = {
    "0": "on",
    "1": "off",
    "2": "5 minutes",
    "3": "10 minutes",
    "4": "30 minutes",
    "5": "24 hours",
}

LED_EFFECTS: Final[dict[str, str]] = {
    "0": "Solid",
    "1": "Rainbow",
    "2": "Glitter",
    "3": "Confetti",
    "4": "Sinelon",
    "5": "BPM",
    "6": "Juggle",
    "7": "Theater",
    "8": "Color Wipe",
    "9": "Sparkle",
    "10": "Comet",
    "11": "Follow Ball",
    "12": "Follow Rainbow",
    "13": "Chasing Comet",
    "14": "Gradient Follow",
}

CLOUD_BASE_URL = "https://app.grounded.so"

BALL_SPEED_MAX: Final = 400
BALL_SPEED_MIN: Final = 100
LED_SPEED_MAX: Final = 90
LED_SPEED_MIN: Final = -90


class OasisMini:
    """Oasis Mini API client class."""

    _access_token: str | None = None
    _mac_address: str | None = None
    _ip_address: str | None = None
    _playlist: dict[int, dict[str, str]] = {}
    _serial_number: str | None = None
    _software_version: str | None = None
    _track: dict | None = None

    autoplay: str
    brightness: int
    busy: bool
    color: str | None = None
    download_progress: int
    error: int
    led_effect: str
    led_speed: int
    max_brightness: int
    playlist: list[int]
    playlist_index: int
    progress: int
    repeat_playlist: bool
    status_code: int

    def __init__(
        self,
        host: str,
        access_token: str | None = None,
        session: ClientSession | None = None,
    ) -> None:
        """Initialize the client."""
        self._host = host
        self._access_token = access_token
        self._session = session if session else ClientSession()

    @property
    def access_token(self) -> str | None:
        """Return the access token, if any."""
        return self._access_token

    @property
    def mac_address(self) -> str | None:
        """Return the mac address."""
        return self._mac_address

    @property
    def drawing_progress(self) -> float | None:
        """Return the drawing progress percent."""
        if not (self.track and (svg_content := self.track.get("svg_content"))):
            return None
        svg_content = decrypt_svg_content(svg_content)
        paths = svg_content.split("L")
        total = self.track.get("reduced_svg_content", {}).get("1", len(paths))
        percent = (100 * self.progress) / total
        return percent

    @property
    def serial_number(self) -> str | None:
        """Return the serial number."""
        return self._serial_number

    @property
    def session(self) -> ClientSession:
        """Return the session."""
        return self._session

    @property
    def software_version(self) -> str | None:
        """Return the software version."""
        return self._software_version

    @property
    def status(self) -> str:
        """Return the status."""
        return STATUS_CODE_MAP.get(self.status_code, f"Unknown ({self.status_code})")

    @property
    def track(self) -> dict | None:
        """Return the current track info."""
        if self._track and self._track.get("id") == self.track_id:
            return self._track
        return None

    @property
    def track_id(self) -> int | None:
        """Return the current track id."""
        if not self.playlist:
            return None
        i = self.playlist_index
        return self.playlist[0] if i >= len(self.playlist) else self.playlist[i]

    @property
    def url(self) -> str:
        """Return the url."""
        return f"http://{self._host}/"

    async def async_add_track_to_playlist(self, track: int | list[int]) -> None:
        """Add track to playlist."""
        if not track:
            return
        if isinstance(track, int):
            track = [track]
        if 0 in self.playlist:
            playlist = [t for t in self.playlist if t] + track
            return await self.async_set_playlist(playlist)
        await self._async_command(params={"ADDJOBLIST": track})
        self.playlist.extend(track)

    async def async_change_track(self, index: int) -> None:
        """Change the track."""
        if index >= len(self.playlist):
            raise ValueError("Invalid index specified")
        await self._async_command(params={"CMDCHANGETRACK": index})

    async def async_clear_playlist(self) -> None:
        """Clear the playlist."""
        await self.async_set_playlist([])

    async def async_get_ip_address(self) -> str | None:
        """Get the ip address."""
        self._ip_address = await self._async_get(params={"GETIP": ""})
        _LOGGER.debug("IP address: %s", self._ip_address)
        return self._ip_address

    async def async_get_mac_address(self) -> str | None:
        """Get the mac address."""
        self._mac_address = await self._async_get(params={"GETMAC": ""})
        _LOGGER.debug("MAC address: %s", self._mac_address)
        return self._mac_address

    async def async_get_serial_number(self) -> str | None:
        """Get the serial number."""
        self._serial_number = await self._async_get(params={"GETOASISID": ""})
        _LOGGER.debug("Serial number: %s", self._serial_number)
        return self._serial_number

    async def async_get_software_version(self) -> str | None:
        """Get the software version."""
        self._software_version = await self._async_get(params={"GETSOFTWAREVER": ""})
        _LOGGER.debug("Software version: %s", self._software_version)
        return self._software_version

    async def async_get_status(self) -> str:
        """Get the status from the device."""
        raw_status = await self._async_get(params={"GETSTATUS": ""})
        _LOGGER.debug("Status: %s", raw_status)
        values = raw_status.split(";")
        playlist = [_parse_int(track) for track in values[3].split(",") if track]
        shift = len(values) - 18 if len(values) > 17 else 0
        status = {
            "status_code": _parse_int(values[0]),  # see status code map
            "error": _parse_int(values[1]),  # noqa: E501; error, 0 = none, and 10 = ?, 18 = can't download?
            "ball_speed": _parse_int(values[2]),  # 200 - 1000
            "playlist": playlist,
            "playlist_index": min(_parse_int(values[4]), len(playlist)),  # noqa: E501; index of above
            "progress": _parse_int(values[5]),  # 0 - max svg path
            "led_effect": values[6],  # led effect (code lookup)
            "led_color_id": values[7],  # led color id?
            "led_speed": _parse_int(values[8]),  # -90 - 90
            "brightness": _parse_int(values[9]),  # noqa: E501; 0 - 200 in app, but seems to be 0 (off) to 304 (max), then repeats
            "color": values[10] if "#" in values[10] else None,  # hex color code
            "busy": _bit_to_bool(values[11 + shift]),  # noqa: E501; device is busy (downloading track, centering, software update)?
            "download_progress": _parse_int(values[12 + shift]),
            "max_brightness": _parse_int(values[13 + shift]),
            "wifi_connected": _bit_to_bool(values[14 + shift]),
            "repeat_playlist": _bit_to_bool(values[15 + shift]),
            "autoplay": AUTOPLAY_MAP.get(value := values[16 + shift], value),
            "autoclean": _bit_to_bool(values[17 + shift])
            if len(values) > 17
            else False,
        }
        for key, value in status.items():
            if (old_value := getattr(self, key, None)) != value:
                _LOGGER.debug(
                    "%s changed: '%s' -> '%s'",
                    key.replace("_", " ").capitalize(),
                    old_value,
                    value,
                )
                setattr(self, key, value)
        return raw_status

    async def async_move_track(self, _from: int, _to: int) -> None:
        """Move a track in the playlist."""
        await self._async_command(params={"MOVEJOB": f"{_from};{_to}"})

    async def async_pause(self) -> None:
        """Send pause command."""
        await self._async_command(params={"CMDPAUSE": ""})

    async def async_play(self) -> None:
        """Send play command."""
        if self.status_code == 15:
            await self.async_stop()
        if self.track_id:
            await self._async_command(params={"CMDPLAY": ""})

    async def async_reboot(self) -> None:
        """Send reboot command."""

        async def _no_response_needed(coro: Awaitable) -> None:
            try:
                await coro
            except Exception as ex:
                _LOGGER.error(ex)

        reboot = self._async_command(params={"CMDBOOT": ""})
        asyncio.create_task(_no_response_needed(reboot))

    async def async_set_ball_speed(self, speed: int) -> None:
        """Set the Oasis Mini ball speed."""
        if not BALL_SPEED_MIN <= speed <= BALL_SPEED_MAX:
            raise ValueError("Invalid speed specified")

        await self._async_command(params={"WRIOASISSPEED": speed})

    async def async_set_led(
        self,
        *,
        led_effect: str | None = None,
        color: str | None = None,
        led_speed: int | None = None,
        brightness: int | None = None,
    ) -> None:
        """Set the Oasis Mini led."""
        if led_effect is None:
            led_effect = self.led_effect
        if color is None:
            color = self.color or "#ffffff"
        if led_speed is None:
            led_speed = self.led_speed
        if brightness is None:
            brightness = self.brightness

        if led_effect not in LED_EFFECTS:
            raise ValueError("Invalid led effect specified")
        if not LED_SPEED_MIN <= led_speed <= LED_SPEED_MAX:
            raise ValueError("Invalid led speed specified")
        if not 0 <= brightness <= self.max_brightness:
            raise ValueError("Invalid brightness specified")

        await self._async_command(
            params={"WRILED": f"{led_effect};0;{color};{led_speed};{brightness}"}
        )

    async def async_set_autoplay(self, option: bool | int | str) -> None:
        """Set autoplay."""
        if isinstance(option, bool):
            option = 0 if option else 1
        if str(option) not in AUTOPLAY_MAP:
            raise ValueError("Invalid pause option specified")
        await self._async_command(params={"WRIWAITAFTER": option})

    async def async_set_playlist(self, playlist: list[int] | int) -> None:
        """Set the playlist."""
        if isinstance(playlist, int):
            playlist = [playlist]
        if is_playing := (self.status_code == 4):
            await self.async_stop()
        await self._async_command(params={"WRIJOBLIST": ",".join(map(str, playlist))})
        self.playlist = playlist
        if is_playing:
            await self.async_play()

    async def async_set_repeat_playlist(self, repeat: bool) -> None:
        """Set repeat playlist."""
        await self._async_command(params={"WRIREPEATJOB": 1 if repeat else 0})

    async def async_sleep(self) -> None:
        """Send sleep command."""
        await self._async_command(params={"CMDSLEEP": ""})

    async def async_stop(self) -> None:
        """Send stop command."""
        await self._async_command(params={"CMDSTOP": ""})

    async def async_upgrade(self, beta: bool = False) -> None:
        """Trigger a software upgrade."""
        await self._async_command(params={"CMDUPGRADE": 1 if beta else 0})

    async def async_cloud_login(self, email: str, password: str) -> None:
        """Login via the cloud."""
        response = await self._async_request(
            "POST",
            urljoin(CLOUD_BASE_URL, "api/auth/login"),
            json={"email": email, "password": password},
        )
        self._access_token = response.get("access_token")

    async def async_cloud_logout(self) -> None:
        """Login via the cloud."""
        await self._async_cloud_request("GET", "api/auth/logout")

    async def async_cloud_get_track_info(self, track_id: int) -> dict[str, Any] | None:
        """Get cloud track info."""
        try:
            return await self._async_cloud_request("GET", f"api/track/{track_id}")
        except ClientResponseError as err:
            if err.status == 404:
                return {"id": track_id, "name": f"Unknown Title (#{track_id})"}
        except Exception as ex:
            _LOGGER.exception(ex)
        return None

    async def async_cloud_get_tracks(
        self, tracks: list[int] | None = None
    ) -> list[dict[str, Any]]:
        """Get tracks info from the cloud"""
        response = await self._async_cloud_request(
            "GET", "api/track", params={"ids[]": tracks or []}
        )
        if not response:
            return None
        track_details = response.get("data", [])
        while next_page_url := response.get("next_page_url"):
            response = await self._async_cloud_request("GET", next_page_url)
            track_details += response.get("data", [])
        return track_details

    async def async_cloud_get_latest_software_details(self) -> dict[str, int | str]:
        """Get the latest software details from the cloud."""
        return await self._async_cloud_request("GET", "api/software/last-version")

    async def async_get_current_track_details(self) -> dict | None:
        """Get current track info, refreshing if needed."""
        track_id = self.track_id
        if (track := self._track) and track.get("id") == track_id:
            return track
        if track_id:
            self._track = await self.async_cloud_get_track_info(track_id)
            if not self._track:
                self._track = TRACKS.get(
                    track_id, {"id": track_id, "name": f"Unknown Title (#{track_id})"}
                )
        return self._track

    async def async_get_playlist_details(self) -> dict[int, dict[str, str]]:
        """Get playlist info."""
        if set(self.playlist).difference(self._playlist.keys()):
            tracks = await self.async_cloud_get_tracks(self.playlist)
            all_tracks = TRACKS | {
                track["id"]: {
                    "name": track["name"],
                    "author": ((track.get("author") or {}).get("person") or {}).get(
                        "name", "Oasis Mini"
                    ),
                    "image": track["image"],
                }
                for track in tracks
            }
            for track in self.playlist:
                self._playlist[track] = all_tracks.get(
                    track, {"name": f"Unknown Title (#{track})"}
                )
        return self._playlist

    async def _async_cloud_request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Perform a cloud request."""
        if not self.access_token:
            return

        return await self._async_request(
            method,
            urljoin(CLOUD_BASE_URL, url),
            headers={"Authorization": f"Bearer {self.access_token}"},
            **kwargs,
        )

    async def _async_command(self, **kwargs: Any) -> str | None:
        """Send a command to the device."""
        result = await self._async_get(**kwargs)
        _LOGGER.debug("Result: %s", result)

    async def _async_get(self, **kwargs: Any) -> str | None:
        """Perform a GET request."""
        return await self._async_request("GET", self.url, **kwargs)

    async def _async_request(self, method: str, url: str, **kwargs) -> Any:
        """Perform a request."""
        _LOGGER.debug(
            "%s %s",
            method,
            self._session._build_url(url).update_query(  # pylint: disable=protected-access
                kwargs.get("params")
            ),
        )
        response = await self._session.request(method, url, **kwargs)
        if response.status == 200:
            if response.content_type == "application/json":
                return await response.json()
            if response.content_type == "text/plain":
                return await response.text()
            return None
        response.raise_for_status()

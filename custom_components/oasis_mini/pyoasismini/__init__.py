"""Oasis Mini API client."""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Final
from urllib.parse import urljoin

from aiohttp import ClientSession

from .utils import _bit_to_bool

_LOGGER = logging.getLogger(__name__)

STATUS_CODE_MAP = {
    2: "stopped",
    3: "centering",
    4: "running",
    5: "paused",
    9: "error",
    13: "downloading",
}

ATTRIBUTES: Final[list[tuple[str, Callable[[str], Any]]]] = [
    ("status_code", int),  # see status code map
    ("error", str),  # error, 0 = none, and 10 = ?, 18 = can't download?
    ("ball_speed", int),  # 200 - 800
    ("playlist", lambda value: [int(track) for track in value.split(",")]),  # noqa: E501 # comma separated track ids
    ("playlist_index", int),  # index of above
    ("progress", int),  # 0 - max svg path
    ("led_effect", str),  # led effect (code lookup)
    ("led_color_id", str),  # led color id?
    ("led_speed", int),  # -90 - 90
    ("brightness", int),  # noqa: E501 # 0 - 200 in app, but seems to be 0 (off) to 304 (max), then repeats
    ("color", str),  # hex color code
    ("busy", _bit_to_bool),  # noqa: E501 # device is busy (downloading track, centering, software update)?
    ("download_progress", int),  # 0 - 100%
    ("max_brightness", int),
    ("wifi_connected", _bit_to_bool),
    ("repeat_playlist", _bit_to_bool),
    ("pause_between_tracks", _bit_to_bool),
]

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
CLOUD_API_URL = f"{CLOUD_BASE_URL}/api"


class OasisMini:
    """Oasis Mini API client class."""

    _access_token: str | None = None
    _current_track_details: dict | None = None
    _serial_number: str | None = None
    _software_version: str | None = None

    brightness: int
    color: str
    led_effect: str
    led_speed: int
    max_brightness: int
    playlist: list[int]
    playlist_index: int
    progress: int
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
    def current_track_id(self) -> int:
        """Return the current track."""
        i = self.playlist_index
        return self.playlist[0] if i >= len(self.playlist) else self.playlist[i]

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
    def url(self) -> str:
        """Return the url."""
        return f"http://{self._host}/"

    async def async_add_track_to_playlist(self, track: int) -> None:
        """Add track to playlist."""
        await self._async_command(params={"ADDJOBLIST": track})
        self.playlist.append(track)

    async def async_change_track(self, index: int) -> None:
        """Change the track."""
        if index >= len(self.playlist):
            raise ValueError("Invalid selection")
        await self._async_command(params={"CMDCHANGETRACK": index})

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

    async def async_get_status(self) -> None:
        """Get the status from the device."""
        status = await self._async_get(params={"GETSTATUS": ""})
        _LOGGER.debug("Status: %s", status)
        for index, value in enumerate(status.split(";")):
            attr, func = ATTRIBUTES[index]
            if (old_value := getattr(self, attr, None)) != (value := func(value)):
                _LOGGER.debug("%s changed: '%s' -> '%s'", attr, old_value, value)
                setattr(self, attr, value)
        return status

    async def async_move_track(self, _from: int, _to: int) -> None:
        """Move a track in the playlist."""
        await self._async_command(params={"MOVEJOB": f"{_from};{_to}"})

    async def async_pause(self) -> None:
        """Send pause command."""
        await self._async_command(params={"CMDPAUSE": ""})

    async def async_play(self) -> None:
        """Send play command."""
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
        if not 200 <= speed <= 800:
            raise Exception("Invalid speed specified")

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
            color = self.color
        if led_speed is None:
            led_speed = self.led_speed
        if brightness is None:
            brightness = self.brightness

        if led_effect not in LED_EFFECTS:
            raise Exception("Invalid led effect specified")
        if not -90 <= led_speed <= 90:
            raise Exception("Invalid led speed specified")
        if not 0 <= brightness <= 200:
            raise Exception("Invalid brightness specified")

        await self._async_command(
            params={"WRILED": f"{led_effect};0;{color};{led_speed};{brightness}"}
        )

    async def async_set_pause_between_tracks(self, pause: bool) -> None:
        """Set the Oasis Mini pause between tracks."""
        await self._async_command(params={"WRIWAITAFTER": 1 if pause else 0})

    async def async_set_repeat_playlist(self, repeat: bool) -> None:
        """Set the Oasis Mini repeat playlist."""
        await self._async_command(params={"WRIREPEATJOB": 1 if repeat else 0})

    async def _async_command(self, **kwargs: Any) -> str | None:
        """Send a command request."""
        result = await self._async_get(**kwargs)
        _LOGGER.debug("Result: %s", result)

    async def _async_get(self, **kwargs: Any) -> str | None:
        """Perform a GET request."""
        response = await self._session.get(self.url, **kwargs)
        if response.status == 200 and response.content_type == "text/plain":
            text = await response.text()
            return text
        return None

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
        if not self.access_token:
            return
        await self._async_request(
            "GET",
            urljoin(CLOUD_BASE_URL, "api/auth/logout"),
            headers={"Authorization": f"Bearer {self.access_token}"},
        )

    async def async_cloud_get_track_info(self, track_id: int) -> None:
        """Get cloud track info."""
        if not self.access_token:
            return

        response = await self._async_request(
            "GET",
            urljoin(CLOUD_BASE_URL, f"api/track/{track_id}"),
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        return response

    async def async_cloud_get_tracks(self, tracks: list[int]) -> None:
        """Get cloud tracks."""
        if not self.access_token:
            return

        response = await self._async_request(
            "GET",
            urljoin(CLOUD_BASE_URL, "api/track"),
            headers={"Authorization": f"Bearer {self.access_token}"},
            params={"ids[]": tracks},
        )
        return response

    async def _async_request(self, method: str, url: str, **kwargs) -> Any:
        """Login via the cloud."""
        response = await self._session.request(method, url, **kwargs)
        if response.status == 200:
            if response.headers.get("Content-Type") == "application/json":
                return await response.json()
            return await response.text()
        response.raise_for_status()

    async def async_get_current_track_details(self) -> dict:
        """Get current track info, refreshing if needed."""
        if (track_details := self._current_track_details) and track_details.get(
            "id"
        ) == self.current_track_id:
            return track_details

        self._current_track_details = await self.async_cloud_get_track_info(
            self.current_track_id
        )

    async def async_get_playlist_details(self) -> dict:
        """Get playlist info."""
        return await self.async_cloud_get_tracks(self.playlist)

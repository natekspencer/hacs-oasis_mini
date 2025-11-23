"""Oasis device."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable, Final, Iterable

from .const import (
    ERROR_CODE_MAP,
    LED_EFFECTS,
    STATUS_CODE_MAP,
    STATUS_CODE_SLEEPING,
    TRACKS,
)
from .utils import _bit_to_bool, _parse_int, create_svg, decrypt_svg_content

if TYPE_CHECKING:  # avoid runtime circular imports
    from .clients import OasisCloudClient
    from .clients.transport import OasisClientProtocol

_LOGGER = logging.getLogger(__name__)

BALL_SPEED_MAX: Final = 400
BALL_SPEED_MIN: Final = 100
BRIGHTNESS_DEFAULT: Final = 100
LED_SPEED_MAX: Final = 90
LED_SPEED_MIN: Final = -90

_STATE_FIELDS = (
    "auto_clean",
    "autoplay",
    "ball_speed",
    "brightness",
    "busy",
    "color",
    "download_progress",
    "error",
    "led_effect",
    "led_speed",
    "mac_address",
    "playlist",
    "playlist_index",
    "progress",
    "repeat_playlist",
    "serial_number",
    "software_version",
    "status_code",
)


class OasisDevice:
    """Oasis device model + behavior.

    Transport-agnostic; all I/O is delegated to an attached
    OasisClientProtocol (MQTT, HTTP, etc.) via `attach_client`.
    """

    manufacturer: Final = "Kinetic Oasis"

    def __init__(
        self,
        *,
        model: str | None = None,
        serial_number: str | None = None,
        name: str | None = None,
        ssid: str | None = None,
        ip_address: str | None = None,
        cloud: OasisCloudClient | None = None,
        client: OasisClientProtocol | None = None,
    ) -> None:
        # Transport
        self._cloud = cloud
        self._client = client
        self._listeners: list[Callable[[], None]] = []

        # Details
        self.model = model
        self.serial_number = serial_number
        self.name = name if name else f"{model} {serial_number}"
        self.ssid = ssid
        self.ip_address = ip_address

        # Status
        self.auto_clean: bool = False
        self.autoplay: int = 0
        self.ball_speed: int = BALL_SPEED_MIN
        self._brightness: int = 0
        self.brightness_max: int = 200
        self.brightness_on: int = BRIGHTNESS_DEFAULT
        self.busy: bool = False
        self.color: str | None = None
        self.download_progress: int = 0
        self.error: int = 0
        self.led_color_id: str = "0"
        self.led_effect: str = "0"
        self.led_speed: int = 0
        self.mac_address: str | None = None
        self.playlist: list[int] = []
        self.playlist_index: int = 0
        self.progress: int = 0
        self.repeat_playlist: bool = False
        self.software_version: str | None = None
        self.status_code: int = 0
        self.wifi_connected: bool = False
        self.wifi_ip: str | None = None
        self.wifi_ssid: str | None = None
        self.wifi_pdns: str | None = None
        self.wifi_sdns: str | None = None
        self.wifi_gate: str | None = None
        self.wifi_sub: str | None = None
        self.environment: str | None = None
        self.schedule: Any | None = None

        # Track metadata cache
        self._track: dict | None = None
        self._track_task: asyncio.Task | None = None

    @property
    def brightness(self) -> int:
        """Return the brightness."""
        return 0 if self.is_sleeping else self._brightness

    @brightness.setter
    def brightness(self, value: int) -> None:
        self._brightness = value
        if value:
            self.brightness_on = value

    @property
    def is_sleeping(self) -> bool:
        """Return `True` if the status is set to sleeping."""
        return self.status_code == STATUS_CODE_SLEEPING

    def attach_client(self, client: OasisClientProtocol) -> None:
        """Attach a transport client (MQTT, HTTP, etc.) to this device."""
        self._client = client

    @property
    def client(self) -> OasisClientProtocol | None:
        """Return the current transport client, if any."""
        return self._client

    def _require_client(self) -> OasisClientProtocol:
        """Return the attached client or raise if missing."""
        if self._client is None:
            raise RuntimeError(
                f"No client/transport attached for device {self.serial_number!r}"
            )
        return self._client

    def _update_field(self, name: str, value: Any) -> bool:
        old = getattr(self, name, None)
        if old != value:
            _LOGGER.debug(
                "%s %s changed: '%s' -> '%s'",
                self.serial_number,
                name.replace("_", " ").capitalize(),
                old,
                value,
            )
            setattr(self, name, value)
            return True
        return False

    def update_from_status_dict(self, data: dict[str, Any]) -> None:
        """Update device fields from a status payload (from any transport)."""
        changed = False
        playlist_or_index_changed = False

        for key, value in data.items():
            if hasattr(self, key):
                if self._update_field(key, value):
                    changed = True
                    if key in ("playlist", "playlist_index"):
                        playlist_or_index_changed = True
            else:
                _LOGGER.warning("Unknown field: %s=%s", key, value)

        if playlist_or_index_changed:
            self.schedule_track_refresh()

        if changed:
            self._notify_listeners()

    def parse_status_string(self, raw_status: str) -> dict[str, Any] | None:
        """Parse a semicolon-separated status string into a state dict.

        Used by:
        - HTTP GETSTATUS response
        - MQTT FULLSTATUS payload (includes software_version)
        """
        if not raw_status:
            return None

        values = raw_status.split(";")

        # We rely on indices 0..17 existing (18 fields)
        if (n := len(values)) < 18:
            _LOGGER.warning(
                "Unexpected status format for %s: %s", self.serial_number, values
            )
            return None

        playlist = [_parse_int(track) for track in values[3].split(",") if track]

        try:
            status: dict[str, Any] = {
                "status_code": _parse_int(values[0]),
                "error": _parse_int(values[1]),
                "ball_speed": _parse_int(values[2]),
                "playlist": playlist,
                "playlist_index": min(_parse_int(values[4]), len(playlist)),
                "progress": _parse_int(values[5]),
                "led_effect": values[6],
                "led_color_id": values[7],
                "led_speed": _parse_int(values[8]),
                "brightness": _parse_int(values[9]),
                "color": values[10] if "#" in values[10] else None,
                "busy": _bit_to_bool(values[11]),
                "download_progress": _parse_int(values[12]),
                "brightness_max": _parse_int(values[13]),
                "wifi_connected": _bit_to_bool(values[14]),
                "repeat_playlist": _bit_to_bool(values[15]),
                "autoplay": _parse_int(values[16]),
                "auto_clean": _bit_to_bool(values[17]),
            }

            # Optional trailing field(s)
            if n > 18:
                status["software_version"] = values[18]

        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Error parsing status string for %s: %r", self.serial_number, raw_status
            )
            return None

        return status

    def update_from_status_string(self, raw_status: str) -> None:
        """Parse and apply a raw status string."""
        if status := self.parse_status_string(raw_status):
            self.update_from_status_dict(status)

    def as_dict(self) -> dict[str, Any]:
        """Return core state as a dict."""
        return {field: getattr(self, field) for field in _STATE_FIELDS}

    @property
    def error_message(self) -> str | None:
        """Return the error message, if any."""
        if self.status_code == 9:
            return ERROR_CODE_MAP.get(self.error, f"Unknown ({self.error})")
        return None

    @property
    def status(self) -> str:
        """Return human-readable status from status_code."""
        return STATUS_CODE_MAP.get(self.status_code, f"Unknown ({self.status_code})")

    @property
    def track(self) -> dict | None:
        """Return cached track info if it matches the current `track_id`."""
        if (track := self._track) and track["id"] == self.track_id:
            return track
        return TRACKS.get(self.track_id)

    @property
    def track_id(self) -> int | None:
        if not self.playlist:
            return None
        i = self.playlist_index
        return self.playlist[0] if i >= len(self.playlist) else self.playlist[i]

    @property
    def track_image_url(self) -> str | None:
        """Return the track image url, if any."""
        if (track := self.track) and (image := track.get("image")):
            return f"https://app.grounded.so/uploads/{image}"
        return None

    @property
    def track_name(self) -> str | None:
        """Return the track name, if any."""
        if track := self.track:
            return track.get("name", f"Unknown Title (#{self.track_id})")
        return None

    @property
    def drawing_progress(self) -> float | None:
        """Return drawing progress percentage for the current track."""
        if not (self.track and (svg_content := self.track.get("svg_content"))):
            return None
        svg_content = decrypt_svg_content(svg_content)
        paths = svg_content.split("L")
        total = self.track.get("reduced_svg_content_new", 0) or len(paths)
        percent = (100 * self.progress) / total
        return min(percent, 100)

    @property
    def playlist_details(self) -> dict[int, dict[str, str]]:
        """Basic playlist details using built-in TRACKS metadata."""
        return {
            track_id: {self.track_id: self.track or {}, **TRACKS}.get(
                track_id,
                {"name": f"Unknown Title (#{track_id})"},
            )
            for track_id in self.playlist
        }

    def create_svg(self) -> str | None:
        """Create the current svg based on track and progress."""
        return create_svg(self.track, self.progress)

    def add_update_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a callback for state changes.

        Returns an unsubscribe function.
        """
        self._listeners.append(listener)

        def _unsub() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return _unsub

    def _notify_listeners(self) -> None:
        """Call all registered listeners."""
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in update listener")

    async def async_get_mac_address(self) -> str | None:
        """Return the device MAC address, refreshing via transport if needed."""
        if self.mac_address:
            return self.mac_address

        client = self._require_client()
        mac = await client.async_get_mac_address(self)
        if mac:
            self._update_field("mac_address", mac)
        return mac

    async def async_set_auto_clean(self, auto_clean: bool) -> None:
        client = self._require_client()
        await client.async_send_auto_clean_command(self, auto_clean)

    async def async_set_ball_speed(self, speed: int) -> None:
        if not BALL_SPEED_MIN <= speed <= BALL_SPEED_MAX:
            raise ValueError("Invalid speed specified")
        client = self._require_client()
        await client.async_send_ball_speed_command(self, speed)

    async def async_set_led(
        self,
        *,
        led_effect: str | None = None,
        color: str | None = None,
        led_speed: int | None = None,
        brightness: int | None = None,
    ) -> None:
        """Set the Oasis device LED (shared validation & attribute updates)."""
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
        if not 0 <= brightness <= self.brightness_max:
            raise ValueError("Invalid brightness specified")

        client = self._require_client()
        await client.async_send_led_command(
            self, led_effect, color, led_speed, brightness
        )

    async def async_sleep(self) -> None:
        client = self._require_client()
        await client.async_send_sleep_command(self)

    async def async_move_track(self, from_index: int, to_index: int) -> None:
        client = self._require_client()
        await client.async_send_move_job_command(self, from_index, to_index)

    async def async_change_track(self, index: int) -> None:
        client = self._require_client()
        await client.async_send_change_track_command(self, index)

    async def async_add_track_to_playlist(self, track: int | Iterable[int]) -> None:
        if isinstance(track, int):
            tracks = [track]
        else:
            tracks = list(track)
        client = self._require_client()
        await client.async_send_add_joblist_command(self, tracks)

    async def async_set_playlist(self, playlist: int | Iterable[int]) -> None:
        if isinstance(playlist, int):
            playlist_list = [playlist]
        else:
            playlist_list = list(playlist)
        client = self._require_client()
        await client.async_send_set_playlist_command(self, playlist_list)

    async def async_set_repeat_playlist(self, repeat: bool) -> None:
        client = self._require_client()
        await client.async_send_set_repeat_playlist_command(self, repeat)

    async def async_set_autoplay(self, option: bool | int | str) -> None:
        """Set autoplay / wait-after behavior."""
        if isinstance(option, bool):
            option = 0 if option else 1
        client = self._require_client()
        await client.async_send_set_autoplay_command(self, str(option))

    async def async_upgrade(self, beta: bool = False) -> None:
        client = self._require_client()
        await client.async_send_upgrade_command(self, beta)

    async def async_play(self) -> None:
        client = self._require_client()
        await client.async_send_play_command(self)

    async def async_pause(self) -> None:
        client = self._require_client()
        await client.async_send_pause_command(self)

    async def async_stop(self) -> None:
        client = self._require_client()
        await client.async_send_stop_command(self)

    async def async_reboot(self) -> None:
        client = self._require_client()
        await client.async_send_reboot_command(self)

    def schedule_track_refresh(self) -> None:
        """Schedule an async refresh of current track info if track_id changed."""
        if not self._cloud:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            _LOGGER.debug("No running loop; cannot schedule track refresh")
            return

        if self._track_task and not self._track_task.done():
            self._track_task.cancel()

        self._track_task = loop.create_task(self._async_refresh_current_track())

    async def _async_refresh_current_track(self) -> None:
        """Refresh the current track info."""
        if not self._cloud:
            return

        if (track_id := self.track_id) is None:
            self._track = None
            return

        if self._track and self._track.get("id") == track_id:
            return

        try:
            track = await self._cloud.async_get_track_info(track_id)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Error fetching track info for %s", track_id)
            return

        if not track:
            return

        self._track = track
        self._notify_listeners()

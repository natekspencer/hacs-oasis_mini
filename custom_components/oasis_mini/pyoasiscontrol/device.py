"""Oasis device."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Final, Iterable

from .const import ERROR_CODE_MAP, LED_EFFECTS, STATUS_CODE_MAP, TRACKS

if TYPE_CHECKING:  # avoid runtime circular imports
    from .clients.transport import OasisClientProtocol

_LOGGER = logging.getLogger(__name__)

BALL_SPEED_MAX: Final = 400
BALL_SPEED_MIN: Final = 100
LED_SPEED_MAX: Final = 90
LED_SPEED_MIN: Final = -90

_STATE_FIELDS = (
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
    "max_brightness",
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
        ssid: str | None = None,
        ip_address: str | None = None,
        client: OasisClientProtocol | None = None,
    ) -> None:
        # Transport
        self._client: OasisClientProtocol | None = client
        self._listeners: list[Callable[[], None]] = []

        # Details
        self.model: str | None = model
        self.serial_number: str | None = serial_number
        self.ssid: str | None = ssid
        self.ip_address: str | None = ip_address

        # Status
        self.auto_clean: bool = False
        self.autoplay: str = "off"
        self.ball_speed: int = BALL_SPEED_MIN
        self.brightness: int = 0
        self.busy: bool = False
        self.color: str | None = None
        self.download_progress: int = 0
        self.error: int = 0
        self.led_effect: str = "0"
        self.led_speed: int = 0
        self.mac_address: str | None = None
        self.max_brightness: int = 200
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

        # Track metadata cache (used if you hydrate from cloud)
        self._track: dict | None = None

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
                "%s changed: '%s' -> '%s'",
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
        for key, value in data.items():
            if hasattr(self, key):
                if self._update_field(key, value):
                    changed = True
            else:
                _LOGGER.warning("Unknown field: %s=%s", key, value)

        if changed:
            self._notify_listeners()

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
    def track_id(self) -> int | None:
        if not self.playlist:
            return None
        i = self.playlist_index
        return self.playlist[0] if i >= len(self.playlist) else self.playlist[i]

    @property
    def track(self) -> dict | None:
        """Return cached track info if it matches the current `track_id`."""
        if self._track and self._track.get("id") == self.track_id:
            return self._track
        if track := TRACKS.get(self.track_id):
            self._track = track
            return self._track
        return None

    @property
    def drawing_progress(self) -> float | None:
        """Return drawing progress percentage for the current track."""
        # if not (self.track and (svg_content := self.track.get("svg_content"))):
        #     return None
        # svg_content = decrypt_svg_content(svg_content)
        # paths = svg_content.split("L")
        total = self.track.get("reduced_svg_content_new", 0)  # or len(paths)
        percent = (100 * self.progress) / total
        return percent

    @property
    def playlist_details(self) -> dict[int, dict[str, str]]:
        """Basic playlist details using built-in TRACKS metadata."""
        return {
            track_id: TRACKS.get(
                track_id,
                {"name": f"Unknown Title (#{track_id})"},
            )
            for track_id in self.playlist
        }

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
        """Set the Oasis Mini LED (shared validation & attribute updates)."""
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

"""Oasis MQTT client (multi-device)."""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime
import logging
import ssl
from typing import Any, Final

import aiomqtt

from ..device import OasisDevice
from ..utils import _bit_to_bool, _parse_int
from .transport import OasisClientProtocol

_LOGGER = logging.getLogger(__name__)

# mqtt connection parameters
HOST: Final = "mqtt.grounded.so"
PORT: Final = 8084
PATH: Final = "mqtt"
USERNAME: Final = "YXBw"
PASSWORD: Final = "RWdETFlKMDczfi4t"
RECONNECT_INTERVAL: Final = 4

# Command queue behaviour
MAX_PENDING_COMMANDS: Final = 10


class OasisMqttClient(OasisClientProtocol):
    """MQTT-based Oasis transport using WSS.

    Responsibilities:
    - Maintain a single MQTT connection to:
        wss://mqtt.grounded.so:8084/mqtt
    - Subscribe only to <serial>/STATUS/# for devices it knows about.
    - Publish commands to <serial>/COMMAND/CMD
    - Map MQTT payloads to OasisDevice.update_from_status_dict()
    """

    def __init__(self) -> None:
        # MQTT connection state
        self._client: aiomqtt.Client | None = None
        self._loop_task: asyncio.Task | None = None
        self._connected_at: datetime | None = None

        self._connected_event: asyncio.Event = asyncio.Event()
        self._stop_event: asyncio.Event = asyncio.Event()

        # Known devices by serial
        self._devices: dict[str, OasisDevice] = {}

        # Per-device events
        self._first_status_events: dict[str, asyncio.Event] = {}
        self._mac_events: dict[str, asyncio.Event] = {}

        # Subscription bookkeeping
        self._subscribed_serials: set[str] = set()
        self._subscription_lock = asyncio.Lock()

        # Pending command queue: (serial, payload)
        self._command_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(
            maxsize=MAX_PENDING_COMMANDS
        )

    def register_device(self, device: OasisDevice) -> None:
        """Register a device so MQTT messages can be routed to it."""
        if not device.serial_number:
            raise ValueError("Device must have serial_number set before registration")

        serial = device.serial_number
        self._devices[serial] = device

        # Ensure we have per-device events
        self._first_status_events.setdefault(serial, asyncio.Event())
        self._mac_events.setdefault(serial, asyncio.Event())

        # Attach ourselves as the client if the device doesn't already have one
        if not device.client:
            device.attach_client(self)

        # If we're already connected, subscribe to this device's topics
        if self._client is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._subscribe_serial(serial))
            except RuntimeError:
                # No running loop (unlikely in HA), so just log
                _LOGGER.debug(
                    "Could not schedule subscription for %s (no running loop)", serial
                )

    def unregister_device(self, device: OasisDevice) -> None:
        serial = device.serial_number
        if not serial:
            return

        self._devices.pop(serial, None)
        self._first_status_events.pop(serial, None)
        self._mac_events.pop(serial, None)

        # If connected and we were subscribed, unsubscribe
        if self._client is not None and serial in self._subscribed_serials:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._unsubscribe_serial(serial))
            except RuntimeError:
                _LOGGER.debug(
                    "Could not schedule unsubscription for %s (no running loop)",
                    serial,
                )

    async def _subscribe_serial(self, serial: str) -> None:
        """Subscribe to STATUS topics for a single device."""
        if not self._client:
            return

        async with self._subscription_lock:
            if not self._client or serial in self._subscribed_serials:
                return

            topic = f"{serial}/STATUS/#"
            await self._client.subscribe([(topic, 1)])
            self._subscribed_serials.add(serial)
            _LOGGER.info("Subscribed to %s", topic)

    async def _unsubscribe_serial(self, serial: str) -> None:
        """Unsubscribe from STATUS topics for a single device."""
        if not self._client:
            return

        async with self._subscription_lock:
            if not self._client or serial not in self._subscribed_serials:
                return

            topic = f"{serial}/STATUS/#"
            await self._client.unsubscribe(topic)
            self._subscribed_serials.discard(serial)
            _LOGGER.info("Unsubscribed from %s", topic)

    async def _resubscribe_all(self) -> None:
        """Resubscribe to all known devices after (re)connect."""
        self._subscribed_serials.clear()
        for serial in list(self._devices):
            await self._subscribe_serial(serial)

    def start(self) -> None:
        """Start MQTT connection loop."""
        if self._loop_task is None or self._loop_task.done():
            self._stop_event.clear()
            loop = asyncio.get_running_loop()
            self._loop_task = loop.create_task(self._mqtt_loop())

    async def async_close(self) -> None:
        """Close connection loop and MQTT client."""
        await self.stop()

    async def stop(self) -> None:
        """Stop MQTT connection loop."""
        self._stop_event.set()

        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                _LOGGER.exception("Error disconnecting MQTT client")
            finally:
                self._client = None

        # Drop pending commands on stop
        while not self._command_queue.empty():
            try:
                self._command_queue.get_nowait()
                self._command_queue.task_done()
            except asyncio.QueueEmpty:
                break

    async def wait_until_ready(
        self, device: OasisDevice, timeout: float = 10.0, request_status: bool = True
    ) -> bool:
        """
        Wait until:
        1. MQTT client is connected
        2. Device sends at least one STATUS message

        If request_status=True, a request status command is sent *after* connection.
        """
        serial = device.serial_number
        if not serial:
            raise RuntimeError("Device has no serial_number set")

        first_status_event = self._first_status_events.setdefault(
            serial, asyncio.Event()
        )

        # Wait for MQTT connection
        try:
            await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            _LOGGER.debug(
                "Timeout (%.1fs) waiting for MQTT connection (device %s)",
                timeout,
                serial,
            )
            return False

        # Optionally request a status refresh
        if request_status:
            try:
                first_status_event.clear()
                await self.async_get_status(device)
            except Exception:
                _LOGGER.debug(
                    "Could not request status for %s (not fully connected yet?)",
                    serial,
                )

        # Wait for first status
        try:
            await asyncio.wait_for(first_status_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            _LOGGER.debug(
                "Timeout (%.1fs) waiting for first STATUS message from %s",
                timeout,
                serial,
            )
            return False

    async def async_get_mac_address(self, device: OasisDevice) -> str | None:
        """For MQTT, GETSTATUS causes MAC_ADDRESS to be published."""
        # If already known on the device, return it
        if device.mac_address:
            return device.mac_address

        serial = device.serial_number
        if not serial:
            raise RuntimeError("Device has no serial_number set")

        mac_event = self._mac_events.setdefault(serial, asyncio.Event())
        mac_event.clear()

        # Ask device to refresh status (including MAC_ADDRESS)
        await self.async_get_status(device)

        try:
            await asyncio.wait_for(mac_event.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            _LOGGER.debug("Timed out waiting for MAC_ADDRESS for %s", serial)

        return device.mac_address

    async def async_send_ball_speed_command(
        self,
        device: OasisDevice,
        speed: int,
    ) -> None:
        payload = f"WRIOASISSPEED={speed}"
        await self._publish_command(device, payload)

    async def async_send_led_command(
        self,
        device: OasisDevice,
        led_effect: str,
        color: str,
        led_speed: int,
        brightness: int,
    ) -> None:
        payload = f"WRILED={led_effect};0;{color};{led_speed};{brightness}"
        await self._publish_command(device, payload, bool(brightness))

    async def async_send_sleep_command(self, device: OasisDevice) -> None:
        await self._publish_command(device, "CMDSLEEP")

    async def async_send_move_job_command(
        self,
        device: OasisDevice,
        from_index: int,
        to_index: int,
    ) -> None:
        payload = f"MOVEJOB={from_index};{to_index}"
        await self._publish_command(device, payload)

    async def async_send_change_track_command(
        self,
        device: OasisDevice,
        index: int,
    ) -> None:
        payload = f"CMDCHANGETRACK={index}"
        await self._publish_command(device, payload)

    async def async_send_add_joblist_command(
        self,
        device: OasisDevice,
        tracks: list[int],
    ) -> None:
        track_str = ",".join(map(str, tracks))
        payload = f"ADDJOBLIST={track_str}"
        await self._publish_command(device, payload)

    async def async_send_set_playlist_command(
        self,
        device: OasisDevice,
        playlist: list[int],
    ) -> None:
        track_str = ",".join(map(str, playlist))
        payload = f"WRIJOBLIST={track_str}"
        await self._publish_command(device, payload)

        # local state optimistic update
        device.update_from_status_dict({"playlist": playlist})

    async def async_send_set_repeat_playlist_command(
        self,
        device: OasisDevice,
        repeat: bool,
    ) -> None:
        payload = f"WRIREPEATJOB={1 if repeat else 0}"
        await self._publish_command(device, payload)

    async def async_send_set_autoplay_command(
        self,
        device: OasisDevice,
        option: str,
    ) -> None:
        payload = f"WRIWAITAFTER={option}"
        await self._publish_command(device, payload)

    async def async_send_upgrade_command(
        self,
        device: OasisDevice,
        beta: bool,
    ) -> None:
        payload = f"CMDUPGRADE={1 if beta else 0}"
        await self._publish_command(device, payload)

    async def async_send_play_command(self, device: OasisDevice) -> None:
        await self._publish_command(device, "CMDPLAY", True)

    async def async_send_pause_command(self, device: OasisDevice) -> None:
        await self._publish_command(device, "CMDPAUSE")

    async def async_send_stop_command(self, device: OasisDevice) -> None:
        await self._publish_command(device, "CMDSTOP")

    async def async_send_reboot_command(self, device: OasisDevice) -> None:
        await self._publish_command(device, "CMDBOOT")

    async def async_get_all(self, device: OasisDevice) -> None:
        """Request FULLSTATUS + SCHEDULE (compact snapshot)."""
        await self._publish_command(device, "GETALL")

    async def async_get_status(self, device: OasisDevice) -> None:
        """Ask device to publish STATUS topics."""
        await self._publish_command(device, "GETSTATUS")

    async def _enqueue_command(self, serial: str, payload: str) -> None:
        """Queue a command to be sent when connected.

        If the queue is full, drop the oldest command to make room.
        """
        if self._command_queue.full():
            try:
                dropped = self._command_queue.get_nowait()
                self._command_queue.task_done()
                _LOGGER.debug(
                    "Command queue full, dropping oldest command: %s", dropped
                )
            except asyncio.QueueEmpty:
                # race: became empty between full() and get_nowait()
                pass

        await self._command_queue.put((serial, payload))
        _LOGGER.debug("Queued command for %s: %s", serial, payload)

    async def _flush_pending_commands(self) -> None:
        """Send any queued commands now that we're connected."""
        if not self._client:
            return

        while not self._command_queue.empty():
            try:
                serial, payload = self._command_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            try:
                # Skip commands for unknown devices
                if serial not in self._devices:
                    _LOGGER.debug(
                        "Skipping queued command for unknown device %s: %s",
                        serial,
                        payload,
                    )
                    self._command_queue.task_done()
                    continue

                topic = f"{serial}/COMMAND/CMD"
                _LOGGER.debug("Flushing queued MQTT command %s => %s", topic, payload)
                await self._client.publish(topic, payload.encode(), qos=1)
            except Exception:
                _LOGGER.debug(
                    "Failed to flush queued command for %s, re-queuing", serial
                )
                # Put it back and break; we'll try again on next reconnect
                await self._enqueue_command(serial, payload)
                self._command_queue.task_done()
                break

            self._command_queue.task_done()

    async def _publish_command(
        self, device: OasisDevice, payload: str, wake: bool = False
    ) -> None:
        serial = device.serial_number
        if not serial:
            raise RuntimeError("Device has no serial number set")

        if wake and device.is_sleeping:
            await self.async_get_all(device)

        # If not connected, just queue the command
        if not self._client or not self._connected_event.is_set():
            _LOGGER.debug(
                "MQTT not connected, queueing command for %s: %s", serial, payload
            )
            await self._enqueue_command(serial, payload)
            return

        topic = f"{serial}/COMMAND/CMD"
        try:
            _LOGGER.debug("MQTT publish %s => %s", topic, payload)
            await self._client.publish(topic, payload.encode(), qos=1)
        except Exception:
            _LOGGER.debug(
                "MQTT publish failed, queueing command for %s: %s", serial, payload
            )
            await self._enqueue_command(serial, payload)

    async def _mqtt_loop(self) -> None:
        loop = asyncio.get_running_loop()
        tls_context = await loop.run_in_executor(None, ssl.create_default_context)

        while not self._stop_event.is_set():
            try:
                _LOGGER.info("Connecting MQTT WSS to wss://%s:%s/%s", HOST, PORT, PATH)

                async with aiomqtt.Client(
                    hostname=HOST,
                    port=PORT,
                    transport="websockets",
                    tls_context=tls_context,
                    username=base64.b64decode(USERNAME).decode(),
                    password=base64.b64decode(PASSWORD).decode(),
                    keepalive=30,
                    websocket_path=f"/{PATH}",
                ) as client:
                    self._client = client
                    self._connected_event.set()
                    self._connected_at = datetime.now(UTC)
                    _LOGGER.info("Connected to MQTT broker")

                    # Subscribe only to STATUS topics for known devices
                    await self._resubscribe_all()

                    # Flush any queued commands now that we're connected
                    await self._flush_pending_commands()

                    async for msg in client.messages:
                        if self._stop_event.is_set():
                            break
                        await self._handle_status_message(msg)

            except asyncio.CancelledError:
                break
            except Exception:
                _LOGGER.info("MQTT connection error")

            finally:
                if self._connected_event.is_set():
                    self._connected_event.clear()
                    if self._connected_at:
                        _LOGGER.info(
                            "MQTT was connected for %s",
                            datetime.now(UTC) - self._connected_at,
                        )
                    self._connected_at = None
                self._client = None
                self._subscribed_serials.clear()

            if not self._stop_event.is_set():
                _LOGGER.info(
                    "Disconnected from broker, retrying in %.1fs", RECONNECT_INTERVAL
                )
                await asyncio.sleep(RECONNECT_INTERVAL)

    async def _handle_status_message(self, msg: aiomqtt.Message) -> None:
        """Map MQTT STATUS topics → OasisDevice.update_from_status_dict payloads."""
        topic_str = str(msg.topic) if msg.topic is not None else ""
        payload = msg.payload.decode(errors="replace")

        parts = topic_str.split("/")
        # Expect: "<serial>/STATUS/<STATUS_NAME>"
        if len(parts) < 3:
            return

        serial, _, status_name = parts[:3]

        device = self._devices.get(serial)
        if not device:
            _LOGGER.debug("Received MQTT for unknown device %s: %s", serial, topic_str)
            return

        data: dict[str, Any] = {}

        try:
            if status_name == "OASIS_STATUS":
                data["status_code"] = int(payload)
            elif status_name == "OASIS_ERROR":
                data["error"] = int(payload)
            elif status_name == "OASIS_SPEEED":
                data["ball_speed"] = int(payload)
            elif status_name == "JOBLIST":
                data["playlist"] = [int(x) for x in payload.split(",") if x]
            elif status_name == "CURRENTJOB":
                data["playlist_index"] = int(payload)
            elif status_name == "CURRENTLINE":
                data["progress"] = int(payload)
            elif status_name == "LED_EFFECT":
                data["led_effect"] = payload
            elif status_name == "LED_EFFECT_COLOR":
                data["led_color_id"] = payload
            elif status_name == "LED_SPEED":
                data["led_speed"] = int(payload)
            elif status_name == "LED_BRIGHTNESS":
                data["brightness"] = int(payload)
            elif status_name == "LED_MAX":
                data["brightness_max"] = int(payload)
            elif status_name == "LED_EFFECT_PARAM":
                data["color"] = payload if payload.startswith("#") else None
            elif status_name == "SYSTEM_BUSY":
                data["busy"] = payload in ("1", "true", "True")
            elif status_name == "DOWNLOAD_PROGRESS":
                data["download_progress"] = int(payload)
            elif status_name == "REPEAT_JOB":
                data["repeat_playlist"] = payload in ("1", "true", "True")
            elif status_name == "WAIT_AFTER_JOB":
                data["autoplay"] = _parse_int(payload)
            elif status_name == "AUTO_CLEAN":
                data["auto_clean"] = payload in ("1", "true", "True")
            elif status_name == "SOFTWARE_VER":
                data["software_version"] = payload
            elif status_name == "MAC_ADDRESS":
                data["mac_address"] = payload
                mac_event = self._mac_events.setdefault(serial, asyncio.Event())
                mac_event.set()
            elif status_name == "WIFI_SSID":
                data["wifi_ssid"] = payload
            elif status_name == "WIFI_IP":
                data["wifi_ip"] = payload
            elif status_name == "WIFI_PDNS":
                data["wifi_pdns"] = payload
            elif status_name == "WIFI_SDNS":
                data["wifi_sdns"] = payload
            elif status_name == "WIFI_GATE":
                data["wifi_gate"] = payload
            elif status_name == "WIFI_SUB":
                data["wifi_sub"] = payload
            elif status_name == "WIFI_STATUS":
                data["wifi_connected"] = _bit_to_bool(payload)
            elif status_name == "SCHEDULE":
                data["schedule"] = payload
            elif status_name == "ENVIRONMENT":
                data["environment"] = payload
            elif status_name == "FULLSTATUS":
                if parsed := device.parse_status_string(payload):
                    data = parsed
            else:
                _LOGGER.warning(
                    "Unknown status received for %s: %s=%s",
                    serial,
                    status_name,
                    payload,
                )
        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Error parsing MQTT payload for %s %s: %r", serial, status_name, payload
            )
            return

        if data:
            device.update_from_status_dict(data)

        first_status_event = self._first_status_events.setdefault(
            serial, asyncio.Event()
        )
        if not first_status_event.is_set():
            first_status_event.set()

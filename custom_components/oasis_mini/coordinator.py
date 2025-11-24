"""Oasis devices coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .pyoasiscontrol import OasisCloudClient, OasisDevice, OasisMqttClient

_LOGGER = logging.getLogger(__name__)


class OasisDeviceCoordinator(DataUpdateCoordinator[list[OasisDevice]]):
    """Oasis device data update coordinator."""

    attempt: int = 0
    last_updated: datetime | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        cloud_client: OasisCloudClient,
        mqtt_client: OasisMqttClient,
    ) -> None:
        """
        Create an OasisDeviceCoordinator that manages OasisDevice discovery and updates using cloud and MQTT clients.

        Parameters:
            cloud_client (OasisCloudClient): Client for communicating with the Oasis cloud API and fetching device data.
            mqtt_client (OasisMqttClient): Client for registering devices and coordinating MQTT-based readiness/status.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=10),
            always_update=False,
        )
        self.cloud_client = cloud_client
        self.mqtt_client = mqtt_client

    async def _async_update_data(self) -> list[OasisDevice]:
        """
        Fetch and assemble the current list of OasisDevice objects, reconcile removed devices in Home Assistant, register discovered devices with MQTT, and verify per-device readiness.

        Returns:
            A list of OasisDevice instances representing devices currently available for the account.

        Raises:
            UpdateFailed: If no devices can be read after repeated attempts or an unexpected error persists past retry limits.
        """
        devices: list[OasisDevice] = []
        self.attempt += 1

        try:
            async with async_timeout.timeout(30):
                raw_devices = await self.cloud_client.async_get_devices()

                existing_by_serial = {
                    d.serial_number: d for d in (self.data or []) if d.serial_number
                }

                for raw in raw_devices:
                    if not (serial := raw.get("serial_number")):
                        continue

                    if device := existing_by_serial.get(serial):
                        if name := raw.get("name"):
                            device.name = name
                    else:
                        device = OasisDevice(
                            model=(raw.get("model") or {}).get("name"),
                            serial_number=serial,
                            name=raw.get("name"),
                            cloud=self.cloud_client,
                        )

                    devices.append(device)

                new_serials = {d.serial_number for d in devices if d.serial_number}
                removed_serials = set(existing_by_serial) - new_serials

                if removed_serials:
                    device_registry = dr.async_get(self.hass)
                    for serial in removed_serials:
                        _LOGGER.info(
                            "Oasis device %s removed from account; cleaning up in HA",
                            serial,
                        )
                        device_entry = device_registry.async_get_device(
                            identifiers={(DOMAIN, serial)}
                        )
                        if device_entry:
                            device_registry.async_update_device(
                                device_id=device_entry.id,
                                remove_config_entry_id=self.config_entry.entry_id,
                            )

                # ✅ Valid state: logged in but no devices on account
                if not devices:
                    _LOGGER.debug("No Oasis devices found for account")
                    self.attempt = 0
                    if devices != self.data:
                        self.last_updated = dt_util.now()
                    return []

                self.mqtt_client.register_devices(devices)

                # Best-effort playlists
                try:
                    await self.cloud_client.async_get_playlists()
                except Exception:
                    _LOGGER.exception("Error fetching playlists from cloud")

                any_success = False

                for device in devices:
                    try:
                        ready = await self.mqtt_client.wait_until_ready(
                            device, request_status=True
                        )
                        if not ready:
                            _LOGGER.warning(
                                "Timeout waiting for Oasis device %s to be ready",
                                device.serial_number,
                            )
                            continue

                        mac = await device.async_get_mac_address()
                        if not mac:
                            _LOGGER.warning(
                                "Could not get MAC address for Oasis device %s",
                                device.serial_number,
                            )
                            continue

                        any_success = True
                        device.schedule_track_refresh()

                    except Exception:
                        _LOGGER.exception(
                            "Error preparing Oasis device %s", device.serial_number
                        )

                if any_success:
                    self.attempt = 0
                else:
                    if self.attempt > 2 or not self.data:
                        raise UpdateFailed(
                            "Couldn't read from any Oasis device "
                            f"after {self.attempt} attempts"
                        )

        except UpdateFailed:
            raise
        except Exception as ex:  # noqa: BLE001
            if self.attempt > 2 or not (devices or self.data):
                raise UpdateFailed(
                    "Unexpected error talking to Oasis devices "
                    f"after {self.attempt} attempts"
                ) from ex
            _LOGGER.warning(
                "Error updating Oasis devices; reusing previous data", exc_info=ex
            )
            return self.data or devices

        if devices != self.data:
            self.last_updated = dt_util.now()

        return devices

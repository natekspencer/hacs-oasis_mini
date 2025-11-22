"""Oasis devices coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
        """Initialize."""
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
        """Update the data."""
        devices: list[OasisDevice] = []
        self.attempt += 1

        try:
            async with async_timeout.timeout(10):
                if not self.data:
                    raw_devices = await self.cloud_client.async_get_devices()
                    devices = [
                        OasisDevice(
                            model=raw_device.get("model", {}).get("name"),
                            serial_number=raw_device.get("serial_number"),
                        )
                        for raw_device in raw_devices
                    ]
                else:
                    devices = self.data
                for device in devices:
                    self.mqtt_client.register_device(device)
                    await self.mqtt_client.wait_until_ready(device, request_status=True)
                    if not device.mac_address:
                        await device.async_get_mac_address()
                    # if not device.software_version:
                    #     await device.async_get_software_version()
                # data = await self.device.async_get_status()
                # devices = self.cloud_client.mac_address
                self.attempt = 0
                # await self.device.async_get_current_track_details()
                # await self.device.async_get_playlist_details()
                # await self.device.async_cloud_get_playlists()
        except Exception as ex:  # pylint:disable=broad-except
            if self.attempt > 2 or not (devices or self.data):
                raise UpdateFailed(
                    f"Couldn't read from the Oasis device after {self.attempt} attempts"
                ) from ex

        if devices != self.data:
            self.last_updated = datetime.now()
        return devices

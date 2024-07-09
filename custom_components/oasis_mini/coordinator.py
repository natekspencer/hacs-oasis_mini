"""Oasis Mini coordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .pyoasismini import OasisMini

_LOGGER = logging.getLogger(__name__)


class OasisMiniCoordinator(DataUpdateCoordinator[str]):
    """Oasis Mini data update coordinator."""

    last_updated: datetime | None = None

    def __init__(self, hass: HomeAssistant, device: OasisMini) -> None:
        """Initialize."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=10)
        )
        self.device = device

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                if not self.device.serial_number:
                    await self.device.async_get_serial_number()
                if not self.device.software_version:
                    await self.device.async_get_software_version()
                data = await self.device.async_get_status()
                await self.device.async_get_current_track_details()
        except Exception as ex:
            raise UpdateFailed("Couldn't read from the Oasis Mini") from ex
        if data is None:
            raise ConfigEntryAuthFailed
        if data != self.data:
            self.last_updated = datetime.now()
        return data

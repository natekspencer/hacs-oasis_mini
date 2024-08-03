"""Oasis Mini update entity."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .entity import OasisMiniEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=6)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Oasis Mini updates using config entry."""
    coordinator: OasisMiniCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.device.access_token:
        async_add_entities(
            [OasisMiniUpdateEntity(coordinator, entry, DESCRIPTOR)], True
        )


DESCRIPTOR = UpdateEntityDescription(
    key="software", device_class=UpdateDeviceClass.FIRMWARE
)


class OasisMiniUpdateEntity(OasisMiniEntity, UpdateEntity):
    """Oasis Mini update entity."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    @property
    def in_progress(self) -> bool | int:
        """Update installation progress."""
        if self.device.status_code == 11:
            return self.device.download_progress
        return False

    @property
    def installed_version(self) -> str:
        """Version installed and in use."""
        return self.device.software_version

    @property
    def should_poll(self) -> bool:
        """Set polling to True."""
        return True

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        version = await self.device.async_get_software_version()
        if version == self.latest_version:
            return
        await self.device.async_upgrade()

    async def async_update(self) -> None:
        """Update the entity."""
        await self.device.async_get_software_version()
        software = await self.device.async_cloud_get_latest_software_details()
        if not software:
            _LOGGER.warning("Unable to get latest software details")
            return
        self._attr_latest_version = software["version"]
        self._attr_release_summary = software["description"]
        self._attr_release_url = f"https://app.grounded.so/software/{software['id']}"

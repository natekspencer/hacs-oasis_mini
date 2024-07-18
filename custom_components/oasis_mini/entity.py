"""Oasis Mini entity."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .pyoasismini import OasisMini

_LOGGER = logging.getLogger(__name__)


class OasisMiniEntity(CoordinatorEntity[OasisMiniCoordinator]):
    """Base class for Oasis Mini entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OasisMiniCoordinator,
        entry: ConfigEntry,
        description: EntityDescription,
    ) -> None:
        """Construct an Oasis Mini entity."""
        super().__init__(coordinator)
        self.entity_description = description
        device = coordinator.device
        serial_number = device.serial_number
        self._attr_unique_id = f"{serial_number}-{description.key}"

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, format_mac(device.mac_address))},
            identifiers={(DOMAIN, serial_number)},
            name=entry.title,
            manufacturer="Kinetic Oasis",
            model="Oasis Mini",
            serial_number=serial_number,
            sw_version=device.software_version,
        )

    @property
    def device(self) -> OasisMini:
        """Return the device."""
        return self.coordinator.device

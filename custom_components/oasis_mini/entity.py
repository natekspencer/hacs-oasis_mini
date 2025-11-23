"""Oasis device entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OasisDeviceCoordinator
from .pyoasiscontrol import OasisDevice


class OasisDeviceEntity(CoordinatorEntity[OasisDeviceCoordinator]):
    """Base class for Oasis device entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OasisDeviceCoordinator,
        device: OasisDevice,
        description: EntityDescription,
    ) -> None:
        """Construct an Oasis device entity."""
        super().__init__(coordinator)
        self.device = device
        self.entity_description = description

        serial_number = device.serial_number
        self._attr_unique_id = f"{serial_number}-{description.key}"

        connections = set()
        if mac_address := device.mac_address:
            connections.add((CONNECTION_NETWORK_MAC, format_mac(mac_address)))

        self._attr_device_info = DeviceInfo(
            connections=connections,
            identifiers={(DOMAIN, serial_number)},
            name=f"{device.model} {serial_number}",
            manufacturer=device.manufacturer,
            model=device.model,
            serial_number=serial_number,
            sw_version=device.software_version,
        )

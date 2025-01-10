"""Support for Oasis Mini."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
import homeassistant.helpers.device_registry as dr

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .helpers import create_client

type OasisMiniConfigEntry = ConfigEntry[OasisMiniCoordinator]

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    # Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: OasisMiniConfigEntry) -> bool:
    """Set up Oasis Mini from a config entry."""
    client = create_client(entry.data | entry.options)
    coordinator = OasisMiniCoordinator(hass, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as ex:
        _LOGGER.exception(ex)

    if not entry.unique_id:
        if not (serial_number := coordinator.device.serial_number):
            dev_reg = dr.async_get(hass)
            devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
            serial_number = next(
                (
                    identifier[1]
                    for identifier in devices[0].identifiers
                    if identifier[0] == DOMAIN
                ),
                None,
            )
        hass.config_entries.async_update_entry(entry, unique_id=serial_number)

    if not coordinator.data:
        await client.session.close()
        raise ConfigEntryNotReady

    if entry.unique_id != coordinator.device.serial_number:
        await client.session.close()
        raise ConfigEntryError("Serial number mismatch")

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OasisMiniConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.device.session.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: OasisMiniConfigEntry) -> None:
    """Handle removal of an entry."""
    if entry.options:
        client = create_client(entry.data | entry.options)
        await client.async_cloud_logout()
        await client.session.close()


async def update_listener(hass: HomeAssistant, entry: OasisMiniConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

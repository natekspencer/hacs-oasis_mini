"""Support for Oasis Mini."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er

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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s", entry.version, entry.minor_version
    )

    if entry.version == 1 and entry.minor_version == 1:
        # Need to update previous playlist select entity to queue
        @callback
        def migrate_unique_id(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
            """Migrate the playlist unique ID to queue."""
            if entity_entry.domain == "select" and entity_entry.unique_id.endswith(
                "-playlist"
            ):
                unique_id = entity_entry.unique_id.replace("-playlist", "-queue")
                return {"new_unique_id": unique_id}
            return None

        await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)
        hass.config_entries.async_update_entry(entry, minor_version=2, version=1)

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True

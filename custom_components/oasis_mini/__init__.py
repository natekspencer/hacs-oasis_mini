"""Support for Oasis devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
import homeassistant.helpers.entity_registry as er

from .coordinator import OasisDeviceCoordinator
from .helpers import create_client
from .pyoasiscontrol import OasisMqttClient, UnauthenticatedError

type OasisDeviceConfigEntry = ConfigEntry[OasisDeviceCoordinator]

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
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: OasisDeviceConfigEntry) -> bool:
    """Set up Oasis devices from a config entry."""
    cloud_client = create_client(hass, entry.data)
    try:
        user = await cloud_client.async_get_user()
    except UnauthenticatedError as err:
        raise ConfigEntryAuthFailed(err) from err

    mqtt_client = OasisMqttClient()
    mqtt_client.start()

    coordinator = OasisDeviceCoordinator(hass, cloud_client, mqtt_client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as ex:
        _LOGGER.exception(ex)

    if entry.unique_id != (user_id := str(user["id"])):
        hass.config_entries.async_update_entry(entry, unique_id=user_id)

    if not coordinator.data:
        _LOGGER.warning("No devices associated with account")

    entry.runtime_data = coordinator

    def _on_oasis_update() -> None:
        coordinator.async_update_listeners()

    for device in coordinator.data:
        device.add_update_listener(_on_oasis_update)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OasisDeviceConfigEntry
) -> bool:
    """Unload a config entry."""
    mqtt_client = entry.runtime_data.mqtt_client
    await mqtt_client.async_close()

    cloud_client = entry.runtime_data.cloud_client
    await cloud_client.async_close()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: OasisDeviceConfigEntry
) -> None:
    """Handle removal of an entry."""
    cloud_client = create_client(hass, entry.data)
    try:
        await cloud_client.async_logout()
    except Exception as ex:
        _LOGGER.exception(ex)
    await cloud_client.async_close()


async def async_migrate_entry(hass: HomeAssistant, entry: OasisDeviceConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s", entry.version, entry.minor_version
    )

    if entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 1:
        new_data = {**entry.data}
        new_options = {**entry.options}

        if entry.minor_version < 2:
            # Need to update previous playlist select entity to queue
            @callback
            def migrate_unique_id(
                entity_entry: er.RegistryEntry,
            ) -> dict[str, Any] | None:
                """Migrate the playlist unique ID to queue."""
                if entity_entry.domain == "select" and entity_entry.unique_id.endswith(
                    "-playlist"
                ):
                    unique_id = entity_entry.unique_id.replace("-playlist", "-queue")
                    return {"new_unique_id": unique_id}
                return None

            await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)

        if entry.minor_version < 3:
            # Auth is now required, host is dropped
            new_data = {**entry.options}
            new_options = {}

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options=new_options,
            minor_version=3,
            title=new_data.get(CONF_EMAIL, "Oasis Control"),
            unique_id=None,
            version=1,
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True

"""Support for Oasis devices."""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import OasisDeviceCoordinator
from .entity import OasisDeviceEntity
from .helpers import create_client
from .pyoasiscontrol import OasisDevice, OasisMqttClient, UnauthenticatedError

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
    Platform.SWITCH,
    Platform.UPDATE,
]


def setup_platform_from_coordinator(
    entry: OasisDeviceConfigEntry,
    async_add_entities: AddEntitiesCallback,
    make_entities: Callable[[OasisDevice], Iterable[OasisDeviceEntity]],
    update_before_add: bool = False,
) -> None:
    """Generic pattern: add entities per device, including newly discovered ones."""
    coordinator = entry.runtime_data

    known_serials: set[str] = set()

    @callback
    def _check_devices() -> None:
        devices = coordinator.data or []
        new_devices: list[OasisDevice] = []

        for device in devices:
            serial = device.serial_number
            if not serial or serial in known_serials:
                continue

            known_serials.add(serial)
            new_devices.append(device)

        if not new_devices:
            return

        if entities := make_entities(new_devices):
            async_add_entities(entities, update_before_add)

    # Initial population
    _check_devices()
    # Future updates (new devices discovered)
    entry.async_on_unload(coordinator.async_add_listener(_check_devices))


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
        coordinator.last_updated = dt_util.now()
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


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: OasisDeviceConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    current_serials = {d.serial_number for d in (config_entry.runtime_data.data or [])}
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN and identifier[1] in current_serials
    )

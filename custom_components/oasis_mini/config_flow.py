"""Config flow for Oasis Mini integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientConnectorError
from httpx import ConnectError, HTTPStatusError
import voluptuous as vol

from homeassistant.components import dhcp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from . import OasisMiniConfigEntry
from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .helpers import create_client

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})
OPTIONS_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


async def cloud_login(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Cloud login."""
    coordinator: OasisMiniCoordinator = handler.parent_handler.config_entry.runtime_data

    try:
        await coordinator.device.async_cloud_login(
            email=user_input[CONF_EMAIL], password=user_input[CONF_PASSWORD]
        )
        user_input[CONF_ACCESS_TOKEN] = coordinator.device.access_token
    except Exception as ex:
        raise SchemaFlowError("invalid_auth") from ex

    del user_input[CONF_PASSWORD]
    return user_input


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA, validate_user_input=cloud_login)
}


class OasisMiniConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Oasis Mini."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: OasisMiniConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        host = {CONF_HOST: discovery_info.ip}
        await self.validate_client(host)
        self._abort_if_unique_id_configured(updates=host)
        # This should never happen since we only listen to DHCP requests
        # for configured devices.
        return self.async_abort(reason="already_configured")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self._async_step(
            "user", STEP_USER_DATA_SCHEMA, user_input, user_input
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry

        suggested_values = user_input or entry.data
        return await self._async_step(
            "reconfigure", STEP_USER_DATA_SCHEMA, user_input, suggested_values
        )

    async def _async_step(
        self,
        step_id: str,
        schema: vol.Schema,
        user_input: dict[str, Any] | None = None,
        suggested_values: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle step setup."""
        errors = {}

        if user_input is not None:
            if not (errors := await self.validate_client(user_input)):
                if step_id != "reconfigure":
                    self._abort_if_unique_id_configured(updates=user_input)
                if existing_entry := self.hass.config_entries.async_get_entry(
                    self.context.get("entry_id")
                ):
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=user_input
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                    return self.async_abort(reason="reconfigure_successful")

                return self.async_create_entry(
                    title=f"Oasis Mini {self.unique_id}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(schema, suggested_values),
            errors=errors,
        )

    async def validate_client(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate client setup."""
        errors = {}
        try:
            async with asyncio.timeout(10):
                client = create_client(user_input)
                await self.async_set_unique_id(await client.async_get_serial_number())
            if not self.unique_id:
                errors["base"] = "invalid_host"
        except asyncio.TimeoutError:
            errors["base"] = "timeout_connect"
        except ConnectError:
            errors["base"] = "invalid_host"
        except ClientConnectorError:
            errors["base"] = "invalid_host"
        except HTTPStatusError as err:
            errors["base"] = str(err)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error(ex)
            errors["base"] = "unknown"
        finally:
            await client.session.close()
        return errors

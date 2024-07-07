"""Config flow for Oasis Mini integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientConnectorError
from httpx import ConnectError, HTTPStatusError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import DOMAIN
from .coordinator import OasisMiniCoordinator
from .helpers import create_client

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})
OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EMAIL): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


async def cloud_login(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    coordinator: OasisMiniCoordinator = handler.parent_handler.hass.data[DOMAIN][
        handler.parent_handler.config_entry.entry_id
    ]

    try:
        await coordinator.device.async_cloud_login(
            email=user_input[CONF_EMAIL], password=user_input[CONF_PASSWORD]
        )
        user_input[CONF_ACCESS_TOKEN] = coordinator.device.access_token
    except:
        raise SchemaFlowError("invalid_auth")

    del user_input[CONF_PASSWORD]
    return user_input


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA, validate_user_input=cloud_login)
}


class OasisMiniConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Oasis Mini."""

    VERSION = 1

    host: str | None = None
    serial_number: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    # async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
    #     """Handle dhcp discovery."""
    #     self.host = discovery_info.ip
    #     self.name = discovery_info.hostname
    #     await self.async_set_unique_id(discovery_info.macaddress)
    #     self._abort_if_unique_id_configured(updates={CONF_HOST: self.host})
    #     return await self.async_step_api_key()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self._async_step("user", STEP_USER_DATA_SCHEMA, user_input)

    async def _async_step(
        self, step_id: str, schema: vol.Schema, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle step setup."""
        if abort := self._abort_if_configured(user_input):
            return abort

        errors = {}

        if user_input is not None:
            if not (errors := await self.validate_client(user_input)):
                data = {CONF_HOST: user_input.get(CONF_HOST, self.host)}
                if existing_entry := self.hass.config_entries.async_get_entry(
                    self.context.get("entry_id")
                ):
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=data
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(
                    title=f"Oasis Mini {self.serial_number}",
                    data=data,
                )

        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    async def validate_client(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate client setup."""
        errors = {}
        try:
            client = create_client({"host": self.host} | user_input)
            self.serial_number = await client.async_get_serial_number()
            if not self.serial_number:
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

    @callback
    def _abort_if_configured(
        self, user_input: dict[str, Any] | None
    ) -> FlowResult | None:
        """Abort if configured."""
        if self.host or user_input:
            data = {CONF_HOST: self.host, **(user_input or {})}
            for entry in self._async_current_entries():
                if entry.data[CONF_HOST] == data[CONF_HOST]:
                    return self.async_abort(reason="already_configured")
        return None

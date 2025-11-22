"""Config flow for Oasis device integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from aiohttp import ClientConnectorError
from httpx import ConnectError, HTTPStatusError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN
from .helpers import create_client
from .pyoasiscontrol import UnauthenticatedError

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


class OasisDeviceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Oasis devices."""

    VERSION = 1
    MINOR_VERSION = 3

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry

        suggested_values = user_input or entry.data
        return await self._async_step(
            "reauth_confirm", STEP_USER_DATA_SCHEMA, user_input, suggested_values
        )

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
                entry_id = self.context.get("entry_id")
                existing_entry = self.hass.config_entries.async_get_entry(entry_id)
                if existing_entry and existing_entry.unique_id:
                    self._abort_if_unique_id_mismatch(reason="wrong_account")
                if existing_entry:
                    return self.async_update_reload_and_abort(
                        existing_entry,
                        unique_id=self.unique_id,
                        title=user_input[CONF_EMAIL],
                        data=user_input,
                        reload_even_if_entry_is_unchanged=False,
                    )

                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
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
                client = create_client(self.hass, user_input)
                await client.async_login(
                    email=user_input[CONF_EMAIL], password=user_input[CONF_PASSWORD]
                )
                user_input[CONF_ACCESS_TOKEN] = client.access_token
                user = await client.async_get_user()
                await self.async_set_unique_id(str(user["id"]))
                del user_input[CONF_PASSWORD]
            if not self.unique_id:
                errors["base"] = "invalid_auth"
        except UnauthenticatedError:
            errors["base"] = "invalid_auth"
        except asyncio.TimeoutError:
            errors["base"] = "timeout_connect"
        except ConnectError:
            errors["base"] = "invalid_auth"
        except ClientConnectorError:
            errors["base"] = "invalid_auth"
        except HTTPStatusError as err:
            errors["base"] = str(err)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error(ex)
            errors["base"] = "unknown"
        finally:
            await client.async_close()
        return errors

"""Config flow for ETA Touch."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from etatouch_restful import EtaTouchClient, EtaTouchConnectionError, EtaTouchResponseError
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_VARIABLES, DEFAULT_NAME, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN
from .helpers import parse_variable_lines

_LOGGER = logging.getLogger(__name__)


class EtaTouchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an ETA Touch config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            try:
                parse_variable_lines(user_input.get(CONF_VARIABLES, ""))
                await self._validate_connection(user_input)
            except ValueError:
                errors[CONF_VARIABLES] = "invalid_variables"
            except EtaTouchConnectionError:
                errors["base"] = "cannot_connect"
            except EtaTouchResponseError:
                errors["base"] = "invalid_response"
            except Exception:
                _LOGGER.exception("Unexpected error while connecting to ETA Touch")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                    vol.Optional(CONF_VARIABLES, default=""): str,
                }
            ),
            errors=errors,
        )

    async def _validate_connection(self, user_input: dict[str, Any]) -> None:
        session = async_get_clientsession(self.hass)
        client = EtaTouchClient(
            user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            session=session,
        )
        await client.get_api_version()


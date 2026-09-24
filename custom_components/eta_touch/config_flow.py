"""Config flow for ETA Touch."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from etatouch_restful import EtaTouchClient, EtaTouchConnectionError, EtaTouchResponseError
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AUTO_DISCOVERY,
    CONF_MAX_DISCOVERED_VARIABLES,
    CONF_VARIABLES,
    DEFAULT_AUTO_DISCOVERY,
    DEFAULT_MAX_DISCOVERED_VARIABLES,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .helpers import parse_variable_lines

_LOGGER = logging.getLogger(__name__)


class EtaTouchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an ETA Touch config flow."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = dict(user_input)
            user_input[CONF_HOST] = user_input[CONF_HOST].strip().lower().rstrip(".")
            user_input.setdefault(CONF_PORT, DEFAULT_PORT)
            if self._endpoint_configured(user_input):
                return self.async_abort(reason="already_configured")
            try:
                parse_variable_lines(user_input.get(CONF_VARIABLES, ""))
            except ValueError:
                errors[CONF_VARIABLES] = "invalid_variables"
            else:
                if error := await self._connection_error(user_input):
                    errors["base"] = error
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
                    vol.Required(CONF_HOST): vol.All(str, vol.Strip, vol.Length(min=1)),
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                        vol.Coerce(int), vol.Range(min=10, max=3600)
                    ),
                    vol.Optional(CONF_AUTO_DISCOVERY, default=DEFAULT_AUTO_DISCOVERY): bool,
                    vol.Optional(
                        CONF_MAX_DISCOVERED_VARIABLES,
                        default=DEFAULT_MAX_DISCOVERED_VARIABLES,
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=200)),
                    vol.Optional(CONF_VARIABLES, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Change the endpoint of the existing controller without replacing its entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        defaults = {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_PORT: entry.data.get(CONF_PORT, DEFAULT_PORT),
        }
        if user_input is not None:
            endpoint = {
                CONF_HOST: user_input[CONF_HOST].strip().lower().rstrip("."),
                CONF_PORT: user_input.get(CONF_PORT, defaults[CONF_PORT]),
            }
            defaults.update(endpoint)
            if self._endpoint_configured(endpoint, ignore_entry_id=entry.entry_id):
                errors["base"] = "already_configured"
            elif error := await self._connection_error(endpoint):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates=endpoint)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=defaults[CONF_HOST]): vol.All(
                        str, vol.Strip, vol.Length(min=1)
                    ),
                    vol.Required(CONF_PORT, default=defaults[CONF_PORT]): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                }
            ),
            errors=errors,
        )

    def _endpoint_configured(
        self, endpoint: dict[str, Any], *, ignore_entry_id: str | None = None
    ) -> bool:
        """Prevent duplicate endpoints, excluding the entry being reconfigured."""
        for entry in self._async_current_entries():
            if entry.entry_id == ignore_entry_id:
                continue
            if (
                entry.data[CONF_HOST].strip().lower().rstrip(".") == endpoint[CONF_HOST]
                and entry.data.get(CONF_PORT, DEFAULT_PORT) == endpoint[CONF_PORT]
            ):
                return True
        return False

    async def _connection_error(self, endpoint: dict[str, Any]) -> str | None:
        """Validate an endpoint using the same errors in setup and reconfiguration."""
        try:
            await self._validate_connection(endpoint)
        except EtaTouchConnectionError:
            return "cannot_connect"
        except EtaTouchResponseError:
            return "invalid_response"
        except Exception:
            _LOGGER.exception("Unexpected error while connecting to ETA Touch")
            return "unknown"
        return None

    async def _validate_connection(self, user_input: dict[str, Any]) -> None:
        session = async_get_clientsession(self.hass)
        client = EtaTouchClient(
            user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            session=session,
        )
        await client.get_api_version()

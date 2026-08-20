"""Instellen van de WattWanneer-integratie via de UI."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InvalidAuth, RateLimited, WattWanneerClient, WattWanneerError
from .const import CONF_API_KEY, DOMAIN

SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class WattWanneerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Vraagt om de API-key en controleert die meteen."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            # Eén installatie per key; voorkomt dubbele sensoren.
            await self.async_set_unique_id(key[-8:])
            self._abort_if_unique_id_configured()

            client = WattWanneerClient(async_get_clientsession(self.hass), key)
            try:
                await client.async_validate()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except RateLimited:
                errors["base"] = "rate_limited"
            except WattWanneerError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="WattWanneer", data={CONF_API_KEY: key}
                )

        return self.async_show_form(
            step_id="user", data_schema=SCHEMA, errors=errors
        )

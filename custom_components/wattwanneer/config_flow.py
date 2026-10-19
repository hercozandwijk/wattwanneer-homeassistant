"""Instellen van de WattWanneer-integratie via de UI."""

from __future__ import annotations

from collections.abc import Mapping
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

    async def _controleer(self, key: str) -> str | None:
        """Geeft de foutcode terug, of None als de key werkt."""
        client = WattWanneerClient(async_get_clientsession(self.hass), key)
        try:
            await client.async_validate()
        except InvalidAuth:
            return "invalid_auth"
        except RateLimited:
            return "rate_limited"
        except WattWanneerError:
            return "cannot_connect"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            # Eén installatie per key; voorkomt dubbele sensoren.
            await self.async_set_unique_id(key[-8:])
            self._abort_if_unique_id_configured()

            if fout := await self._controleer(key):
                errors["base"] = fout
            else:
                return self.async_create_entry(
                    title="WattWanneer", data={CONF_API_KEY: key}
                )

        return self.async_show_form(
            step_id="user", data_schema=SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start als de API de opgeslagen key weigert (ConfigEntryAuthFailed)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Vraagt om een nieuwe key, bijvoorbeeld na een nieuw abonnement."""
        errors: dict[str, str] = {}

        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            if fout := await self._controleer(key):
                errors["base"] = fout
            else:
                # De unique_id blijft gelijk: het is dezelfde installatie met
                # een nieuwe key, en zo blijven sensoren en historie behouden.
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: key}
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=SCHEMA, errors=errors
        )

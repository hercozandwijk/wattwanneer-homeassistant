"""Instellen van de WattWanneer-integratie via de UI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import InvalidAuth, RateLimited, WattWanneerClient, WattWanneerError
from .const import CONF_API_KEY, CONF_ZONE, DOMAIN, ZONE_NL, ZONES

SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})
# Hassfest eist kleine letters in vertaalsleutels, dus de keuzelijst gebruikt
# nl en be. Opgeslagen wordt NL of BE, zoals de API het verwacht.
SCHEMA_USER = SCHEMA.extend(
    {
        vol.Required(CONF_ZONE, default=ZONE_NL.lower()): SelectSelector(
            SelectSelectorConfig(
                options=[z.lower() for z in ZONES],
                translation_key=CONF_ZONE,
                mode=SelectSelectorMode.LIST,
            )
        )
    }
)
TITELS = {"NL": "WattWanneer", "BE": "WattWanneer België"}


class WattWanneerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Vraagt om de API-key en controleert die meteen."""

    VERSION = 1

    async def _controleer(self, key: str, zone: str = ZONE_NL) -> str | None:
        """Geeft de foutcode terug, of None als de key werkt."""
        client = WattWanneerClient(async_get_clientsession(self.hass), key, zone)
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
            zone = user_input.get(CONF_ZONE, ZONE_NL).upper()
            # Eén installatie per key en land; voorkomt dubbele sensoren. Voor
            # Nederland is dit dezelfde unique_id als voor 0.3.0.
            uid = key[-8:] if zone == ZONE_NL else f"{key[-8:]}_{zone.lower()}"
            await self.async_set_unique_id(uid)
            self._abort_if_unique_id_configured()

            if fout := await self._controleer(key, zone):
                errors["base"] = fout
            else:
                return self.async_create_entry(
                    title=TITELS[zone], data={CONF_API_KEY: key, CONF_ZONE: zone}
                )

        return self.async_show_form(
            step_id="user", data_schema=SCHEMA_USER, errors=errors
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
            zone = self._get_reauth_entry().data.get(CONF_ZONE, ZONE_NL)
            if fout := await self._controleer(key, zone):
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

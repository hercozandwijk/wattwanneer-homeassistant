"""Tests voor de configuratiedialoog."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.wattwanneer.const import API_BASE, DOMAIN


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_formulier_wordt_getoond(hass: HomeAssistant):
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_geldige_key_maakt_entry(hass: HomeAssistant, aioclient_mock, summary_payload):
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "ww_geldigetestkey1234567890ab"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WattWanneer"
    assert result["data"]["api_key"] == "ww_geldigetestkey1234567890ab"


@pytest.mark.parametrize(
    ("status", "fout"),
    [(401, "invalid_auth"), (429, "rate_limited"), (500, "cannot_connect")],
)
async def test_foutmeldingen(hass: HomeAssistant, aioclient_mock, status, fout):
    """De gebruiker moet zien wat er mis is, niet alleen dat het misging."""
    aioclient_mock.get(f"{API_BASE}/summary", status=status)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "ww_watdanook1234567890abcdef"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": fout}


async def test_dezelfde_key_niet_twee_keer(
    hass: HomeAssistant, aioclient_mock, summary_payload
):
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    key = "ww_dubbeletestkey1234567890ab"
    eerste = await _start(hass)
    await hass.config_entries.flow.async_configure(eerste["flow_id"], {"api_key": key})

    tweede = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        tweede["flow_id"], {"api_key": key}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

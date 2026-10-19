"""Tests voor een geweigerde API-key en het invullen van een nieuwe.

Weigert de API de opgeslagen key (verlopen of opnieuw afgesloten abonnement), dan
hoort Home Assistant de gebruiker om een nieuwe key te vragen, en niet elk uur
opnieuw te proberen met een key die toch geweigerd wordt.
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wattwanneer.const import API_BASE, DOMAIN, TODAY_URL

OUDE_KEY = "ww_oudetestkey1234567890abcdef"
NIEUWE_KEY = "ww_nieuwetestkey1234567890abcd"


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, data={"api_key": OUDE_KEY}, title="WattWanneer", unique_id=OUDE_KEY[-8:]
    )
    entry.add_to_hass(hass)
    return entry


def _reauth_flows(hass: HomeAssistant) -> list:
    return [
        f for f in hass.config_entries.flow.async_progress()
        if f["handler"] == DOMAIN and f["context"]["source"] == SOURCE_REAUTH
    ]


async def test_geweigerde_key_bij_opstarten_vraagt_om_nieuwe(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168", status=401)
    entry = _entry(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert len(_reauth_flows(hass)) == 1


async def test_geweigerde_key_later_vraagt_om_nieuwe(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    """Eerst werkt de key, bij een volgende update niet meer."""
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168", json=forecast_payload)
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    aioclient_mock.get(TODAY_URL, json=today_payload)
    entry = _entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert _reauth_flows(hass) == []

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168", status=401)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert len(_reauth_flows(hass)) == 1


async def test_nieuwe_key_wordt_opgeslagen(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168", json=forecast_payload)
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    aioclient_mock.get(TODAY_URL, json=today_payload)
    entry = _entry(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": f"  {NIEUWE_KEY} "}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["api_key"] == NIEUWE_KEY
    assert entry.unique_id == OUDE_KEY[-8:], "zelfde installatie, dus sensoren blijven bestaan"


async def test_ook_de_nieuwe_key_geweigerd(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(f"{API_BASE}/summary", status=401)
    entry = _entry(hass)
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": NIEUWE_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["api_key"] == OUDE_KEY


def test_tijdzone_niet_in_de_event_loop_aangemaakt():
    """ZoneInfo leest van schijf. Alleen const.py mag hem aanmaken, bij het importeren."""
    map_ = Path(__file__).resolve().parent.parent / "custom_components" / DOMAIN
    for bestand in map_.glob("*.py"):
        if bestand.name == "const.py":
            continue
        assert "ZoneInfo(" not in bestand.read_text(), f"ZoneInfo(...) in {bestand.name}"

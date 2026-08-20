"""Tests voor de sensoren en de afgeleide berekeningen."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wattwanneer.const import API_BASE, DOMAIN, TODAY_URL


async def _setup(hass, aioclient_mock, forecast_payload, summary_payload, today_payload):
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168", json=forecast_payload)
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    aioclient_mock.get(TODAY_URL, json=today_payload)
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": "ww_test"}, title="WattWanneer")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_alle_sensoren_verschijnen(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    await _setup(hass, aioclient_mock, forecast_payload, summary_payload, today_payload)
    ids = [e for e in hass.states.async_entity_ids("sensor") if "wattwanneer" in e]
    assert len(ids) == 7


async def test_goedkoopste_venster_leest_summary(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    """Het venster komt uit /v1/summary en houdt de attributen mee."""
    await _setup(hass, aioclient_mock, forecast_payload, summary_payload, today_payload)
    state = hass.states.get("sensor.wattwanneer_cheapest_window")
    assert state is not None
    assert state.attributes["window_hours"] == 3
    assert state.attributes["average_price"] == 0.0746
    # end_exclusive is het echte einde; daarop moet een automation schakelen
    assert state.attributes["end"] == "2026-08-20T13:00:00Z"


async def test_weekgemiddelde_over_alle_punten(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    await _setup(hass, aioclient_mock, forecast_payload, summary_payload, today_payload)
    state = hass.states.get("sensor.wattwanneer_average_this_week")
    # (0.10 + 0.20) / 2
    assert float(state.state) == 0.15
    assert state.attributes["hours"] == 2
    assert state.attributes["cheapest_price"] == 0.10


async def test_api_fout_maakt_sensoren_onbeschikbaar(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    """Bij een storing moeten sensoren unavailable worden, niet stilletjes
    een oude waarde blijven tonen waar automations op schakelen."""
    entry = await _setup(
        hass, aioclient_mock, forecast_payload, summary_payload, today_payload
    )
    coordinator = hass.data[DOMAIN][entry.entry_id]

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168", status=500)
    aioclient_mock.get(f"{API_BASE}/summary", status=500)
    aioclient_mock.get(TODAY_URL, status=500)

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    state = hass.states.get("sensor.wattwanneer_current_price")
    assert state.state == "unavailable"

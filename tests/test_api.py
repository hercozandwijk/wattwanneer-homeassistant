"""Tests voor de API-client, met name de foutafhandeling."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.wattwanneer.api import (
    InvalidAuth,
    RateLimited,
    WattWanneerClient,
    WattWanneerError,
)
from custom_components.wattwanneer.const import API_BASE, TODAY_URL


def _client(hass: HomeAssistant) -> WattWanneerClient:
    return WattWanneerClient(async_get_clientsession(hass), "ww_test")


async def test_validate_ok(hass: HomeAssistant, aioclient_mock, summary_payload):
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    await _client(hass).async_validate()


@pytest.mark.parametrize(
    ("status", "verwacht"),
    [(401, InvalidAuth), (429, RateLimited), (500, WattWanneerError)],
)
async def test_foutstatussen(hass: HomeAssistant, aioclient_mock, status, verwacht):
    """Elke HTTP-fout moet een eigen, herkenbare uitzondering geven."""
    aioclient_mock.get(f"{API_BASE}/summary", status=status)
    with pytest.raises(verwacht):
        await _client(hass).async_validate()


async def test_fetch_combineert_bronnen(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    """De client haalt forecast, summary en today op en normaliseert ze."""
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168", json=forecast_payload)
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    aioclient_mock.get(TODAY_URL, json=today_payload)

    data = await _client(hass).async_fetch()

    assert len(data["points"]) == 2
    assert data["points"][0]["price"] == 0.10
    assert data["points"][0]["source"] == "entsoe_day_ahead"
    # timestamps moeten aware zijn, anders gaat rekenen met tijdzones mis
    assert data["points"][0]["timestamp"].tzinfo is not None
    assert len(data["today"]) == 3
    assert data["generated_at"] == "2026-08-19T11:20:00Z"


async def test_today_negeert_incomplete_rijen(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload
):
    """Een rij zonder prijs mag de hele ophaalronde niet laten klappen."""
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168", json=forecast_payload)
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    aioclient_mock.get(
        TODAY_URL,
        json=[
            {"datetime": "2026-08-20 12:00", "price_eur_kwh": 0.1357},
            {"datetime": "2026-08-20 13:00"},
            {"price_eur_kwh": 0.2},
        ],
    )
    data = await _client(hass).async_fetch()
    assert len(data["today"]) == 1

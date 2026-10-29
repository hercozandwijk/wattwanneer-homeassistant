"""Tests voor de landkeuze: Nederland of België.

Sinds 0.3.0 kun je bij het instellen België kiezen. De integratie vraagt de API
dan met ?zone=BE en leest today_prices_be.json. Een bestaande installatie (zonder
zone in de config) moet precies blijven doen wat hij deed.
"""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wattwanneer.api import WattWanneerClient
from custom_components.wattwanneer.const import API_BASE, DOMAIN, TODAY_URL, TODAY_URL_BE

KEY = "ww_zonetestkey1234567890abcdef"


def _mock_be(aioclient_mock, forecast_payload, summary_payload, today_payload):
    """Alleen URL's met zone=BE: een verzoek zonder zone vindt dan geen antwoord."""
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168&zone=BE", json=dict(forecast_payload, zone="BE"))
    aioclient_mock.get(f"{API_BASE}/summary?zone=BE", json=dict(summary_payload, zone="BE"))
    aioclient_mock.get(TODAY_URL_BE, json=today_payload)


def _urls(aioclient_mock) -> list[str]:
    return [str(call[1]) for call in aioclient_mock.mock_calls]


async def test_nederland_vraagt_precies_wat_het_altijd_vroeg(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168", json=forecast_payload)
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    aioclient_mock.get(TODAY_URL, json=today_payload)
    await WattWanneerClient(async_get_clientsession(hass), KEY).async_fetch()
    assert _urls(aioclient_mock) == [f"{API_BASE}/forecast?hours=168", f"{API_BASE}/summary", TODAY_URL]


async def test_belgie_vraagt_met_zone_en_leest_het_belgische_bestand(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    _mock_be(aioclient_mock, forecast_payload, summary_payload, today_payload)
    data = await WattWanneerClient(async_get_clientsession(hass), KEY, "BE").async_fetch()
    assert _urls(aioclient_mock) == [
        f"{API_BASE}/forecast?hours=168&zone=BE",
        f"{API_BASE}/summary?zone=BE",
        TODAY_URL_BE,
    ]
    assert len(data["points"]) == 2
    assert len(data["today"]) == 3


async def test_dialoog_belgie_maakt_een_belgische_entry(
    hass: HomeAssistant, aioclient_mock, summary_payload
):
    aioclient_mock.get(f"{API_BASE}/summary?zone=BE", json=summary_payload)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_key": KEY, "zone": "BE"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WattWanneer België"
    assert result["data"] == {"api_key": KEY, "zone": "BE"}
    assert _urls(aioclient_mock) == [f"{API_BASE}/summary?zone=BE"]


async def test_dialoog_zonder_keuze_is_nederland(hass: HomeAssistant, aioclient_mock, summary_payload):
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_key": KEY})
    assert result["title"] == "WattWanneer"
    assert result["data"] == {"api_key": KEY, "zone": "NL"}
    assert result["result"].unique_id == KEY[-8:]


async def test_zelfde_key_voor_beide_landen_mag(hass: HomeAssistant, aioclient_mock, summary_payload):
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    for zone in ("NL", "BE", "BE"):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_key": KEY, "zone": zone})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert sorted(e.data["zone"] for e in hass.config_entries.async_entries(DOMAIN)) == ["BE", "NL"]


async def test_belgische_installatie_haalt_belgische_prijzen(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    _mock_be(aioclient_mock, forecast_payload, summary_payload, today_payload)
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": KEY, "zone": "BE"}, title="WattWanneer België")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ids = [e for e in hass.states.async_entity_ids("sensor") if "wattwanneer" in e]
    assert len(ids) == 8
    assert all(e.startswith("sensor.wattwanneer_belgie_") for e in ids)
    apparaten = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert [a.name for a in apparaten] == ["WattWanneer België"]


async def test_bestaande_installatie_zonder_zone_blijft_nederland(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168", json=forecast_payload)
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    aioclient_mock.get(TODAY_URL, json=today_payload)
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": KEY}, title="WattWanneer")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert all("zone=" not in u and u != TODAY_URL_BE for u in _urls(aioclient_mock))
    assert hass.states.get("sensor.wattwanneer_current_price") is not None


async def test_nieuwe_key_houdt_het_land(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    _mock_be(aioclient_mock, forecast_payload, summary_payload, today_payload)
    entry = MockConfigEntry(
        domain=DOMAIN, data={"api_key": "ww_oud", "zone": "BE"}, title="WattWanneer België", unique_id="x_be"
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}, data=entry.data
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"api_key": KEY})
    await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert entry.data == {"api_key": KEY, "zone": "BE"}

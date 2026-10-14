"""Tests voor de sensor in Nordpool-formaat.

Pakketten zoals het lokale Zendure-pakket lezen ``raw_today`` uit een sensor en
zoeken daarin het uur waarin ``now()`` valt. Dat moet dus kloppen, ook rond de
wintertijd, en morgen mag pas gevuld zijn als de day-ahead-prijzen er zijn.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wattwanneer.const import API_BASE, DOMAIN, TODAY_URL

ENTITY = "sensor.wattwanneer_prices_nordpool_format"
NL = ZoneInfo("Europe/Amsterdam")


def _dag(datum: str, basis: float, uren: int = 24) -> list[dict]:
    begin = datetime.fromisoformat(f"{datum} 00:00")
    return [
        {"datetime": (begin + timedelta(hours=u)).strftime("%Y-%m-%d %H:00"), "price_eur_kwh": basis + u / 100}
        for u in range(uren)
    ]


async def _setup(hass, aioclient_mock, forecast_payload, summary_payload, today):
    aioclient_mock.get(f"{API_BASE}/forecast?hours=168", json=forecast_payload)
    aioclient_mock.get(f"{API_BASE}/summary", json=summary_payload)
    aioclient_mock.get(TODAY_URL, json=today)
    entry = MockConfigEntry(domain=DOMAIN, data={"api_key": "ww_test"}, title="WattWanneer")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_vandaag_en_morgen_in_nordpool_formaat(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, freezer
):
    freezer.move_to("2026-08-20T10:30:00+00:00")  # 12:30 in Nederland
    await _setup(hass, aioclient_mock, forecast_payload, summary_payload,
                 _dag("2026-08-20", 0.10) + _dag("2026-08-21", 0.20))
    state = hass.states.get(ENTITY)
    assert state is not None
    assert float(state.state) == 0.22  # het uur van 12:00
    a = state.attributes
    assert len(a["raw_today"]) == 24 and len(a["today"]) == 24
    uur = a["raw_today"][12]
    assert uur["value"] == 0.22
    assert uur["start"] == datetime(2026, 8, 20, 12, tzinfo=NL)
    assert uur["end"] == datetime(2026, 8, 20, 13, tzinfo=NL)
    # Zo rekent het Zendure-pakket ermee: dit moet zonder fouten werken.
    assert uur["start"].isoformat() == "2026-08-20T12:00:00+02:00"
    assert uur["start"].hour == 12
    assert a["tomorrow_valid"] is True
    assert a["raw_tomorrow"][0]["start"].isoformat() == "2026-08-21T00:00:00+02:00"
    assert a["current_price"] == 0.22
    assert a["min"] == 0.10 and a["max"] == 0.33
    assert a["currency"] == "EUR" and a["unit"] == "kWh" and a["price_in_cents"] is False


async def test_morgen_leeg_tot_de_prijzen_er_zijn(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, freezer
):
    """Een half gevulde morgen telt niet, zoals bij Nordpool."""
    freezer.move_to("2026-08-20T08:00:00+00:00")
    await _setup(hass, aioclient_mock, forecast_payload, summary_payload,
                 _dag("2026-08-20", 0.10) + _dag("2026-08-21", 0.20, uren=3))
    a = hass.states.get(ENTITY).attributes
    assert a["tomorrow_valid"] is False
    assert a["raw_tomorrow"] == [] and a["tomorrow"] == []


async def test_wintertijd_herhaald_uur_dekt_twee_echte_uren(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, freezer
):
    """WattWanneer geeft op 25 oktober 24 uur, met 02:00 als gemiddelde van beide.

    Dat uur moet dan lopen tot 03:00 wintertijd, anders vindt een pakket dat het
    huidige uur zoekt tussen 02:00 en 03:00 wintertijd geen prijs.
    """
    freezer.move_to("2026-10-25T01:30:00+00:00")  # tweede keer 02:30 in Nederland
    await _setup(hass, aioclient_mock, forecast_payload, summary_payload, _dag("2026-10-25", 0.10))
    state = hass.states.get(ENTITY)
    twee = state.attributes["raw_today"][2]
    assert twee["start"].isoformat() == "2026-10-25T02:00:00+02:00"
    assert twee["end"].isoformat() == "2026-10-25T03:00:00+01:00"
    assert state.attributes["raw_today"][3]["start"].isoformat() == "2026-10-25T03:00:00+01:00"
    nu = datetime(2026, 10, 25, 1, 30, tzinfo=ZoneInfo("UTC"))
    assert twee["start"] <= nu < twee["end"]
    assert float(state.state) == 0.12


async def test_grote_lijsten_gaan_niet_de_database_in(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, today_payload
):
    await _setup(hass, aioclient_mock, forecast_payload, summary_payload, today_payload)
    entiteit = next(
        e for e in hass.data["sensor"].entities if e.entity_id == ENTITY
    )
    assert {"raw_today", "raw_tomorrow", "today", "tomorrow"} <= entiteit._unrecorded_attributes


async def test_templates_zoals_pakketten_ze_gebruiken(
    hass: HomeAssistant, aioclient_mock, forecast_payload, summary_payload, freezer
):
    """De bewerkingen die het Zendure-pakket en andere Nordpool-templates doen,
    in de echte template-engine van Home Assistant."""
    from homeassistant.helpers.template import Template

    freezer.move_to("2026-08-20T10:30:00+00:00")
    await _setup(hass, aioclient_mock, forecast_payload, summary_payload,
                 _dag("2026-08-20", 0.10) + _dag("2026-08-21", 0.20))
    render = lambda t: Template(t, hass).async_render()  # noqa: E731

    # Uur zoeken door start direct met now() te vergelijken.
    uur = render(
        "{% set raw = state_attr('" + ENTITY + "', 'raw_today') %}"
        "{% set nu = now() %}"
        "{{ raw | selectattr('start', '>=', nu.replace(minute=0, second=0, microsecond=0))"
        " | selectattr('start', '<', nu.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))"
        " | map(attribute='value') | list | first }}"
    )
    assert float(uur) == 0.22
    # Kwartiermodus: via as_datetime en timestamps.
    kwartier = render(
        "{% set ts = as_timestamp(now()) %}"
        "{% for p in state_attr('" + ENTITY + "', 'raw_today') %}"
        "{% if as_timestamp(as_datetime(p.start)) <= ts < as_timestamp(as_datetime(p.end)) %}{{ p.value }}{% endif %}"
        "{% endfor %}"
    )
    assert float(kwartier) == 0.22
    # Groeperen per uur en terugschrijven als tekst.
    groepen = render(
        "{{ state_attr('" + ENTITY + "', 'raw_tomorrow') | groupby('start.hour') | list | count }}"
    )
    assert int(groepen) == 24
    tekst = render("{{ (state_attr('" + ENTITY + "', 'raw_today') | first).start.isoformat() }}")
    assert tekst == "2026-08-20T00:00:00+02:00"

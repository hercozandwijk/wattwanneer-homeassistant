"""Testopzet voor de WattWanneer-integratie."""

from __future__ import annotations

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Zorgt dat HA de custom_components-map meeneemt in elke test."""
    yield


@pytest.fixture
def forecast_payload() -> dict:
    return {
        "zone": "NL",
        "generated_at": "2026-08-19T11:20:00Z",
        "model_version": "hist_gradient_boosting",
        "horizon_hours": 3,
        "points": [
            {
                "timestamp": "2026-08-20T10:00:00Z",
                "price_eur_per_kwh": 0.10,
                "confidence_low": 0.09,
                "confidence_high": 0.11,
                "source": "entsoe_day_ahead",
            },
            {
                "timestamp": "2026-08-20T11:00:00Z",
                "price_eur_per_kwh": 0.20,
                "confidence_low": 0.19,
                "confidence_high": 0.21,
                "source": "model",
            },
        ],
    }


@pytest.fixture
def summary_payload() -> dict:
    return {
        "zone": "NL",
        "generated_at": "2026-08-19T11:20:00Z",
        "cheapest_window": {
            "window_hours": 3,
            "start": "2026-08-20T10:00:00Z",
            "end": "2026-08-20T12:00:00Z",
            "end_exclusive": "2026-08-20T13:00:00Z",
            "avg_price": 0.0746,
        },
        "average_price_next_24h": 0.1477,
        "average_price_next_7d": 0.1416,
        "expected_peak_price_next_7d": 0.35,
    }


@pytest.fixture
def today_payload() -> list[dict]:
    return [
        {"datetime": "2026-08-20 12:00", "price_eur_kwh": 0.1357},
        {"datetime": "2026-08-20 13:00", "price_eur_kwh": 0.0668},
        {"datetime": "2026-08-21 12:00", "price_eur_kwh": 0.1500},
    ]

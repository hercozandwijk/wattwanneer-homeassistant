"""Constanten voor de WattWanneer-integratie."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "wattwanneer"

CONF_API_KEY = "api_key"

# De betaalde API levert de 168-uurs voorspelling.
API_BASE = "https://wattwanneer.nl/api/v1"
# today_prices.json is publiek en dekt vandaag plus morgen. Dat hebben we apart
# nodig: zodra de dagelijkse run in de middag klaar is, begint /v1/forecast bij
# morgen 00:00 en zit het huidige uur er dus niet meer in.
TODAY_URL = "https://wattwanneer.nl/public/today_prices.json"

# De voorspelling ververst een keer per dag, in de middag. Een keer per uur
# ophalen is ruim voldoende en blijft ver onder de rate limit van 10 per minuut.
UPDATE_INTERVAL = timedelta(hours=1)

# Tijdzone waarin WattWanneer zijn lokale datums uitdrukt.
LOCAL_TZ = "Europe/Amsterdam"

ATTR_PRICES_TODAY = "prices_today"
ATTR_PRICES_TOMORROW = "prices_tomorrow"
ATTR_FORECAST = "forecast"
ATTR_GENERATED_AT = "generated_at"
ATTR_SOURCE = "source"

"""Constanten voor de WattWanneer-integratie."""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

DOMAIN = "wattwanneer"

CONF_API_KEY = "api_key"
CONF_ZONE = "zone"

# Biedzone. Sinds 0.3.0 ook België: de API neemt dan de Nederlandse
# voorspelling en legt daar de echte Belgische day-ahead prijzen overheen.
# Een installatie zonder zone (van voor 0.3.0) is Nederland.
ZONE_NL = "NL"
ZONE_BE = "BE"
ZONES = [ZONE_NL, ZONE_BE]

# De betaalde API levert de 168-uurs voorspelling.
API_BASE = "https://wattwanneer.nl/api/v1"
# today_prices.json is publiek en dekt vandaag plus morgen. Dat hebben we apart
# nodig: zodra de dagelijkse run in de middag klaar is, begint /v1/forecast bij
# morgen 00:00 en zit het huidige uur er dus niet meer in.
TODAY_URL = "https://wattwanneer.nl/public/today_prices.json"
# Hetzelfde voor België, in hetzelfde formaat en dezelfde lokale tijd.
TODAY_URL_BE = "https://wattwanneer.nl/public/today_prices_be.json"

# De voorspelling ververst een keer per dag, in de middag. Een keer per uur
# ophalen is ruim voldoende en blijft ver onder de rate limit van 10 per minuut.
UPDATE_INTERVAL = timedelta(hours=1)

# Tijdzone waarin WattWanneer zijn lokale datums uitdrukt. Brussel heeft
# dezelfde klok, dus dit geldt ook voor de Belgische prijzen.
LOCAL_TZ = "Europe/Amsterdam"
# Een keer aangemaakt bij het importeren. ZoneInfo leest de tijdzonedata van
# schijf, en dat is blokkerende I/O die niet in de event loop hoort, terwijl
# price_at en _now_local bij elke update van elke sensor draaien.
LOCAL_ZONE = ZoneInfo(LOCAL_TZ)

ATTR_PRICES_TODAY = "prices_today"
ATTR_PRICES_TOMORROW = "prices_tomorrow"
ATTR_FORECAST = "forecast"
ATTR_GENERATED_AT = "generated_at"
ATTR_SOURCE = "source"

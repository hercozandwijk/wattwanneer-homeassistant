"""Kleine client rond de WattWanneer-API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .const import API_BASE, TODAY_URL

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=20)


class WattWanneerError(Exception):
    """Algemene fout bij het benaderen van de API."""


class InvalidAuth(WattWanneerError):
    """De API-key wordt geweigerd."""


class RateLimited(WattWanneerError):
    """Te veel verzoeken; probeer het later opnieuw."""


def _parse_utc(value: str) -> datetime:
    """ISO 8601 met Z naar een aware datetime in UTC."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class WattWanneerClient:
    """Haalt prijzen op bij WattWanneer.

    Gebruikt twee bronnen: de betaalde API voor de weekvoorspelling en het
    publieke today_prices.json voor vandaag. Dat laatste is nodig omdat de
    forecast na de dagelijkse run bij morgen 00:00 begint, waardoor het huidige
    uur er niet meer in zit.
    """

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key, "Accept": "application/json"}

    async def _get(self, url: str, *, authenticated: bool = True) -> Any:
        headers = self._headers if authenticated else {"Accept": "application/json"}
        try:
            async with self._session.get(url, headers=headers, timeout=TIMEOUT) as resp:
                if resp.status == 401:
                    raise InvalidAuth("API-key geweigerd")
                if resp.status == 429:
                    raise RateLimited("rate limit bereikt")
                if resp.status >= 400:
                    raise WattWanneerError(f"HTTP {resp.status} van {url}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise WattWanneerError(f"netwerkfout: {err}") from err

    async def async_validate(self) -> None:
        """Controleert of de key werkt. Gebruikt in de config flow."""
        await self._get(f"{API_BASE}/summary")

    async def async_fetch(self) -> dict[str, Any]:
        """Haalt alles op wat de sensoren nodig hebben."""
        forecast = await self._get(f"{API_BASE}/forecast?hours=168")
        summary = await self._get(f"{API_BASE}/summary")
        today_raw = await self._get(TODAY_URL, authenticated=False)

        points = [
            {
                "timestamp": _parse_utc(p["timestamp"]),
                "price": float(p["price_eur_per_kwh"]),
                "source": p.get("source", "model"),
            }
            for p in forecast.get("points", [])
            if p.get("timestamp") is not None
        ]

        # today_prices.json gebruikt lokale NL-tijd zonder tijdzone-aanduiding.
        today: list[dict[str, Any]] = []
        for row in today_raw or []:
            stamp = row.get("datetime")
            price = row.get("price_eur_kwh")
            if stamp is None or price is None:
                continue
            today.append({"local": str(stamp), "price": float(price)})

        return {
            "points": points,
            "summary": summary,
            "today": today,
            "generated_at": forecast.get("generated_at"),
            "model_version": forecast.get("model_version"),
        }

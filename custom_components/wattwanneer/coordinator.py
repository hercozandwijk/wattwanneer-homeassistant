"""Haalt periodiek de WattWanneer-data op."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import InvalidAuth, RateLimited, WattWanneerClient, WattWanneerError
from .const import DOMAIN, LOCAL_ZONE, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class WattWanneerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Eén ophaalronde per uur, gedeeld door alle sensoren."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: WattWanneerClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_fetch()
        except InvalidAuth as err:
            # ConfigEntryAuthFailed laat HA de herauthenticatie starten: de
            # gebruiker krijgt een melding om een nieuwe key in te vullen, in
            # plaats van dat we elk uur blijven proberen met een geweigerde key.
            # Bij de eerste refresh in async_setup_entry geldt hetzelfde.
            raise ConfigEntryAuthFailed(f"API-key geweigerd: {err}") from err
        except RateLimited as err:
            raise UpdateFailed(f"Rate limit bereikt: {err}") from err
        except WattWanneerError as err:
            raise UpdateFailed(str(err)) from err

    # ---- afgeleide waarden die meerdere sensoren gebruiken ----

    def _now_local(self) -> datetime:
        return datetime.now(timezone.utc).astimezone(LOCAL_ZONE)

    def price_at(self, moment: datetime) -> float | None:
        """Prijs van het uur waarin ``moment`` valt.

        Kijkt eerst in today_prices (dekt vandaag en morgen, ook na de
        middagrun) en valt daarna terug op de weekvoorspelling.
        """
        if not self.data:
            return None
        lokaal = moment.astimezone(LOCAL_ZONE).strftime("%Y-%m-%d %H:00")
        for row in self.data.get("today", []):
            if row["local"] == lokaal:
                return row["price"]
        uur = moment.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        for point in self.data.get("points", []):
            if point["timestamp"] == uur:
                return point["price"]
        return None

    def prices_for_day(self, offset_days: int = 0) -> list[dict[str, Any]]:
        """Alle uurprijzen van vandaag (0) of morgen (1), lokale tijd."""
        if not self.data:
            return []
        doel = (self._now_local().date()).toordinal() + offset_days
        uit = []
        for row in self.data.get("today", []):
            try:
                dag = datetime.strptime(row["local"], "%Y-%m-%d %H:00")
            except ValueError:
                continue
            if dag.date().toordinal() == doel:
                uit.append({"start": row["local"], "price": row["price"]})
        return uit

    def raw_for_day(self, offset_days: int = 0) -> list[dict[str, Any]]:
        """Uurprijzen van vandaag (0) of morgen (1) in het formaat van Nordpool.

        Elk uur als ``start``, ``end`` en ``value``. Start en einde zijn
        datetime-objecten met tijdzone, zoals bij de Nordpool-integratie, want
        pakketten rekenen ermee in hun templates (``item.start.isoformat()``,
        ``selectattr('start', '>=', now())``). Het einde is het volgende uur op
        de klok. Bij de wintertijd dekt het herhaalde uur 02:00 zo twee echte
        uren, want WattWanneer middelt die twee al tot een prijs.
        """
        uit = []
        for row in self.prices_for_day(offset_days):
            klok = datetime.strptime(row["start"], "%Y-%m-%d %H:00")
            start = klok.replace(tzinfo=LOCAL_ZONE)
            eind = (klok + timedelta(hours=1)).replace(tzinfo=LOCAL_ZONE)
            uit.append({"start": start, "end": eind, "value": row["price"]})
        return uit

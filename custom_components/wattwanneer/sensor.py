"""Sensoren van de WattWanneer-integratie."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOCAL_TZ
from .coordinator import WattWanneerCoordinator

EUR_KWH = "EUR/kWh"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: WattWanneerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            CurrentPriceSensor(coordinator, entry),
            NextHourPriceSensor(coordinator, entry),
            AverageTodaySensor(coordinator, entry),
            LowestTodaySensor(coordinator, entry),
            HighestTodaySensor(coordinator, entry),
            CheapestWindowSensor(coordinator, entry),
            WeekAverageSensor(coordinator, entry),
        ]
    )


class WattWanneerSensor(CoordinatorEntity[WattWanneerCoordinator], SensorEntity):
    """Basis met de gedeelde device-info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WattWanneerCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="WattWanneer",
            manufacturer="WattWanneer",
            model="Stroomprijsvoorspelling",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://wattwanneer.nl/api.html",
        )

    @property
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)


class PriceSensor(WattWanneerSensor):
    """Gemeenschappelijke instellingen voor alles wat een prijs toont.

    Bewust zonder state_class: Home Assistant staat 'measurement' niet toe bij
    device_class 'monetary' en waarschuwt daar bij elke update over. Grafieken
    en historie werken gewoon via de recorder; alleen langetermijnstatistieken
    vervallen, en die zijn voor een prijs die per uur verspringt toch niet
    zinvol.
    """

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = EUR_KWH
    _attr_suggested_display_precision = 4


class CurrentPriceSensor(PriceSensor):
    _attr_translation_key = "current_price"
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_price"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.price_at(self._now)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "prices_today": self.coordinator.prices_for_day(0),
            "prices_tomorrow": self.coordinator.prices_for_day(1),
            "generated_at": (self.coordinator.data or {}).get("generated_at"),
        }


class NextHourPriceSensor(PriceSensor):
    _attr_translation_key = "next_hour_price"
    _attr_icon = "mdi:clock-fast"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_hour_price"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.price_at(self._now + timedelta(hours=1))


class AverageTodaySensor(PriceSensor):
    _attr_translation_key = "average_today"
    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_average_today"

    @property
    def native_value(self) -> float | None:
        rijen = self.coordinator.prices_for_day(0)
        if not rijen:
            return None
        return round(sum(r["price"] for r in rijen) / len(rijen), 4)


class LowestTodaySensor(PriceSensor):
    _attr_translation_key = "lowest_today"
    _attr_icon = "mdi:trending-down"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_lowest_today"

    @property
    def native_value(self) -> float | None:
        rijen = self.coordinator.prices_for_day(0)
        return min((r["price"] for r in rijen), default=None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rijen = self.coordinator.prices_for_day(0)
        if not rijen:
            return {}
        goedkoopste = min(rijen, key=lambda r: r["price"])
        return {"hour": goedkoopste["start"]}


class HighestTodaySensor(PriceSensor):
    _attr_translation_key = "highest_today"
    _attr_icon = "mdi:trending-up"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_highest_today"

    @property
    def native_value(self) -> float | None:
        rijen = self.coordinator.prices_for_day(0)
        return max((r["price"] for r in rijen), default=None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rijen = self.coordinator.prices_for_day(0)
        if not rijen:
            return {}
        duurste = max(rijen, key=lambda r: r["price"])
        return {"hour": duurste["start"]}


class CheapestWindowSensor(WattWanneerSensor):
    """Starttijd van het goedkoopste aaneengesloten venster."""

    _attr_translation_key = "cheapest_window"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_cheapest_window"

    @property
    def native_value(self) -> datetime | None:
        venster = ((self.coordinator.data or {}).get("summary") or {}).get(
            "cheapest_window"
        )
        if not venster or not venster.get("start"):
            return None
        return datetime.fromisoformat(venster["start"].replace("Z", "+00:00"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        venster = ((self.coordinator.data or {}).get("summary") or {}).get(
            "cheapest_window"
        ) or {}
        eind = venster.get("end_exclusive")
        return {
            "end": eind,
            "window_hours": venster.get("window_hours"),
            "average_price": venster.get("avg_price"),
            "local_start": (
                datetime.fromisoformat(venster["start"].replace("Z", "+00:00"))
                .astimezone(ZoneInfo(LOCAL_TZ))
                .strftime("%Y-%m-%d %H:%M")
                if venster.get("start")
                else None
            ),
        }


class WeekAverageSensor(PriceSensor):
    """Gemiddelde over de hele voorspelling; de reden om WattWanneer te gebruiken."""

    _attr_translation_key = "week_average"
    _attr_icon = "mdi:calendar-week"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_week_average"

    @property
    def native_value(self) -> float | None:
        punten = (self.coordinator.data or {}).get("points") or []
        if not punten:
            return None
        return round(sum(p["price"] for p in punten) / len(punten), 4)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        punten = (self.coordinator.data or {}).get("points") or []
        if not punten:
            return {}
        goedkoopste = min(punten, key=lambda p: p["price"])
        return {
            "hours": len(punten),
            "cheapest_hour": goedkoopste["timestamp"].astimezone(
                ZoneInfo(LOCAL_TZ)
            ).strftime("%Y-%m-%d %H:%M"),
            "cheapest_price": goedkoopste["price"],
            "forecast": [
                {
                    "start": p["timestamp"].isoformat(),
                    "price": p["price"],
                    "source": p["source"],
                }
                for p in punten
            ],
        }

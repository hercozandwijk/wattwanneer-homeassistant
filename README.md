<img src="icon.png" alt="WattWanneer" width="96" align="right" />

# WattWanneer voor Home Assistant

[![Validatie](https://github.com/hercozandwijk/wattwanneer-homeassistant/actions/workflows/validate.yml/badge.svg)](https://github.com/hercozandwijk/wattwanneer-homeassistant/actions/workflows/validate.yml)
[![hacs](https://img.shields.io/badge/HACS-custom-41BDF5.svg)](https://hacs.xyz)

Zet de Nederlandse stroomprijzen van [WattWanneer](https://wattwanneer.nl) in Home
Assistant, inclusief de voorspelling tot zeven dagen vooruit. Waar day-ahead-bronnen
stoppen bij morgen, kun je hiermee kiezen welke dag van de week het goedkoopst is.

## Wat je krijgt

| Sensor | Wat het is |
| --- | --- |
| Huidige prijs | Prijs van het lopende uur |
| Prijs volgend uur | Handig voor automations die net iets vooruit kijken |
| Gemiddelde vandaag | Referentie om "goedkoop" tegen af te zetten |
| Laagste vandaag | Met het uur als attribuut |
| Hoogste vandaag | Met het uur als attribuut |
| Goedkoopste venster | Starttijd van het goedkoopste aaneengesloten blok |
| Gemiddelde deze week | Met de volledige 168-uurs reeks als attribuut |

De sensoren `Huidige prijs` en `Gemiddelde deze week` hebben de volledige
prijsreeksen als attributen, zodat je ze direct in ApexCharts of een eigen
template kunt gebruiken.

## Installatie

1. Voeg deze repository in HACS toe als custom repository (categorie: Integration).
2. Installeer WattWanneer en herstart Home Assistant.
3. Ga naar Instellingen, Apparaten en diensten, Integratie toevoegen, en zoek WattWanneer.
4. Vul je API-key in.

Nog geen API-key? Je sluit een abonnement af op
[wattwanneer.nl/api.html](https://wattwanneer.nl/api.html).

## Hoe vaak wordt er opgehaald

Eén keer per uur. De voorspelling zelf ververst één keer per dag, in de middag,
dus vaker ophalen levert dezelfde data op. De API staat 10 verzoeken per minuut
toe, dus je zit hier ruim onder.

## Voorbeeld: vaatwasser op het goedkoopste blok

```yaml
automation:
  - alias: Vaatwasser op het goedkoopste venster
    trigger:
      - platform: time_pattern
        minutes: "/5"
    condition:
      - condition: template
        value_template: >
          {{ as_timestamp(states('sensor.wattwanneer_cheapest_window'))
             <= as_timestamp(now()) < as_timestamp(states('sensor.wattwanneer_cheapest_window'))
             + state_attr('sensor.wattwanneer_cheapest_window','window_hours') * 3600 }}
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.vaatwasser
```

## Problemen melden

Open een issue in deze repository. Vermeld je Home Assistant-versie en het
relevante stuk uit je log (Instellingen, Systeem, Logboek).

## Hoe het onder water werkt

De integratie gebruikt twee bronnen:

- `/v1/forecast` en `/v1/summary` van de betaalde API leveren de 168-uurs
  voorspelling en het goedkoopste venster.
- Het publieke `today_prices.json` levert de uren van vandaag. Dat is nodig
  omdat de API na de dagelijkse run (in de middag) begint bij morgen 00:00,
  waardoor het huidige uur er niet meer in zit. Zonder die tweede bron zou de
  sensor "Huidige prijs" 's middags leeglopen.

Alle tijdstempels uit de API zijn UTC; `today_prices.json` gebruikt lokale
Nederlandse tijd. De coordinator rekent dat om via de tijdzonedatabase, dus ook
rond de overgang naar zomer- en wintertijd klopt het.

De prijssensoren hebben bewust geen `state_class`. Home Assistant staat
`measurement` niet toe bij `device_class: monetary` en waarschuwt daar bij elke
update over. Grafieken en historie werken gewoon via de recorder.

## Ontwikkelen en testen

Je hebt geen draaiende Home Assistant nodig om te testen:

```bash
python3 -m venv venv
./venv/bin/pip install pytest-homeassistant-custom-component
./venv/bin/python -m pytest tests/ -q
```

Wil je het in een echte Home Assistant proberen, dan kan dat zonder Docker:

```bash
python3 -m venv venv
./venv/bin/pip install homeassistant
mkdir -p config/custom_components
cp -r custom_components/wattwanneer config/custom_components/
./venv/bin/hass --config config
```

Daarna is de interface bereikbaar op http://localhost:8123.

De GitHub Action draait bij elke push en daarnaast elke maandagochtend tegen de
nieuwste Home Assistant, zodat een brekende wijziging in HA zichtbaar wordt
voordat een gebruiker er tegenaan loopt.

## Status

Getest op Home Assistant 2026.8.2: installatie via de configuratiedialoog
(geldige key, ongeldige key, dezelfde key twee keer), alle zeven sensoren met
live data, en een volledige herstart waarna alles terugkomt. Zestien unit tests
dekken daarnaast de foutafhandeling, waaronder een onbereikbare API.

Nog te doen voor opname in de standaard HACS-lijst: een pull request naar
[home-assistant/brands](https://github.com/home-assistant/brands) en naar
[hacs/default](https://github.com/hacs/default). Tot die tijd werkt de
integratie prima als custom repository.

## Voor de HACS-aanvraag

De map `brands/` bevat `icon.png` (256x256) en `icon@2x.png` (512x512), klaar
voor de pull request naar [home-assistant/brands](https://github.com/home-assistant/brands).
Die is pas nodig bij opname in de standaard HACS-lijst, niet om de integratie
als custom repository te gebruiken.

## Licentie

MIT, zie [LICENSE](LICENSE).

<img src="icon.png" alt="WattWanneer" width="96" align="right" />

# WattWanneer voor Home Assistant

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

## Voor de HACS-aanvraag

De map `brands/` bevat `icon.png` (256x256) en `icon@2x.png` (512x512), klaar
voor de pull request naar [home-assistant/brands](https://github.com/home-assistant/brands).
Die is pas nodig bij opname in de standaard HACS-lijst, niet om de integratie
als custom repository te gebruiken.

## Licentie

MIT, zie [LICENSE](LICENSE).

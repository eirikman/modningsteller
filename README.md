# Modningsteller 1.0.0

Første stabile versjon av Modningsteller.

Denne releasen viderefører funksjonaliteten i 0.9.1 og inkluderer integrasjonsikonet med rype samt et eksempel på gjenbrukbar Lovelace/Decluttering Card-mal.

## Installasjon

Kopier `custom_components/modningsteller` til `/config/custom_components/` og start Home Assistant på nytt.

## Dashboard-mal

Se `dashboard/modningsteller_decluttering.yaml`. Den bygger videre på oppsettet som er brukt i prosjektet og inkluderer status, sensorhelse, kalibrering og notat.

Eksempel på bruk etter at templaten er lagt inn:

```yaml
type: custom:decluttering-card
template: modningsteller
variables:
  - id: rype
```


## v1.0.1

Adjusted temperature sensor staleness handling for devices such as Zigbee temperature sensors that may report infrequently. A reading is now considered stale only after at least 2 hours, or three times the configured update interval when that is longer. Degree-day accumulation is paused when the reading exceeds that threshold.

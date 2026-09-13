# Modningsteller

A Home Assistant custom integration for tracking the maturation of game meat using degree days and temperature history.

Modningsteller is designed for meat maturation where accumulated temperature exposure is used as an indicator of maturation progress. Each maturation process is independent and can use its own temperature sensor, target value and update interval.

> **Status:** Personal project / private repository  
> The integration is currently developed for personal use. The project may be published to HACS at a later stage.

## Features

- Multiple independent maturation counters
- Configurable starting degree-day value
- Configurable target value
- Selectable temperature sensor
- Change temperature sensor while a process is running
- Rolling one-hour average temperature
- Configurable calculation interval
- Start, pause and reset controls
- Explicit process states:
  - Stopped
  - Running
  - Paused
  - Target reached
- Degree-day accumulation continues after the target is reached
- Notification when the target is reached
- Estimated finish time
- Elapsed active time
- Remaining degree days
- Timestamp for when the target was reached
- Temperature sensor health monitoring
- Detection of stale or unavailable temperature data
- Calibration of accumulated degree days during an ongoing process
- Calibration comments and history
- Notes for the maturation process
- History of important events
- Persistent state across Home Assistant restarts
- Norwegian and English translations
- Integration branding with a ptarmigan icon
- Optional Lovelace dashboard template

## How it works

The integration accumulates degree days based on the rolling average temperature from the selected temperature sensor.

The basic calculation is:

    degree days += average temperature × elapsed time in days

The temperature average is calculated over the most recent hour.

The calculation interval is configurable. The default interval is 10 minutes.

The target value is a notification threshold, not a stopping point. When the target is reached:

1. The target is marked as reached.
2. A notification/event is generated.
3. The counter continues accumulating degree days.

This makes it possible to see the actual degree-day value when the meat is eventually removed.

## Installation

### Manual installation

Copy the integration directory into your Home Assistant configuration directory:

    /config/custom_components/modningsteller/

The resulting structure should be:

    /config
    └── custom_components
        └── modningsteller
            ├── __init__.py
            ├── button.py
            ├── config_flow.py
            ├── const.py
            ├── coordinator.py
            ├── manifest.json
            ├── number.py
            ├── select.py
            ├── sensor.py
            ├── text.py
            ├── brand
            │   └── icon.png
            └── translations
                ├── en.json
                └── nb.json

Restart Home Assistant after installation.

The integration can then be added from:

**Settings → Devices & services → Add integration**

Search for:

**Modningsteller**

## Configuration

Each maturation process is configured independently.

Typical configuration options include:

- Name
- Temperature sensor
- Initial degree-day value
- Target degree-day value
- Calculation interval

### Temperature sensor

The temperature sensor can also be changed while a maturation process is running.

When the sensor is changed, accumulated degree days and process timing are preserved. Temperature averaging starts using the new sensor so that historical data from different sensors is not mixed.

## Process controls

### Start

Starts a stopped or paused maturation process.

Pressing Start while the process is already running has no effect.

### Pause

Stops degree-day accumulation and active-time counting while preserving the current process state.

### Reset

Resets the process to its configured initial degree-day value and places it in the **Stopped** state.

Reset does not automatically start a new process.

A new start time is created when Start is pressed after a reset.

## Calibration

Degree days can be adjusted during an ongoing process.

Calibration does not reset:

- Start time
- Elapsed active time
- Temperature sensor
- Process history

Calibration events are recorded together with the previous value, new value, timestamp and optional comment.

This is useful when part of the maturation process took place before the process was added to Home Assistant, or when an external measurement indicates that the accumulated value should be corrected.

## Notes

Each maturation process can have an associated note.

Notes can be used for information such as:

- Type of game
- Cut of meat
- Location
- Refrigerator changes
- Other observations

Notes are stored persistently and survive Home Assistant restarts.

## Temperature sensor health

The integration monitors the selected temperature sensor.

The sensor health state can indicate conditions such as:

- OK
- Stale
- Unavailable
- Unknown

If temperature data is no longer considered valid, degree-day accumulation is paused to avoid accumulating incorrect values from a stale temperature reading.

This is intentionally tolerant of battery-powered Zigbee temperature sensors, which may report infrequently.

The stale-data threshold is currently designed to allow relatively long reporting intervals.

## Sensors

Depending on configuration and process state, a maturation counter provides entities such as:

- Degree days
- Remaining degree days
- One-hour average temperature
- Elapsed time
- Start time
- Estimated finish time
- Target reached
- Status
- Temperature sensor health
- Last valid temperature reading
- Last event

Additional control entities are provided for:

- Start
- Pause
- Reset
- Calibration
- Notes
- Temperature sensor selection

## Events

The integration emits Home Assistant events for important process changes.

Events can include:

- `started`
- `paused`
- `reset`
- `calibrated`
- `temperature_sensor_changed`
- `target_reached`
- `sensor_health_changed`
- `note_added`
- `note_cleared`

These events can be used in Home Assistant automations.

## Dashboard

An optional Lovelace dashboard template is included in:

    dashboard/modningsteller_decluttering.yaml

The template is intended for use with the [Decluttering Card](https://github.com/custom-cards/decluttering-card).

Example:

```yaml
type: custom:decluttering-card
template: modningsteller
variables:
  - id: rype
```

The `id` must match the entity ID prefix generated by your Modningsteller instance.

For example:

```yaml
type: custom:decluttering-card
template: modningsteller
variables:
  - id: hjortelar
```

The dashboard template is optional. The integration itself does not depend on it.

## Development

The project repository is structured as follows:

```text
custom_components/modningsteller/
    Home Assistant integration

dashboard/
    Optional Lovelace dashboard templates
```

Future development uses Git for version control and GitHub releases for versioned builds.

## Versioning

The project uses semantic versioning:

- `MAJOR` - breaking changes
- `MINOR` - new functionality
- `PATCH` - bug fixes and small improvements

Example:

```text
v1.0.1
v1.1.0
v1.1.1
```

## Requirements

The integration is developed for modern Home Assistant versions and is currently tested against the Home Assistant version used by the developer.

## License

Modningsteller is licensed under the [MIT License](LICENSE).

## Disclaimer

This integration is a personal Home Assistant project.

Degree-day calculations are provided as an aid for monitoring a maturation process and should not be considered a substitute for appropriate food-safety practices, temperature control or professional guidance.
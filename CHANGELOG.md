# Changelog

## [unreleased]

### Added

### Fixed

### Changed


---


## [v1.1.4]

### Added
- Updated README with automation on events example
- Added localized notification messages.

### Fixed
- Notification text for staled temp sensor corrected.


### Changed

---


## [v1.1.3]

## What's changed

### Bug Fixes

- Fixed temperature sensor selection so changes made from the dashboard persist across Home Assistant restarts.
- Improved temperature sensor handling during Home Assistant startup.
- Sensor health now remains Unknown while Home Assistant or the selected temperature sensor is still starting.
- Added an automatic sensor health refresh once Home Assistant startup is complete.
- Prevented false temperature sensor unavailable notifications during startup.
- Improved handling of temporary sensor unavailability while retaining the last known valid temperature.

### Tests

- Added regression tests for temperature sensor persistence and startup health handling.
- GitHub Actions tests pass successfully.


---

## [v1.1.2]

## What's changed

- Fixed an issue where the temperature sensor selected from the dashboard reverted to the original configuration after a Home Assistant restart.
- Dashboard-selected temperature sensors are now persisted in the Config Entry options.
- Added migration for existing installations where the selected sensor was only stored in Modningsteller's persistent state.
- Added regression tests for sensor persistence and migration.
- Minor fix in Dashboard

No changes were made to the degree-day calculation or other process logic.


---


## [V1.1.1]

## What's changed

This release focuses on the Lovelace dashboard experience and documentation.

### Dashboard
- Added three reusable Decluttering Card templates:
  - `modningsteller_oversikt` — overview gauge
  - `modningsteller_popup` — detailed popup with controls and information
  - `modningsteller_kontroll` — full control dashboard

### Documentation
- Updated the README with dashboard screenshots
- Added examples showing how to use the Decluttering Card templates
- Clarified dashboard template usage and entity ID prefixes

### Compatibility
- No changes to the core maturation calculation or process logic
- Existing Modningsteller configurations are unchanged


---

## [v1.1.0]

## What's changed

### Sensor health
- Added a configurable stale-temperature timeout per maturation counter.
- The timeout can be changed after creation.
- Stale and unavailable temperature sensors no longer stop maturation if a last known temperature is available.
- The last known temperature is used while the sensor is stale or unavailable.
- Sensor health warnings are still generated when temperature data becomes stale or unavailable.

### Reset behaviour
- Reset now clears the active calibration value.
- Reset clears the active calibration comment.
- Reset clears the active maturation note.
- Calibration and note history are preserved across resets.
- Reset places the counter in the Stopped state.

### Testing
- Added and updated automated tests for the new sensor-health and reset behaviour.


---


## [v1.0.2]

## What's changed

- Expanded automated test coverage for the core coordinator logic.
- Added tests for start, pause and reset behaviour.
- Added tests for target reached and continued accumulation.
- Added tests for calibration and temperature sensor changes.
- Added tests for sensor health and stale temperature data.
- Added tests for notes, events and persistent state.
- Improved CI test reliability.

This release does not intentionally change the user-facing functionality of the integration.


---


## [v1.0.1]

## What's changed

- Expanded automated test coverage for the core coordinator logic.
- Added tests for start, pause and reset behaviour.
- Added tests for target reached and continued accumulation.
- Added tests for calibration and temperature sensor changes.
- Added tests for sensor health and stale temperature data.
- Added tests for notes, events and persistent state.
- Improved CI test reliability.

This release does not intentionally change the user-facing functionality of the integration.
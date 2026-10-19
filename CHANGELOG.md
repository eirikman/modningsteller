# Changelog

## [unreleased]

### Added

### Fixed

### Changed


---


## [v1.5.0]

### Fixed
- Changing the temperature sensor in Configure works like changing it from the dashboard: the interval with the old sensor is counted, and the change is recorded in the event and sensor-change history.
- Saving options in Configure no longer loses the counting since the last update when the integration reloads.
- Temperature sensors that have not reported a value yet can be selected from the dashboard list, instead of failing.
- Choosing an entity that is not a temperature sensor shows a translated error message.
- Modningsteller's own average temperature sensors can no longer be chosen as the temperature sensor, in the dashboard list, in Configure or in the initial setup.

### Changed
- The dashboard sensor list only shows temperature sensors that measure (state class `measurement`), which leaves out set points such as a car's set temperature. The selected sensor is always kept in the list.
- The dashboard sensor list always shows the area in parentheses when the sensor has one, also when it is inherited from the sensor's device or already part of the name.


---


## [v1.4.0]

### Added
- Test that sets up the whole integration with a real recorder, to catch start-up failures.

### Fixed
- Temperature history is read through the recorder's database executor, as Home Assistant requires.
- Deleting a counter removes its stored state and its notifications.
- Reset, and calibration below a reached target, remove the old target-reached notification.
- Counting continues with the last known temperature during the startup wait after a Home Assistant restart. Only the sensor status and notification wait for the sensor.

### Changed
- The one-hour average temperature is time-weighted. Each reading counts for as long as it was the current value, and unavailable periods are left out. Sensors that only report on change no longer skew the average.


---


## [v1.3.0]

### Added
- Update every minute when the estimated time to the target is shorter than the configured update interval.

### Fixed
- Temperature sensor selected from the dashboard is persisted again across Home Assistant restarts (regression since v1.1.3).
- Target-reached notification no longer fails when no average temperature is known.
- Expected finish time uses the same temperature model as the degree-day accumulation, including the range below 4 °C.
- Lowering the target below the current value marks the target as reached and sends the notification.
- Coordinator passes the config entry explicitly, as required by newer Home Assistant versions.

### Changed
- Tests check that the manifest version has a matching CHANGELOG entry, and releases check that the tag matches the manifest version.


---


## [v1.2.1]

### Changed
- Status after reset is now called Ready (Klar) instead of Stopped.
- Sensor health notifications are no longer sent while the counter is Ready. Sensor health is still updated.
- State attribute names are now English (for example `mål` → `target_degree_days`). Templates and automations that read the old Norwegian attribute names must be updated.
- Remaining Norwegian text in the code moved to the translation files.


---


## [v1.2.0]

### Changed
- New degree-day model for temperatures below 4 °C, to reflect slower biological processes:
  - At or above 4 °C: degree days += average temperature × elapsed days
  - Between 0 °C and 4 °C: degree days += 40 / (40 − 7.5 × average temperature) × elapsed days
  - Below 0 °C: no degree days are accumulated


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
"""Data update coordinator for Modningsteller."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import Any

from homeassistant.components.recorder import get_instance, history
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    AVERAGE_WINDOW_MINUTES,
    CONF_INITIAL_DEGREE_DAYS,
    CONF_TARGET_DEGREE_DAYS,
    CONF_TEMPERATURE_ENTITY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_SENSOR_STALE_MINUTES,
    CONF_SENSOR_STALE_MINUTES,
    MIN_SENSOR_STALE_MINUTES,
    MAX_SENSOR_STALE_MINUTES,
    DOMAIN,
    FAST_UPDATE_INTERVAL_MINUTES,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class ModningstellerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate temperature history reads and degree-day accumulation."""

    STARTUP_RETRY_INTERVAL_SECONDS = 15
    STARTUP_RETRY_ATTEMPTS = 20  # Up to 5 minutes after Home Assistant starts.

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.temperature_entity = self._get_option(CONF_TEMPERATURE_ENTITY)
        self.initial_degree_days = float(self._get_option(CONF_INITIAL_DEGREE_DAYS))
        self.target_degree_days = float(self._get_option(CONF_TARGET_DEGREE_DAYS))
        self.update_interval_minutes = int(self._get_option(CONF_UPDATE_INTERVAL))
        self.sensor_stale_minutes = self._get_sensor_stale_minutes()

        self.degree_days = float(entry.data[CONF_INITIAL_DEGREE_DAYS])
        self.average_temperature: float | None = None
        self.last_update: datetime | None = None
        self.running = True
        self.stopped = False
        self.reached_target = self.degree_days >= self.target_degree_days
        self.target_notification_sent = False
        self.target_reached_at: datetime | None = None

        # Process timing. active_seconds excludes time while paused and the
        # unknown interval during a Home Assistant restart.
        self.run_started_at: datetime | None = None
        self.active_seconds: float = 0.0
        self.calibration_value: float = self.degree_days
        self.calibration_comment: str = ""
        self.calibration_history: list[dict[str, Any]] = []
        self.temperature_change_history: list[dict[str, Any]] = []
        self.last_event: str = "initialized"
        self.last_event_at: datetime | None = None
        self.last_event_details: dict[str, Any] = {}
        self.note: str = ""
        self.note_updated_at: datetime | None = None
        self.note_history: list[dict[str, Any]] = []

        self.temperature_sensor_health: str = "unknown"
        self.last_valid_temperature: float | None = None
        self.last_valid_temperature_at: datetime | None = None
        self.last_temperature_age_seconds: float | None = None

        self._temperature_window_start: datetime | None = None
        self._stored_temperature_entity: str | None = None
        # Home Assistant integrations that provide the selected temperature
        # sensor may finish starting shortly after Modningsteller itself.
        # Keep sensor health as unknown during this startup grace period so a
        # transient startup race does not create a false unavailable alarm.
        self._startup_grace_active = True
        self._startup_retry_task: asyncio.Task[None] | None = None
        self.on_target_reached = None
        self.on_target_cleared = None
        self.on_sensor_health_changed = None
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}_{entry.entry_id}",
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=self.update_interval_minutes),
        )

    def _get_option(self, key: str) -> Any:
        """Return an option, falling back to the original config data."""
        return self.entry.options.get(key, self.entry.data.get(key))

    def _get_sensor_stale_minutes(self) -> int:
        """Return the configured stale timeout in minutes."""
        raw_value = self.entry.options.get(
            CONF_SENSOR_STALE_MINUTES,
            self.entry.data.get(CONF_SENSOR_STALE_MINUTES, DEFAULT_SENSOR_STALE_MINUTES),
        )
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            value = DEFAULT_SENSOR_STALE_MINUTES
        return min(max(value, MIN_SENSOR_STALE_MINUTES), MAX_SENSOR_STALE_MINUTES)

    async def async_startup_sensor_check(self) -> None:
        """Refresh until the selected temperature sensor is ready after startup."""
        try:
            for _attempt in range(self.STARTUP_RETRY_ATTEMPTS):
                await self.async_refresh()
                if not self._startup_grace_active:
                    return
                await asyncio.sleep(self.STARTUP_RETRY_INTERVAL_SECONDS)

            # The grace window has expired. Perform one final normal refresh so
            # a genuinely unavailable sensor becomes visible and can notify.
            self._startup_grace_active = False
            await self.async_refresh()
        except asyncio.CancelledError:
            raise

    async def _async_setup(self) -> None:
        """Load persisted state."""
        stored = await self._store.async_load()
        now = dt_util.utcnow()
        if not stored:
            self.last_update = now
            self.run_started_at = now
            return

        try:
            self.degree_days = float(stored.get("degree_days", self.degree_days))
            stored_average = stored.get("average_temperature")
            self.average_temperature = (
                float(stored_average) if stored_average is not None else None
            )
            stored_running = stored.get("running")
            self.running = bool(stored_running) if stored_running is not None else True
            stored_stopped = stored.get("stopped")
            if stored_stopped is not None:
                self.stopped = bool(stored_stopped)
            else:
                self.stopped = self.last_event == "reset" and not self.running

            stored_window_start = stored.get("temperature_window_start")
            self._temperature_window_start = (
                dt_util.parse_datetime(stored_window_start)
                if stored_window_start
                else None
            )
            self._stored_temperature_entity = stored.get("temperature_entity")

            self.calibration_value = float(stored.get("calibration_value", self.degree_days))
            self.calibration_comment = str(stored.get("calibration_comment", ""))
            self.calibration_history = list(stored.get("calibration_history", []))[-20:]
            self.temperature_change_history = list(
                stored.get("temperature_change_history", [])
            )[-20:]
            self.last_event = str(stored.get("last_event", "initialized"))
            stored_last_event_at = stored.get("last_event_at")
            self.last_event_at = (
                dt_util.parse_datetime(stored_last_event_at)
                if stored_last_event_at
                else None
            )
            stored_event_details = stored.get("last_event_details", {})
            self.last_event_details = (
                dict(stored_event_details)
                if isinstance(stored_event_details, dict)
                else {}
            )
            self.note = str(stored.get("note", ""))[:1000]
            stored_note_updated_at = stored.get("note_updated_at")
            self.note_updated_at = (
                dt_util.parse_datetime(stored_note_updated_at)
                if stored_note_updated_at
                else None
            )
            self.note_history = list(stored.get("note_history", []))[-20:]

            self.temperature_sensor_health = str(stored.get("temperature_sensor_health", "unknown"))
            stored_last_valid_temperature = stored.get("last_valid_temperature")
            self.last_valid_temperature = (
                float(stored_last_valid_temperature)
                if stored_last_valid_temperature is not None
                else None
            )
            stored_last_valid_temperature_at = stored.get("last_valid_temperature_at")
            self.last_valid_temperature_at = (
                dt_util.parse_datetime(stored_last_valid_temperature_at)
                if stored_last_valid_temperature_at
                else None
            )

            stored_active_seconds = stored.get("active_seconds", 0.0)
            self.active_seconds = max(float(stored_active_seconds), 0.0)
            stored_run_started_at = stored.get("run_started_at")
            self.run_started_at = (
                dt_util.parse_datetime(stored_run_started_at)
                if stored_run_started_at
                else None
            )

            stored_last_update = stored.get("last_update")
            # Never accumulate an unknown interval while Home Assistant was
            # restarting. Resume timing from now on the next update.
            self.last_update = now

            stored_target_reached_at = stored.get("target_reached_at")
            self.target_reached_at = (
                dt_util.parse_datetime(stored_target_reached_at)
                if stored_target_reached_at
                else None
            )
            self.target_notification_sent = bool(
                stored.get("target_notification_sent", False)
            )

            self.reached_target = self.degree_days >= self.target_degree_days
            if not self.reached_target:
                self.target_reached_at = None
                self.target_notification_sent = False
            elif self.target_reached_at is None and not self.stopped:
                # The target was lowered below the current value in the
                # options flow. Treat it as reached now, so the event,
                # timestamp and notification are not silently skipped.
                self.target_reached_at = now
                self._set_event(
                    "target_reached",
                    now,
                    {"degree_days": round(self.degree_days, 3), "via": "target_changed"},
                )
                if not self.target_notification_sent:
                    self.target_notification_sent = True
                    if self.on_target_reached is not None:
                        self.hass.async_create_task(self.on_target_reached())

            if self.run_started_at is None and self.running:
                self.run_started_at = now

            # If the configured sensor changed, start a fresh average window
            # so old-sensor history cannot leak into the new sensor's average.
            if (
                self._stored_temperature_entity
                and self._stored_temperature_entity != self.temperature_entity
            ):
                self._temperature_window_start = now
                self.last_update = now
                self.average_temperature = None

        except (TypeError, ValueError) as err:
            _LOGGER.warning("Could not restore stored Modningsteller state: %s", err)
            self.last_update = now
            self.run_started_at = now if self.running else None

    @property
    def temperature_sensor_stale_after_seconds(self) -> float:
        """Return how old a temperature reading may be before it is stale."""
        return float(self.sensor_stale_minutes * 60)

    async def async_set_sensor_stale_minutes(self, value: int) -> None:
        """Set and persist the sensor stale timeout."""
        value = int(value)
        if not MIN_SENSOR_STALE_MINUTES <= value <= MAX_SENSOR_STALE_MINUTES:
            raise ValueError(
                f"Sensor stale timeout must be between {MIN_SENSOR_STALE_MINUTES} and "
                f"{MAX_SENSOR_STALE_MINUTES} minutes"
            )
        self.sensor_stale_minutes = value
        options = dict(self.entry.options)
        options[CONF_SENSOR_STALE_MINUTES] = value
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        await self._async_save_state()
        self.async_set_updated_data(self._data())

    def _set_sensor_health(
        self, health: str, now: datetime, reason: str | None = None
    ) -> None:
        """Update sensor health and emit an event when it changes."""
        if health == self.temperature_sensor_health:
            return
        old_health = self.temperature_sensor_health
        self.temperature_sensor_health = health
        details = {
            "old_health": old_health,
            "new_health": health,
            "reason": reason,
            "temperature_entity": self.temperature_entity,
            "last_valid_temperature": self.last_valid_temperature,
            "last_valid_temperature_at": self.last_valid_temperature_at,
        }
        self._set_event("sensor_health_changed", now, details)
        # Sensor health continues to update while the counter is Ready, but
        # a reset/ready counter must not generate sensor-health notifications.
        # The event is still emitted so the health state and event history stay current.
        if not self.stopped and self.on_sensor_health_changed is not None:
            self.hass.async_create_task(
                self.on_sensor_health_changed(old_health, health, reason)
            )

    async def _async_update_data(self) -> dict[str, Any]:
        """Read temperature history and accumulate degree days."""
        data = await self._async_update_data_internal(accumulate=True)
        self._adjust_update_interval()
        return data

    @callback
    def async_set_updated_data(self, data: dict[str, Any]) -> None:
        """Publish new data, using the update interval for the new state."""
        self._adjust_update_interval()
        super().async_set_updated_data(data)

    def estimated_seconds_to_target(self) -> float | None:
        """Return the estimated time until the target, or None if unknown.

        Uses the same temperature model as the accumulation. Returns None
        when the counter is not running, the target is already reached, or
        no maturation happens at the current average temperature.
        """
        if not self.running or self.reached_target or self.average_temperature is None:
            return None
        degree_days_per_day = self._calculate_degree_days(self.average_temperature, 86400)
        if degree_days_per_day <= 0:
            return None
        remaining_degree_days = max(self.target_degree_days - self.degree_days, 0.0)
        return remaining_degree_days / degree_days_per_day * 86400

    def _adjust_update_interval(self) -> None:
        """Update every minute when the target is due before the next update.

        With the configured interval, the target could be passed by up to one
        interval before it is detected. Close to the target, a one-minute
        interval makes the target time and notification more accurate.
        """
        configured = timedelta(minutes=self.update_interval_minutes)
        fast = timedelta(minutes=FAST_UPDATE_INTERVAL_MINUTES)
        seconds_to_target = self.estimated_seconds_to_target()
        if (
            configured > fast
            and seconds_to_target is not None
            and seconds_to_target < configured.total_seconds()
        ):
            self.update_interval = fast
        else:
            self.update_interval = configured

    async def _async_update_data_internal(self, *, accumulate: bool) -> dict[str, Any]:
        """Refresh temperature status and optionally accumulate process time."""
        now = dt_util.utcnow()

        current_state = self.hass.states.get(self.temperature_entity)
        current_value: float | None = None
        health = "ok"
        reason: str | None = None

        if current_state is None or current_state.state in {"unknown", "unavailable"}:
            health = "unavailable"
            reason = "state_unavailable"
        else:
            try:
                current_value = float(current_state.state)
            except (TypeError, ValueError):
                current_value = None
            if current_value is None or not -100 < current_value < 100:
                current_value = None
                health = "unavailable"
                reason = "invalid_temperature"

        if current_value is not None and current_state is not None:
            # We have now received a real reading from the selected sensor.
            # End the startup grace period permanently for this run.
            self._startup_grace_active = False
            self.last_temperature_age_seconds = max(
                (now - current_state.last_updated).total_seconds(), 0.0
            )
            self.last_valid_temperature = current_value
            self.last_valid_temperature_at = current_state.last_updated
            if self.last_temperature_age_seconds > self.temperature_sensor_stale_after_seconds:
                health = "stale"
                reason = "reading_too_old"
        else:
            self.last_temperature_age_seconds = (
                max((now - self.last_valid_temperature_at).total_seconds(), 0.0)
                if self.last_valid_temperature_at is not None
                else None
            )

        # A selected temperature integration can become available a little
        # later than Home Assistant itself. While the startup retry window is
        # active, treat an unavailable/invalid live sensor as unknown. This
        # prevents false alarms during startup while allowing genuine sensor
        # failures to be reported normally afterward. Only the status and the
        # notification wait: counting continues with the last known
        # temperature, so the run does not stop while the sensor starts.
        if self._startup_grace_active and health == "unavailable":
            self._set_sensor_health("unknown", now, "home_assistant_starting")
            if self.last_valid_temperature is None:
                self.average_temperature = None
                if self.running:
                    self.last_update = now
                await self._async_save_state()
                return self._data()
            self.average_temperature = self.last_valid_temperature
        elif health != "ok":
            self._set_sensor_health(health, now, reason)
            # Continue with the last known valid temperature when one exists.
            if self.last_valid_temperature is None:
                self.average_temperature = None
                if self.running:
                    self.last_update = now
                await self._async_save_state()
                return self._data()
            self.average_temperature = self.last_valid_temperature
        else:
            self._set_sensor_health("ok", now)
            try:
                await self._async_update_average(now, current_value)
            except UpdateFailed as err:
                # Recorder/history can fail independently of the live sensor.
                # Use the last known value rather than creating a long gap.
                self._set_sensor_health("stale", now, "temperature_history_unavailable")
                if self.last_valid_temperature is None:
                    self.average_temperature = None
                    if self.running:
                        self.last_update = now
                    await self._async_save_state()
                    _LOGGER.warning("Modningsteller update skipped: %s", err)
                    return self._data()
                self.average_temperature = self.last_valid_temperature

        if accumulate and self.running and self.last_update is not None and self.average_temperature is not None:
            elapsed_seconds = max((now - self.last_update).total_seconds(), 0.0)
            self.active_seconds += elapsed_seconds
            self.degree_days += self._calculate_degree_days(
                self.average_temperature, elapsed_seconds
            )

            # The target is a notification threshold, not a stop condition.
            if self.degree_days >= self.target_degree_days and not self.reached_target:
                self.reached_target = True
                self.target_reached_at = now
                self._set_event("target_reached", now, {"degree_days": round(self.degree_days, 3)})
                if not self.target_notification_sent:
                    self.target_notification_sent = True
                    if self.on_target_reached is not None:
                        self.hass.async_create_task(self.on_target_reached())
            self.last_update = now

        if (
            self._temperature_window_start is not None
            and now - self._temperature_window_start
            >= timedelta(minutes=AVERAGE_WINDOW_MINUTES)
        ):
            self._temperature_window_start = None

        await self._async_save_state()
        return self._data()

    @staticmethod
    def _calculate_degree_days(temperature: float, elapsed_seconds: float) -> float:
        """Calculate degree-day contribution for a temperature interval.

        At temperatures below 0 °C, maturation is considered stopped and
        contributes no degree days. From 0 °C up to (but not including) 4 °C,
        the contribution follows the low-temperature formula. At 4 °C and
        above, the existing linear degree-day calculation is used.
        """
        elapsed_days = max(elapsed_seconds, 0.0) / 86400

        if temperature < 0:
            degree_day_factor = 0.0
        elif temperature < 4:
            degree_day_factor = 40 / (40 - 7.5 * temperature)
        else:
            degree_day_factor = temperature

        return degree_day_factor * elapsed_days

    def _data(self) -> dict[str, Any]:
        """Return the current coordinator data."""
        return {
            "degree_days": self.degree_days,
            "target_degree_days": self.target_degree_days,
            "remaining_degree_days": max(self.target_degree_days - self.degree_days, 0.0),
            "average_temperature": self.average_temperature,
            "temperature_entity": self.temperature_entity,
            "reached_target": self.reached_target,
            "target_reached_at": self.target_reached_at,
            "running": self.running,
            "stopped": self.stopped,
            "last_update": self.last_update,
            "run_started_at": self.run_started_at,
            "active_seconds": self._current_active_seconds(),
            "calibration_value": self.calibration_value,
            "calibration_comment": self.calibration_comment,
            "calibration_history": self.calibration_history,
            "temperature_change_history": self.temperature_change_history,
            "last_event": self.last_event,
            "last_event_at": self.last_event_at,
            "last_event_details": self.last_event_details,
            "note": self.note,
            "note_updated_at": self.note_updated_at,
            "note_history": self.note_history,
            "temperature_sensor_health": self.temperature_sensor_health,
            "last_valid_temperature": self.last_valid_temperature,
            "last_valid_temperature_at": self.last_valid_temperature_at,
            "last_temperature_age_seconds": self.last_temperature_age_seconds,
            "sensor_stale_minutes": self.sensor_stale_minutes,
            "sensor_stale_after_seconds": self.temperature_sensor_stale_after_seconds,
        }

    def _current_active_seconds(self) -> float:
        """Return elapsed active run time including the current active segment."""
        if not self.running or self.last_update is None:
            return max(self.active_seconds, 0.0)
        now = dt_util.utcnow()
        return max(
            self.active_seconds + max((now - self.last_update).total_seconds(), 0.0),
            0.0,
        )


    def _set_event(self, event_type: str, when: datetime, details: dict[str, Any] | None = None) -> None:
        """Record and publish a structured process event."""
        self.last_event = event_type
        self.last_event_at = when
        self.last_event_details = details or {}
        event_data = {
            "type": event_type,
            "entry_id": self.entry.entry_id,
            "name": self.entry.title,
            "timestamp": when.isoformat(),
            "degree_days": round(self.degree_days, 3),
            "target_degree_days": round(self.target_degree_days, 3),
            "remaining_degree_days": round(
                max(self.target_degree_days - self.degree_days, 0.0), 3
            ),
            "status": (
                "ready"
                if self.stopped
                else "paused"
                if not self.running
                else "target_reached"
                if self.reached_target
                else "running"
            ),
            "temperature_entity": self.temperature_entity,
            "average_temperature": self.average_temperature,
            "details": details or {},
        }
        self.hass.bus.async_fire(f"{DOMAIN}_event", event_data)

    async def async_change_temperature_entity(self, new_entity: str) -> None:
        """Switch temperature sensor without resetting the maturation run."""
        if new_entity == self.temperature_entity:
            return

        state = self.hass.states.get(new_entity)
        if state is None or (state.attributes.get("device_class") != "temperature" and new_entity != self.temperature_entity):
            raise ValueError("Selected entity is not a temperature sensor")

        now = dt_util.utcnow()
        old_entity = self.temperature_entity

        # Close the active interval with the old sensor before switching, so
        # time is not lost and old/new sensor history is never mixed.
        if self.running and self.last_update is not None and self.average_temperature is not None:
            elapsed_seconds = max((now - self.last_update).total_seconds(), 0.0)
            self.active_seconds += elapsed_seconds
            self.degree_days += self._calculate_degree_days(
                self.average_temperature, elapsed_seconds
            )
            if self.degree_days >= self.target_degree_days and not self.reached_target:
                self.reached_target = True
                self.target_reached_at = now
                self._set_event("target_reached", now, {"degree_days": round(self.degree_days, 3)})
                if not self.target_notification_sent:
                    self.target_notification_sent = True
                    if self.on_target_reached is not None:
                        self.hass.async_create_task(self.on_target_reached())

        previous_health = self.temperature_sensor_health

        self.temperature_entity = new_entity
        # Persist the dashboard selection in the config entry options so it
        # survives Home Assistant restarts and is shown in the options flow.
        options = dict(self.entry.options)
        options[CONF_TEMPERATURE_ENTITY] = new_entity
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self._temperature_window_start = now
        self.last_update = now
        self.average_temperature = None

        # Do not carry temperature data from the old sensor into the new one.
        # The new sensor gets a completely fresh health evaluation below.
        self.last_valid_temperature = None
        self.last_valid_temperature_at = None
        self.last_temperature_age_seconds = None

        # If the old sensor was unhealthy, move through unknown before checking
        # the new sensor. This guarantees that an unhealthy new sensor triggers
        # a fresh notification containing the new sensor name.
        if previous_health in {"unavailable", "stale"}:
            self._set_sensor_health("unknown", now, "temperature_sensor_changed")

        self._set_event(
            "temperature_sensor_changed",
            now,
            {
                "old_entity": old_entity,
                "new_entity": new_entity,
                "old_entity_name": self.hass.states.get(old_entity).name if self.hass.states.get(old_entity) else old_entity,
                "new_entity_name": self.hass.states.get(new_entity).name if self.hass.states.get(new_entity) else new_entity,
            },
        )
        self.temperature_change_history.append(
            {
                "timestamp": now.isoformat(),
                "old_entity": old_entity,
                "new_entity": new_entity,
            }
        )
        self.temperature_change_history = self.temperature_change_history[-20:]

        # Perform a complete status refresh from the new sensor immediately.
        # This does not accumulate any degree days or active time.
        await self._async_update_data_internal(accumulate=False)
        self.async_set_updated_data(self._data())

    async def async_set_note(self, value: str) -> None:
        """Store a note attached to this maturation counter."""
        now = dt_util.utcnow()
        note = value[:1000].strip()
        self.note = note
        self.note_updated_at = now if note else None
        if note:
            self.note_history.append({
                "timestamp": now.isoformat(),
                "note": note,
            })
            self.note_history = self.note_history[-20:]
            self._set_event("note_added", now, {"note": note})
        else:
            self._set_event("note_cleared", now)
        await self._async_save_state()
        self.async_set_updated_data(self._data())

    async def async_calibrate(self, new_value: float, comment: str = "") -> None:
        """Adjust the accumulated degree-day value without resetting the run."""
        try:
            value = float(new_value)
        except (TypeError, ValueError) as err:
            raise ValueError("Calibration value must be a number") from err

        if value < 0 or value > 10000:
            raise ValueError("Calibration value must be between 0 and 10000")

        now = dt_util.utcnow()
        old_value = self.degree_days
        old_reached = self.reached_target

        # Calibration changes only the accumulated degree-day value. It does
        # not alter the run start time or active elapsed time.
        self.degree_days = value
        self.calibration_value = round(value, 3)
        self.calibration_comment = comment[:255]

        new_reached = self.degree_days >= self.target_degree_days
        if new_reached and not old_reached:
            self.reached_target = True
            self.target_reached_at = now
            self._set_event("target_reached", now, {"degree_days": round(self.degree_days, 3), "via": "calibration"})
            self.target_notification_sent = True
            if self.on_target_reached is not None:
                self.hass.async_create_task(self.on_target_reached())
        elif not new_reached:
            self.reached_target = False
            self.target_reached_at = None
            self.target_notification_sent = False
            if old_reached and self.on_target_cleared is not None:
                self.on_target_cleared()
        else:
            self.reached_target = True

        self._set_event(
            "calibrated",
            now,
            {"old_degree_days": round(old_value, 3), "new_degree_days": round(value, 3), "delta_degree_days": round(value - old_value, 3), "comment": comment[:255]},
        )
        self.calibration_history.append(
            {
                "timestamp": now.isoformat(),
                "old_value": round(old_value, 3),
                "new_value": round(value, 3),
                "delta": round(value - old_value, 3),
                "comment": comment[:255],
            }
        )
        self.calibration_history = self.calibration_history[-20:]

        await self._async_save_state()
        self.async_set_updated_data(self._data())

    async def async_start(self) -> None:
        """Start or resume the counter. Pressing Start while running does nothing."""
        if self.running:
            return

        now = dt_util.utcnow()
        was_stopped = self.stopped
        self.running = True
        self.stopped = False
        self.last_update = now

        if was_stopped:
            # A reset creates a stopped, fresh run. Start establishes the
            # actual process start time and clears any active-time carryover.
            self.run_started_at = now
            self.active_seconds = 0.0
            self.target_notification_sent = False
            self.target_reached_at = None
            self.reached_target = False

            if self.degree_days >= self.target_degree_days:
                self.reached_target = True
                self.target_reached_at = now
                self._set_event(
                    "target_reached",
                    now,
                    {"degree_days": round(self.degree_days, 3), "via": "start"},
                )
                if not self.target_notification_sent:
                    self.target_notification_sent = True
                    if self.on_target_reached is not None:
                        self.hass.async_create_task(self.on_target_reached())

        self._set_event("started", now, {"resumed": not was_stopped})
        await self._async_save_state()
        self.async_set_updated_data(self._data())

    async def async_pause(self) -> None:
        """Pause the counter without changing accumulated degree days."""
        if not self.running:
            return
        now = dt_util.utcnow()
        if self.last_update is not None:
            self.active_seconds += max((now - self.last_update).total_seconds(), 0.0)
        self.running = False
        self.stopped = False
        self.last_update = now
        self._set_event("paused", now)
        await self._async_save_state()
        self.async_set_updated_data(self._data())

    async def async_reset(self) -> None:
        """Reset to the configured initial value and leave the counter ready."""
        now = dt_util.utcnow()
        self.degree_days = self.initial_degree_days
        # The previous run's "target reached" notification no longer applies.
        if self.on_target_cleared is not None:
            self.on_target_cleared()
        self.reached_target = False
        self.target_reached_at = None
        self.target_notification_sent = False
        self.running = False
        self.stopped = True
        self.run_started_at = None
        self.active_seconds = 0.0
        self.last_update = now
        self._temperature_window_start = None
        self.calibration_value = 0.0
        self.calibration_comment = ""
        self.note = ""
        self.note_updated_at = None
        self._set_event("reset", now, {"initial_degree_days": self.degree_days})

        # Refresh the rolling average immediately without accumulating time.
        try:
            await self._async_update_average(now)
        except UpdateFailed as err:
            _LOGGER.warning("Could not refresh average temperature after reset: %s", err)
            self.average_temperature = None

        await self._async_save_state()
        self.async_set_updated_data(self._data())

    async def _async_update_average(self, now: datetime, current_value: float | None = None) -> None:
        """Update the rolling one-hour average without accumulating degree days."""
        history_start = now - timedelta(minutes=AVERAGE_WINDOW_MINUTES)

        if self._temperature_window_start is not None:
            history_start = max(history_start, self._temperature_window_start)

        try:
            # Database access must run in the recorder's own executor.
            history_data = await get_instance(self.hass).async_add_executor_job(
                partial(
                    history.get_significant_states,
                    self.hass,
                    history_start,
                    now,
                    [self.temperature_entity],
                    include_start_time_state=True,
                    significant_changes_only=False,
                    no_attributes=True,
                )
            )
        except Exception as err:
            raise UpdateFailed(
                f"Could not retrieve temperature history for {self.temperature_entity}"
            ) from err

        samples: list[tuple[datetime, float | None]] = [
            (state.last_updated, self._valid_temperature(state.state))
            for state in history_data.get(self.temperature_entity, [])
        ]

        # The live state can be newer than what the recorder has written.
        live_state = self.hass.states.get(self.temperature_entity)
        if current_value is None and live_state is not None:
            current_value = self._valid_temperature(live_state.state)
        if current_value is not None:
            live_time = live_state.last_updated if live_state is not None else now
            samples.append((live_time, current_value))

        average = self._time_weighted_average(samples, history_start, now)
        if average is None:
            raise UpdateFailed(
                f"No valid temperature measurements available for {self.temperature_entity}"
            )

        self.average_temperature = average

    @staticmethod
    def _valid_temperature(raw_state: Any) -> float | None:
        """Return a temperature in a plausible range, or None."""
        try:
            value = float(raw_state)
        except (TypeError, ValueError):
            return None
        return value if -100 < value < 100 else None

    @staticmethod
    def _time_weighted_average(
        samples: list[tuple[datetime, float | None]],
        start: datetime,
        end: datetime,
    ) -> float | None:
        """Return the time-weighted average temperature between start and end.

        Each sample is valid from its timestamp until the next sample. A
        sensor that only reports on change would otherwise give too much
        weight to periods with many small changes. Periods where the sensor
        was unavailable (None) are left out. Falls back to a plain mean when
        the samples cover no time, for example a single reading at the end.
        """
        ordered = sorted(samples, key=lambda sample: sample[0])
        weighted_sum = 0.0
        total_seconds = 0.0
        for index, (timestamp, value) in enumerate(ordered):
            if value is None:
                continue
            segment_start = max(timestamp, start)
            segment_end = ordered[index + 1][0] if index + 1 < len(ordered) else end
            seconds = (min(segment_end, end) - segment_start).total_seconds()
            if seconds > 0:
                weighted_sum += value * seconds
                total_seconds += seconds

        if total_seconds > 0:
            return weighted_sum / total_seconds

        values = [value for _, value in ordered if value is not None]
        return sum(values) / len(values) if values else None

    async def _async_save_state(self) -> None:
        """Persist the accumulated state."""
        if self.last_update is None:
            return

        await self._store.async_save(
            {
                "degree_days": self.degree_days,
                "average_temperature": self.average_temperature,
                "last_update": self.last_update.isoformat(),
                "reached_target": self.reached_target,
                "running": self.running,
                "stopped": self.stopped,
                "temperature_entity": self.temperature_entity,
                "temperature_window_start": (
                    self._temperature_window_start.isoformat()
                    if self._temperature_window_start is not None
                    else None
                ),
                "target_notification_sent": self.target_notification_sent,
                "target_reached_at": (
                    self.target_reached_at.isoformat()
                    if self.target_reached_at is not None
                    else None
                ),
                "run_started_at": (
                    self.run_started_at.isoformat()
                    if self.run_started_at is not None
                    else None
                ),
                "active_seconds": self._current_active_seconds(),
                "calibration_value": self.calibration_value,
                "calibration_comment": self.calibration_comment,
                "calibration_history": self.calibration_history[-20:],
                "temperature_change_history": self.temperature_change_history[-20:],
                "last_event": self.last_event,
                "last_event_at": (self.last_event_at.isoformat() if self.last_event_at is not None else None),
                "last_event_details": self.last_event_details,
                "note": self.note,
                "note_updated_at": (
                    self.note_updated_at.isoformat() if self.note_updated_at is not None else None
                ),
                "note_history": self.note_history[-20:],
                "temperature_sensor_health": self.temperature_sensor_health,
                "last_valid_temperature": self.last_valid_temperature,
                "last_valid_temperature_at": (
                    self.last_valid_temperature_at.isoformat()
                    if self.last_valid_temperature_at is not None
                    else None
                ),
            }
        )

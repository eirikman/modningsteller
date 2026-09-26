"""Sensors for Modningsteller."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import ModningstellerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Modningsteller sensors."""
    coordinator: ModningstellerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DegreeDaySensor(coordinator),
            AverageTemperatureSensor(coordinator),
            StatusSensor(coordinator),
            ExpectedFinishSensor(coordinator),
            RemainingDegreeDaysSensor(coordinator),
            StartTimeSensor(coordinator),
            TargetReachedTimeSensor(coordinator),
            ElapsedTimeSensor(coordinator),
            LastEventSensor(coordinator),
            TemperatureSensorHealthSensor(coordinator),
            LastValidTemperatureTimeSensor(coordinator),
        ]
    )


class BaseModningstellerSensor(CoordinatorEntity[ModningstellerCoordinator], SensorEntity):
    """Base sensor for Modningsteller."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ModningstellerCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Modningsteller",
            model="Modningsteller",
        )


class DegreeDaySensor(BaseModningstellerSensor):
    """Accumulated degree days."""

    _attr_translation_key = "degree_days"
    _attr_icon = "mdi:bird"
    _attr_native_unit_of_measurement = "°C·d"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "degree_days")

    @property
    def native_value(self) -> float:
        return round(self.coordinator.degree_days, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "target_degree_days": self.coordinator.target_degree_days,
            "temperature_entity": self.coordinator.temperature_entity,
            "average_temperature_last_hour": self.coordinator.average_temperature,
            "last_updated": self.coordinator.last_update,
            "target_reached": self.coordinator.reached_target,
            "target_reached_at": self.coordinator.target_reached_at,
            "start_time": self.coordinator.run_started_at,
            "elapsed_active_time": self.coordinator._current_active_seconds(),
            "remaining_degree_days": self.coordinator._data()["remaining_degree_days"],
            "last_calibrations": self.coordinator.calibration_history[-5:],
            "last_sensor_changes": self.coordinator.temperature_change_history[-5:],
            "note": self.coordinator.note,
            "note_updated_at": self.coordinator.note_updated_at,
            "last_notes": self.coordinator.note_history[-5:],
        }


class AverageTemperatureSensor(BaseModningstellerSensor):
    """Rolling one-hour average temperature."""

    _attr_translation_key = "average_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "average_temperature")

    @property
    def native_value(self) -> float | None:
        if self.coordinator.average_temperature is None:
            return None
        return round(self.coordinator.average_temperature, 2)


class RemainingDegreeDaysSensor(BaseModningstellerSensor):
    """Degree days remaining until the configured target."""

    _attr_translation_key = "remaining_degree_days"
    _attr_icon = "mdi:paw"
    _attr_native_unit_of_measurement = "°C·d"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "remaining_degree_days")

    @property
    def native_value(self) -> float:
        return round(max(self.coordinator.target_degree_days - self.coordinator.degree_days, 0.0), 3)


class StartTimeSensor(BaseModningstellerSensor):
    """Start time of the current maturation run."""

    _attr_translation_key = "start_time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "start_time")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.run_started_at


class TargetReachedTimeSensor(BaseModningstellerSensor):
    """Time when the target was first reached in the current run."""

    _attr_translation_key = "target_reached_time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "target_reached_time")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.target_reached_at


class ElapsedTimeSensor(BaseModningstellerSensor):
    """Active elapsed time for the current maturation run."""

    _attr_translation_key = "elapsed_time"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT


    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "elapsed_time")

    async def async_added_to_hass(self) -> None:
        """Refresh the elapsed-time display once per minute.

        The degree-day calculation keeps its configured update interval, while
        this display-only entity is refreshed independently so it does not lag
        behind the start timestamp for up to the configured interval.
        """
        await super().async_added_to_hass()
        from homeassistant.helpers.event import async_track_time_interval

        self._cancel_elapsed_refresh = async_track_time_interval(
            self.hass, self._async_refresh_elapsed, timedelta(minutes=1)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the independent elapsed-time refresh."""
        cancel = getattr(self, "_cancel_elapsed_refresh", None)
        if cancel is not None:
            cancel()
        await super().async_will_remove_from_hass()

    @callback
    def _async_refresh_elapsed(self, _now: datetime) -> None:
        """Refresh the elapsed-time state without running the calculation."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        return round(self.coordinator._current_active_seconds() / 86400, 4)


class ExpectedFinishSensor(BaseModningstellerSensor):
    """Estimated time when the target degree days will be reached."""

    _attr_translation_key = "expected_finish"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "expected_finish")

    @property
    def native_value(self) -> datetime | None:
        if not self.coordinator.running:
            return None

        if self.coordinator.reached_target:
            return self.coordinator.target_reached_at

        average_temperature = self.coordinator.average_temperature
        if average_temperature is None or average_temperature <= 0:
            return None

        remaining_degree_days = max(
            self.coordinator.target_degree_days - self.coordinator.degree_days, 0.0
        )
        if remaining_degree_days <= 0:
            return self.coordinator.target_reached_at

        now = dt_util.now()
        days_remaining = remaining_degree_days / average_temperature
        return now + timedelta(days=days_remaining)


class StatusSensor(BaseModningstellerSensor):
    """Current counter status."""

    _attr_translation_key = "status"
    _attr_icon = "mdi:list-status"

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "status")

    @property
    def native_value(self) -> str:
        if self.coordinator.stopped:
            return "stopped"
        if not self.coordinator.running:
            return "paused"
        if self.coordinator.reached_target:
            return "target_reached"
        return "running"


class LastEventSensor(BaseModningstellerSensor):
    """Latest maturation process event."""

    _attr_translation_key = "last_event"
    _attr_icon = "mdi:timeline-clock-outline"

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "last_event")

    @property
    def native_value(self) -> str:
        return self.coordinator.last_event

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "timestamp": self.coordinator.last_event_at,
            "details": self.coordinator.last_event_details,
        }


class TemperatureSensorHealthSensor(BaseModningstellerSensor):
    """Health of the selected temperature sensor."""

    _attr_translation_key = "temperature_sensor_health"

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "temperature_sensor_health")

    @property
    def native_value(self) -> str:
        return self.coordinator.temperature_sensor_health

    @property
    def icon(self) -> str:
        return {
            "ok": "mdi:thermometer-check",
            "stale": "mdi:thermometer-alert",
            "unavailable": "mdi:thermometer-off",
        }.get(self.coordinator.temperature_sensor_health, "mdi:thermometer")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "temperature_entity": self.coordinator.temperature_entity,
            "last_valid_temperature": self.coordinator.last_valid_temperature,
            "last_valid_temperature_at": self.coordinator.last_valid_temperature_at,
            "last_temperature_age_seconds": self.coordinator.last_temperature_age_seconds,
            "sensor_stale_after_seconds": self.coordinator.temperature_sensor_stale_after_seconds,
        }


class LastValidTemperatureTimeSensor(BaseModningstellerSensor):
    """Timestamp of the last valid live temperature reading."""

    _attr_translation_key = "last_valid_temperature_time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "last_valid_temperature_time")

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_valid_temperature_at

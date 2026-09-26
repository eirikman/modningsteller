"""Tests for Modningsteller sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant.util import dt as dt_util

from custom_components.modningsteller.sensor import (
    DegreeDaySensor,
    LastEventSensor,
    TemperatureSensorHealthSensor,
)


def test_device_model_and_degree_day_attribute_names(coordinator) -> None:
    """Use English, stable names for device metadata and state attributes."""
    now = dt_util.utcnow()
    coordinator.last_update = now
    coordinator.run_started_at = now
    coordinator.target_reached_at = now
    coordinator.average_temperature = 4.5
    coordinator.reached_target = True
    coordinator.active_seconds = 3600
    coordinator.calibration_history = [{"timestamp": now.isoformat()}]
    coordinator.temperature_change_history = [{"timestamp": now.isoformat()}]
    coordinator.note = "Test note"
    coordinator.note_updated_at = now
    coordinator.note_history = [{"timestamp": now.isoformat(), "note": "Test note"}]

    sensor = DegreeDaySensor(coordinator)
    attributes = sensor.extra_state_attributes

    assert sensor.device_info["model"] == "Modningsteller"
    assert set(attributes) == {
        "target_degree_days",
        "temperature_entity",
        "average_temperature_last_hour",
        "last_updated",
        "target_reached",
        "target_reached_at",
        "start_time",
        "elapsed_active_time",
        "remaining_degree_days",
        "last_calibrations",
        "last_sensor_changes",
        "note",
        "note_updated_at",
        "last_notes",
    }


def test_last_event_attribute_names(coordinator) -> None:
    """Use English names for last-event attributes."""
    coordinator.last_event_at = datetime(2026, 9, 20, 10, 0, 0)
    coordinator.last_event_details = {"reason": "test"}

    sensor = LastEventSensor(coordinator)

    assert set(sensor.extra_state_attributes) == {"timestamp", "details"}


def test_temperature_health_attribute_names(coordinator) -> None:
    """Use English names for temperature-health attributes."""
    coordinator.last_valid_temperature = 5.5
    coordinator.last_valid_temperature_at = datetime(2026, 9, 20, 10, 0, 0)
    coordinator.last_temperature_age_seconds = 120.0

    sensor = TemperatureSensorHealthSensor(coordinator)

    assert set(sensor.extra_state_attributes) == {
        "temperature_entity",
        "last_valid_temperature",
        "last_valid_temperature_at",
        "last_temperature_age_seconds",
        "sensor_stale_after_seconds",
    }

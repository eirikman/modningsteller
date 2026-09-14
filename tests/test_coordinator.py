"""Tests for the Modningsteller coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.modningsteller.const import CONF_TEMPERATURE_ENTITY


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_degree_days_accumulate_from_elapsed_time(
    hass: HomeAssistant, coordinator, freezer
) -> None:
    """4 C for one day should add 4 degree days."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    hass.states.async_set(
        "sensor.test_temperature",
        "4.0",
        {"device_class": "temperature"},
    )
    coordinator.last_update = dt_util.utcnow() - timedelta(days=1)
    coordinator.average_temperature = 4.0
    coordinator._async_update_average = AsyncMock()

    await coordinator._async_update_data()

    assert coordinator.degree_days == pytest.approx(4.0)
    assert coordinator.active_seconds == pytest.approx(86400.0)


async def test_start_while_running_does_nothing(coordinator, freezer) -> None:
    """Pressing Start while running must not restart the process clock."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    started_at = dt_util.utcnow() - timedelta(hours=5)
    coordinator.running = True
    coordinator.stopped = False
    coordinator.run_started_at = started_at
    coordinator.last_update = started_at
    coordinator.active_seconds = 1234.0
    coordinator.degree_days = 12.5

    await coordinator.async_start()

    assert coordinator.running is True
    assert coordinator.stopped is False
    assert coordinator.run_started_at == started_at
    assert coordinator.active_seconds == pytest.approx(1234.0)
    assert coordinator.degree_days == pytest.approx(12.5)


async def test_pause_stops_active_time_and_resume_continues(
    coordinator, freezer
) -> None:
    """Pause freezes active time; Start resumes without resetting it."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    coordinator.running = True
    coordinator.stopped = False
    coordinator.last_update = dt_util.utcnow() - timedelta(minutes=10)
    coordinator.active_seconds = 100.0

    await coordinator.async_pause()

    assert coordinator.running is False
    assert coordinator.stopped is False
    assert coordinator.active_seconds == pytest.approx(700.0)

    pause_time = dt_util.utcnow()
    freezer.tick(delta=timedelta(minutes=30))
    await coordinator.async_start()

    assert coordinator.running is True
    assert coordinator.stopped is False
    assert coordinator.active_seconds == pytest.approx(700.0)
    assert coordinator.last_update == dt_util.utcnow()
    assert coordinator.run_started_at != pause_time


async def test_reset_stops_counter_and_next_start_creates_new_run(
    coordinator, freezer
) -> None:
    """Reset returns to the preset and leaves the counter stopped."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    coordinator.degree_days = 17.5
    coordinator.running = True
    coordinator.stopped = False
    coordinator.run_started_at = dt_util.utcnow() - timedelta(hours=4)
    coordinator.active_seconds = 12345.0
    coordinator._async_update_average = AsyncMock()

    await coordinator.async_reset()

    assert coordinator.degree_days == pytest.approx(0.0)
    assert coordinator.running is False
    assert coordinator.stopped is True
    assert coordinator.run_started_at is None
    assert coordinator.active_seconds == pytest.approx(0.0)

    freezer.tick(delta=timedelta(minutes=5))
    await coordinator.async_start()

    assert coordinator.running is True
    assert coordinator.stopped is False
    assert coordinator.run_started_at == dt_util.utcnow()
    assert coordinator.active_seconds == pytest.approx(0.0)


async def test_calibration_changes_degree_days_without_resetting_timing(
    coordinator, freezer
) -> None:
    """Calibration changes degree days but preserves process timing."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    started_at = dt_util.utcnow() - timedelta(hours=6)
    coordinator.run_started_at = started_at
    coordinator.active_seconds = 1234.0
    coordinator.degree_days = 12.5

    await coordinator.async_calibrate(18.75, "Moved to another refrigerator")

    assert coordinator.degree_days == pytest.approx(18.75)
    assert coordinator.run_started_at == started_at
    assert coordinator.active_seconds == pytest.approx(1234.0)
    assert coordinator.calibration_comment == "Moved to another refrigerator"
    assert coordinator.calibration_history[-1]["old_value"] == pytest.approx(12.5)
    assert coordinator.calibration_history[-1]["new_value"] == pytest.approx(18.75)


async def test_target_reached_notifies_once_and_counter_continues(
    hass: HomeAssistant, coordinator, freezer
) -> None:
    """Reaching the target fires once, but accumulation continues."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    coordinator.target_degree_days = 1.0
    coordinator.last_update = dt_util.utcnow() - timedelta(hours=6)
    coordinator.average_temperature = 4.0
    hass.states.async_set(
        "sensor.test_temperature",
        "4.0",
        {"device_class": "temperature"},
    )
    coordinator._async_update_average = AsyncMock()
    target_callback = AsyncMock()
    coordinator.on_target_reached = target_callback

    await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert coordinator.degree_days == pytest.approx(1.0)
    assert coordinator.reached_target is True
    assert coordinator.target_reached_at is not None
    assert target_callback.await_count == 1

    coordinator.last_update = dt_util.utcnow() - timedelta(hours=6)
    await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert coordinator.degree_days == pytest.approx(2.0)
    assert target_callback.await_count == 1


async def test_stale_temperature_sensor_stops_accumulation(
    hass: HomeAssistant, coordinator, freezer
) -> None:
    """A stale temperature reading must prevent degree-day accumulation."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    old_timestamp = dt_util.utcnow() - timedelta(hours=3)
    hass.states.async_set(
        "sensor.test_temperature",
        "4.0",
        {"device_class": "temperature"},
        timestamp=old_timestamp,
    )
    coordinator.degree_days = 5.0
    coordinator.last_update = dt_util.utcnow() - timedelta(hours=1)

    await coordinator._async_update_data()

    assert coordinator.temperature_sensor_health == "stale"
    assert coordinator.degree_days == pytest.approx(5.0)
    assert coordinator.average_temperature is None


async def test_temperature_sensor_change_preserves_value_and_history(
    hass: HomeAssistant, coordinator, freezer
) -> None:
    """Changing sensors preserves accumulated degree days and logs the change."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    hass.states.async_set(
        "sensor.other_temperature",
        "5.0",
        {"device_class": "temperature"},
    )
    coordinator.degree_days = 12.5
    coordinator.running = True
    coordinator.last_update = dt_util.utcnow()
    coordinator.average_temperature = 4.0
    coordinator._async_update_average = AsyncMock()

    await coordinator.async_change_temperature_entity("sensor.other_temperature")

    assert coordinator.degree_days == pytest.approx(12.5)
    assert coordinator.temperature_entity == "sensor.other_temperature"
    assert coordinator.average_temperature is None
    assert coordinator.temperature_change_history[-1]["old_entity"] == "sensor.test_temperature"
    assert coordinator.temperature_change_history[-1]["new_entity"] == "sensor.other_temperature"


async def test_note_is_stored_and_added_to_history(coordinator, freezer) -> None:
    """A maturation note is stored and kept in note history."""
    freezer.move_to("2026-09-14 12:00:00+00:00")

    await coordinator.async_set_note("Left hind leg, moved to garage fridge")

    assert coordinator.note == "Left hind leg, moved to garage fridge"
    assert coordinator.note_updated_at == dt_util.utcnow()
    assert coordinator.note_history[-1]["note"] == "Left hind leg, moved to garage fridge"
    assert coordinator.last_event == "note_added"


async def test_reset_uses_configured_initial_value_and_clears_run_state(
    coordinator, freezer
) -> None:
    """Reset returns to the configured initial value and clears run state."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    coordinator.initial_degree_days = 7.5
    coordinator.degree_days = 24.0
    coordinator.running = True
    coordinator.stopped = False
    coordinator.reached_target = True
    coordinator.target_notification_sent = True
    coordinator.target_reached_at = dt_util.utcnow()
    coordinator.active_seconds = 12345.0
    coordinator.run_started_at = dt_util.utcnow() - timedelta(hours=3)

    coordinator._async_update_average = AsyncMock()

    await coordinator.async_reset()

    assert coordinator.degree_days == pytest.approx(7.5)
    assert coordinator.running is False
    assert coordinator.stopped is True
    assert coordinator.reached_target is False
    assert coordinator.target_notification_sent is False
    assert coordinator.target_reached_at is None
    assert coordinator.run_started_at is None
    assert coordinator.active_seconds == pytest.approx(0.0)


async def test_pause_after_target_sets_paused_state_but_keeps_target_reached(
    coordinator, freezer
) -> None:
    """Pausing after target keeps target information without staying 'running'."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    coordinator.running = True
    coordinator.stopped = False
    coordinator.reached_target = True
    coordinator.degree_days = 42.0
    coordinator.last_update = dt_util.utcnow() - timedelta(minutes=10)

    await coordinator.async_pause()

    assert coordinator.running is False
    assert coordinator.stopped is False
    assert coordinator.reached_target is True
    assert coordinator.degree_days == pytest.approx(42.0)


async def test_target_reached_event_contains_running_target_status(
    hass: HomeAssistant, coordinator, freezer
) -> None:
    """Target reached emits the structured integration event with target status."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    coordinator.target_degree_days = 1.0
    coordinator.last_update = dt_util.utcnow() - timedelta(hours=6)
    coordinator.average_temperature = 4.0
    coordinator._async_update_average = AsyncMock()
    hass.states.async_set(
        "sensor.test_temperature",
        "4.0",
        {"device_class": "temperature"},
    )

    captured: list = []
    hass.bus.async_listen_once(
        "modningsteller_event",
        lambda event: captured.append(event),
    )

    await coordinator._async_update_data()
    await hass.async_block_till_done()

    assert captured
    event_data = captured[0].data
    assert event_data["type"] == "target_reached"
    assert event_data["status"] == "target_reached"
    assert event_data["degree_days"] == pytest.approx(1.0)


async def test_unavailable_temperature_sensor_does_not_accumulate(
    hass: HomeAssistant, coordinator, freezer
) -> None:
    """An unavailable temperature sensor must not add degree days."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    coordinator.degree_days = 8.0
    coordinator.average_temperature = 5.0
    coordinator.last_update = dt_util.utcnow() - timedelta(hours=2)
    hass.states.async_set(
        "sensor.test_temperature",
        "unavailable",
        {"device_class": "temperature"},
    )

    await coordinator._async_update_data()

    assert coordinator.temperature_sensor_health == "unavailable"
    assert coordinator.degree_days == pytest.approx(8.0)
    assert coordinator.average_temperature is None


async def test_sensor_health_callback_fires_when_health_changes(
    hass: HomeAssistant, coordinator, freezer
) -> None:
    """Sensor health changes invoke the configured callback once per transition."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    callback = AsyncMock()
    coordinator.on_sensor_health_changed = callback

    coordinator._set_sensor_health("ok", dt_util.utcnow())
    await hass.async_block_till_done()
    assert callback.await_count == 1
    assert callback.await_args.args[:2] == ("unknown", "ok")

    coordinator._set_sensor_health("ok", dt_util.utcnow())
    await hass.async_block_till_done()
    assert callback.await_count == 1

    coordinator._set_sensor_health("stale", dt_util.utcnow(), "reading_too_old")
    await hass.async_block_till_done()
    assert callback.await_count == 2
    assert callback.await_args.args[:2] == ("ok", "stale")


async def test_temperature_sensor_change_closes_old_interval_before_switch(
    hass: HomeAssistant, coordinator, freezer
) -> None:
    """Sensor changes preserve the old interval before starting a fresh window."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    hass.states.async_set(
        "sensor.other_temperature",
        "5.0",
        {"device_class": "temperature"},
    )
    coordinator.degree_days = 10.0
    coordinator.running = True
    coordinator.stopped = False
    coordinator.last_update = dt_util.utcnow() - timedelta(hours=1)
    coordinator.active_seconds = 0.0
    coordinator.average_temperature = 4.0

    coordinator._async_update_average = AsyncMock()

    await coordinator.async_change_temperature_entity("sensor.other_temperature")

    assert coordinator.degree_days == pytest.approx(10.0 + 4.0 / 24.0)
    assert coordinator.active_seconds == pytest.approx(3600.0)
    assert coordinator.temperature_entity == "sensor.other_temperature"
    assert coordinator.average_temperature is None
    assert coordinator._temperature_window_start is not None
    assert (dt_util.utcnow() - coordinator._temperature_window_start).total_seconds() < 1


async def test_calibration_crossing_target_notifies_once(
    coordinator, freezer
) -> None:
    """Calibration across the target triggers the target notification once."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    coordinator.degree_days = 39.0
    coordinator.target_degree_days = 40.0
    coordinator.running = True
    callback = AsyncMock()
    coordinator.on_target_reached = callback

    await coordinator.async_calibrate(41.5, "External measurement")
    await coordinator.hass.async_block_till_done()

    assert coordinator.degree_days == pytest.approx(41.5)
    assert coordinator.reached_target is True
    assert coordinator.target_reached_at is not None
    assert coordinator.target_notification_sent is True
    assert callback.await_count == 1

    await coordinator.async_calibrate(42.0, "Correction")
    await coordinator.hass.async_block_till_done()
    assert callback.await_count == 1


async def test_calibration_below_target_clears_target_reached_state(
    coordinator, freezer
) -> None:
    """Calibration below the target clears the target-reached state."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    coordinator.degree_days = 45.0
    coordinator.target_degree_days = 40.0
    coordinator.reached_target = True
    coordinator.target_notification_sent = True
    coordinator.target_reached_at = dt_util.utcnow() - timedelta(hours=1)

    await coordinator.async_calibrate(35.0, "Correction")

    assert coordinator.reached_target is False
    assert coordinator.target_notification_sent is False
    assert coordinator.target_reached_at is None


async def test_note_can_be_cleared_and_records_event(coordinator, freezer) -> None:
    """Clearing the note removes it and publishes a note_cleared event."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    await coordinator.async_set_note("Test note")
    await coordinator.async_set_note("")

    assert coordinator.note == ""
    assert coordinator.note_updated_at is None
    assert coordinator.last_event == "note_cleared"
    assert coordinator.note_history[-1]["note"] == "Test note"


async def test_state_restores_running_values_from_store(hass: HomeAssistant, modning_entry, freezer) -> None:
    """Persisted process state is restored after a coordinator is recreated."""
    freezer.move_to("2026-09-14 12:00:00+00:00")
    from custom_components.modningsteller.coordinator import ModningstellerCoordinator

    stored_started = dt_util.utcnow() - timedelta(hours=4)
    stored = {
        "degree_days": 23.5,
        "average_temperature": 4.25,
        "running": True,
        "stopped": False,
        "temperature_entity": "sensor.test_temperature",
        "active_seconds": 12345.0,
        "run_started_at": stored_started.isoformat(),
        "last_event": "started",
        "target_reached_at": None,
        "target_notification_sent": False,
        "temperature_sensor_health": "ok",
        "note": "Restored note",
    }

    coordinator = ModningstellerCoordinator(hass, modning_entry)
    coordinator._store.async_load = AsyncMock(return_value=stored)
    coordinator._store.async_save = AsyncMock()

    await coordinator._async_setup()

    assert coordinator.degree_days == pytest.approx(23.5)
    assert coordinator.average_temperature == pytest.approx(4.25)
    assert coordinator.running is True
    assert coordinator.stopped is False
    assert coordinator.active_seconds == pytest.approx(12345.0)
    assert coordinator.run_started_at == stored_started
    assert coordinator.note == "Restored note"
    assert coordinator.last_update == dt_util.utcnow()

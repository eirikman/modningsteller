"""Tests for the rolling one-hour average temperature."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from custom_components.modningsteller.coordinator import ModningstellerCoordinator

START = datetime(2026, 9, 14, 11, 0, 0, tzinfo=dt_util.UTC)
END = START + timedelta(hours=1)


def _at(minutes: float) -> datetime:
    return START + timedelta(minutes=minutes)


def test_time_weighted_average_ignores_how_often_the_sensor_reports() -> None:
    """50 minutes at 3 C and 10 busy minutes around 6 C average about 3.5 C."""
    samples = [(_at(0), 3.0)] + [
        (_at(50 + minute), 6.0 + (0.2 if minute % 2 else -0.2))
        for minute in range(10)
    ]

    average = ModningstellerCoordinator._time_weighted_average(samples, START, END)

    assert average == pytest.approx(3.5, abs=0.05)


def test_time_weighted_average_leaves_out_unavailable_periods() -> None:
    """Periods where the sensor was unavailable do not count."""
    samples = [(_at(0), 2.0), (_at(30), None), (_at(45), 6.0)]

    average = ModningstellerCoordinator._time_weighted_average(samples, START, END)

    # 30 minutes at 2 C and 15 minutes at 6 C.
    assert average == pytest.approx((2.0 * 30 + 6.0 * 15) / 45)


def test_time_weighted_average_clamps_samples_from_before_the_window() -> None:
    """A reading from before the window only counts from the window start."""
    samples = [(START - timedelta(hours=3), 10.0), (_at(30), 4.0)]

    average = ModningstellerCoordinator._time_weighted_average(samples, START, END)

    assert average == pytest.approx(7.0)


def test_time_weighted_average_falls_back_to_plain_mean_without_duration() -> None:
    """A single reading at the end of the window is still used."""
    average = ModningstellerCoordinator._time_weighted_average(
        [(END, 5.0)], START, END
    )

    assert average == pytest.approx(5.0)


def test_time_weighted_average_without_valid_values_is_none() -> None:
    """No valid readings gives no average."""
    assert ModningstellerCoordinator._time_weighted_average([], START, END) is None
    assert (
        ModningstellerCoordinator._time_weighted_average(
            [(_at(0), None)], START, END
        )
        is None
    )


async def test_update_average_reads_history_in_recorder_executor(
    hass: HomeAssistant, coordinator, freezer
) -> None:
    """History is read through the recorder executor and time weighted."""
    freezer.move_to(END)
    history = {
        "sensor.test_temperature": [
            State("sensor.test_temperature", "3.0", last_updated=_at(0)),
            State("sensor.test_temperature", "unavailable", last_updated=_at(30)),
            State("sensor.test_temperature", "5.0", last_updated=_at(40)),
        ]
    }
    hass.states.async_set("sensor.test_temperature", "5.0")
    recorder = MagicMock()
    recorder.async_add_executor_job = AsyncMock(return_value=history)

    with patch(
        "custom_components.modningsteller.coordinator.get_instance",
        return_value=recorder,
    ):
        await coordinator._async_update_average(dt_util.utcnow())

    recorder.async_add_executor_job.assert_awaited_once()
    # 30 minutes at 3 C and 20 minutes at 5 C; the live state adds no time.
    assert coordinator.average_temperature == pytest.approx(
        (3.0 * 30 + 5.0 * 20) / 50
    )

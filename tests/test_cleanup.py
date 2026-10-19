"""Tests for clean-up of notifications and stored state."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import modningsteller
from custom_components.modningsteller.const import STORAGE_KEY_PREFIX


async def test_remove_entry_deletes_stored_state_and_notifications(
    hass: HomeAssistant, modning_entry: MockConfigEntry, hass_storage
) -> None:
    """Deleting a counter removes its storage file and notifications."""
    key = f"{STORAGE_KEY_PREFIX}_{modning_entry.entry_id}"
    hass_storage[key] = {"version": 1, "key": key, "data": {"degree_days": 12.0}}

    with patch.object(modningsteller, "async_dismiss") as dismiss:
        await modningsteller.async_remove_entry(hass, modning_entry)

    assert key not in hass_storage
    dismissed = {call.args[1] for call in dismiss.call_args_list}
    assert dismissed == {
        f"modningsteller_{modning_entry.entry_id}_target",
        f"modningsteller_{modning_entry.entry_id}_sensor_health",
    }


async def test_reset_clears_target_notification(coordinator) -> None:
    """Reset removes the previous run's target notification."""
    coordinator.on_target_cleared = MagicMock()
    coordinator._async_update_average = AsyncMock()

    await coordinator.async_reset()

    coordinator.on_target_cleared.assert_called_once()


async def test_calibration_below_reached_target_clears_notification(
    coordinator,
) -> None:
    """Calibrating below a reached target removes its notification."""
    coordinator.on_target_cleared = MagicMock()
    coordinator.degree_days = 45.0
    coordinator.reached_target = True

    await coordinator.async_calibrate(30.0)

    coordinator.on_target_cleared.assert_called_once()


async def test_calibration_below_unreached_target_keeps_notifications(
    coordinator,
) -> None:
    """Calibrating while the target is not reached does not dismiss anything."""
    coordinator.on_target_cleared = MagicMock()
    coordinator.degree_days = 10.0

    await coordinator.async_calibrate(20.0)

    coordinator.on_target_cleared.assert_not_called()

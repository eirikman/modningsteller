"""Tests for Modningsteller persistent notifications."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.modningsteller import (
    _async_sensor_health_changed,
    _sensor_health_notification_id,
)
from custom_components.modningsteller.const import DOMAIN


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_sensor_health_notification_created_for_stale_sensor(
    hass: HomeAssistant, coordinator, modning_entry
) -> None:
    """A transition to stale creates a persistent notification."""
    hass.data.setdefault(DOMAIN, {})[modning_entry.entry_id] = coordinator

    with (
        patch(
            "custom_components.modningsteller._async_sensor_health_notification_text",
            new=AsyncMock(return_value=("Temperature sensor is stale", "Sensor warning")),
        ),
        patch("custom_components.modningsteller.async_create") as async_create,
    ):
        await _async_sensor_health_changed(
            hass,
            modning_entry,
            "ok",
            "stale",
            "reading_too_old",
        )

    async_create.assert_called_once_with(
        hass,
        "Sensor warning",
        title="Temperature sensor is stale",
        notification_id=_sensor_health_notification_id(modning_entry),
    )

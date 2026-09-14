"""Shared pytest fixtures for Modningsteller tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modningsteller.const import (
    CONF_INITIAL_DEGREE_DAYS,
    CONF_TARGET_DEGREE_DAYS,
    CONF_TEMPERATURE_ENTITY,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from custom_components.modningsteller.coordinator import ModningstellerCoordinator


@pytest.fixture
def modning_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry suitable for coordinator tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test maturation",
        data={
            CONF_INITIAL_DEGREE_DAYS: 0.0,
            CONF_TARGET_DEGREE_DAYS: 40.0,
            CONF_TEMPERATURE_ENTITY: "sensor.test_temperature",
            CONF_UPDATE_INTERVAL: 10,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, modning_entry: MockConfigEntry
) -> AsyncGenerator[ModningstellerCoordinator, None]:
    """Return a coordinator with persistence and UI callbacks mocked."""
    coordinator = ModningstellerCoordinator(hass, modning_entry)
    coordinator._store.async_load = AsyncMock(return_value=None)
    coordinator._store.async_save = AsyncMock()
    coordinator.async_set_updated_data = MagicMock()
    yield coordinator
    await hass.async_block_till_done()

"""Tests for setting up and unloading the whole integration."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modningsteller.const import (
    CONF_INITIAL_DEGREE_DAYS,
    CONF_SENSOR_STALE_MINUTES,
    CONF_TARGET_DEGREE_DAYS,
    CONF_TEMPERATURE_ENTITY,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)


@pytest.mark.usefixtures("recorder_mock", "enable_custom_integrations")
async def test_setup_and_unload_with_recorder(hass: HomeAssistant) -> None:
    """The integration loads with a real recorder, creates entities and unloads."""
    hass.states.async_set(
        "sensor.test_temperature", "4.0", {"device_class": "temperature"}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Rype",
        data={
            "name": "Rype",
            CONF_TEMPERATURE_ENTITY: "sensor.test_temperature",
            CONF_INITIAL_DEGREE_DAYS: 0.0,
            CONF_TARGET_DEGREE_DAYS: 40.0,
            CONF_UPDATE_INTERVAL: 10,
            CONF_SENSOR_STALE_MINUTES: 120,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    unique_ids = {
        registry_entry.unique_id
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }
    assert f"{entry.entry_id}_degree_days" in unique_ids
    assert f"{entry.entry_id}_temperature_sensor" in unique_ids

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED

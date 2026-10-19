"""Tests for changing settings in the options flow ("Configure")."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modningsteller.const import (
    CONF_INITIAL_DEGREE_DAYS,
    CONF_SENSOR_STALE_MINUTES,
    CONF_TARGET_DEGREE_DAYS,
    CONF_TEMPERATURE_ENTITY,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)

OPTIONS = {
    CONF_TEMPERATURE_ENTITY: "sensor.test_temperature",
    CONF_INITIAL_DEGREE_DAYS: 0.0,
    CONF_TARGET_DEGREE_DAYS: 40.0,
    CONF_UPDATE_INTERVAL: 10,
    CONF_SENSOR_STALE_MINUTES: 120,
}


@pytest.fixture
async def loaded_entry(
    recorder_mock, hass: HomeAssistant, enable_custom_integrations
) -> MockConfigEntry:
    """Set up a running counter with a real recorder."""
    for entity_id in ("sensor.test_temperature", "sensor.other_temperature"):
        hass.states.async_set(entity_id, "4.0", {"device_class": "temperature"})
    entry = MockConfigEntry(
        domain=DOMAIN, title="Rype", data={"name": "Rype", **OPTIONS}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


def _coordinator(hass: HomeAssistant, entry: MockConfigEntry):
    return hass.data[DOMAIN][entry.entry_id]


def _rewind(hass: HomeAssistant, entry: MockConfigEntry, minutes: int) -> float:
    """Pretend the last update was some minutes ago at 4 C."""
    coordinator = _coordinator(hass, entry)
    coordinator.average_temperature = 4.0
    coordinator.last_update = dt_util.utcnow() - timedelta(minutes=minutes)
    return coordinator.degree_days


async def _save_options(
    hass: HomeAssistant, entry: MockConfigEntry, **changes
) -> dict:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={**OPTIONS, **changes}
    )
    await hass.async_block_till_done()
    return result


async def test_options_sensor_change_works_like_dashboard(
    recorder_mock, hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Changing the sensor in Configure closes the interval and records it."""
    before = _rewind(hass, loaded_entry, 30)

    result = await _save_options(
        hass, loaded_entry, **{CONF_TEMPERATURE_ENTITY: "sensor.other_temperature"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    coordinator = _coordinator(hass, loaded_entry)  # Reloaded coordinator
    assert coordinator.temperature_entity == "sensor.other_temperature"
    assert coordinator.temperature_change_history[-1]["old_entity"] == (
        "sensor.test_temperature"
    )
    assert coordinator.degree_days == pytest.approx(before + 4.0 * 30 / 1440, rel=1e-3)


async def test_saving_options_does_not_lose_counting(
    recorder_mock, hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Saving options reloads the integration without losing counted time."""
    before = _rewind(hass, loaded_entry, 30)

    await _save_options(hass, loaded_entry, **{CONF_TARGET_DEGREE_DAYS: 50.0})

    coordinator = _coordinator(hass, loaded_entry)
    assert coordinator.target_degree_days == 50.0
    assert coordinator.degree_days == pytest.approx(before + 4.0 * 30 / 1440, rel=1e-3)


async def test_sensor_without_state_can_be_selected(coordinator) -> None:
    """A registered temperature sensor without a value yet is accepted."""
    hass = coordinator.hass
    er.async_get(hass).async_get_or_create(
        "sensor",
        "test",
        "garage_temperature",
        suggested_object_id="garage_temperature",
        original_device_class="temperature",
    )

    await coordinator.async_change_temperature_entity("sensor.garage_temperature")

    assert coordinator.temperature_entity == "sensor.garage_temperature"


async def test_non_temperature_sensor_is_rejected(coordinator) -> None:
    """Other entities give a clear validation error."""
    coordinator.hass.states.async_set("sensor.humidity", "55", {"device_class": "humidity"})

    with pytest.raises(ServiceValidationError):
        await coordinator.async_change_temperature_entity("sensor.humidity")

    assert coordinator.temperature_entity == "sensor.test_temperature"

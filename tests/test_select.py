"""Tests for the Modningsteller temperature sensor select."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.modningsteller.select import TemperatureSensorSelect


@pytest.mark.usefixtures("enable_custom_integrations")
def test_temperature_select_includes_registry_sensors_without_state(
    hass: HomeAssistant, coordinator, monkeypatch
) -> None:
    """Registered temperature entities are offered even before they have a state."""
    registry = MagicMock()
    registry.entities = {
        "sensor.registry_temperature": SimpleNamespace(
            disabled_by=None,
            device_class="temperature",
            original_device_class=None,
            area_id=None,
            name="Garage temperature",
            original_name="Garage temperature",
        )
    }
    registry.async_get.side_effect = registry.entities.get

    from homeassistant.helpers import entity_registry as er

    monkeypatch.setattr(er, "async_get", lambda _hass: registry)

    coordinator.temperature_entity = "sensor.registry_temperature"
    select = TemperatureSensorSelect(coordinator)
    select.hass = hass
    select._update_options()

    assert "Garage temperature" in select.options


@pytest.mark.usefixtures("enable_custom_integrations")
def test_temperature_select_includes_live_unregistered_temperature_sensor(
    hass: HomeAssistant, coordinator, monkeypatch
) -> None:
    """Live temperature sensors are included even when not present in the registry."""
    registry = MagicMock()
    registry.entities = {}
    registry.async_get.return_value = None

    from homeassistant.helpers import entity_registry as er

    monkeypatch.setattr(er, "async_get", lambda _hass: registry)
    hass.states.async_set(
        "sensor.yaml_temperature",
        "4.5",
        {
            "device_class": "temperature",
            "friendly_name": "YAML temperature",
        },
    )

    select = TemperatureSensorSelect(coordinator)
    select.hass = hass
    select._update_options()

    assert any(option.startswith("YAML temperature") for option in select.options)

"""Tests for the Modningsteller temperature sensor select."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.modningsteller.const import DOMAIN
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
            device_id=None,
            name="Garage temperature",
            original_name="Garage temperature",
            platform="zigbee",
            capabilities={"state_class": "measurement"},
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
            "state_class": "measurement",
            "friendly_name": "YAML temperature",
        },
    )

    select = TemperatureSensorSelect(coordinator)
    select.hass = hass
    select._update_options()

    assert any(option.startswith("YAML temperature") for option in select.options)


def _register(
    hass: HomeAssistant,
    platform: str,
    object_id: str,
    state_class: str | None,
    friendly_name: str,
) -> str:
    """Register a temperature sensor and give it a state."""
    entry = er.async_get(hass).async_get_or_create(
        "sensor",
        platform,
        object_id,
        suggested_object_id=object_id,
        original_device_class="temperature",
        capabilities={"state_class": state_class} if state_class else None,
    )
    attributes = {"device_class": "temperature", "friendly_name": friendly_name}
    if state_class:
        attributes["state_class"] = state_class
    hass.states.async_set(entry.entity_id, "4.0", attributes)
    return entry.entity_id


@pytest.mark.usefixtures("enable_custom_integrations")
def test_temperature_select_offers_only_measuring_sensors_from_others(
    hass: HomeAssistant, coordinator
) -> None:
    """Own average sensors and non-measuring sensors are left out."""
    measuring = _register(hass, "zigbee", "garage", "measurement", "Garage")
    _register(hass, DOMAIN, "rype_average", "measurement", "Rype Middeltemperatur")
    _register(hass, "car", "setpoint", None, "Car set temperature")
    hass.states.async_set(
        "sensor.yaml_setpoint",
        "21",
        {"device_class": "temperature", "friendly_name": "YAML setpoint"},
    )

    select = TemperatureSensorSelect(coordinator)
    select.hass = hass
    select._update_options()

    offered = {select._option_to_entity[option] for option in select.options}
    assert measuring in offered
    assert offered == {measuring, coordinator.temperature_entity}


@pytest.mark.usefixtures("enable_custom_integrations")
def test_temperature_select_keeps_current_sensor_even_if_filtered(
    hass: HomeAssistant, coordinator
) -> None:
    """The selected sensor is never removed from the list."""
    current = _register(hass, "car", "setpoint", None, "Car set temperature")
    coordinator.temperature_entity = current

    select = TemperatureSensorSelect(coordinator)
    select.hass = hass
    select._update_options()

    assert current in select._option_to_entity.values()


async def test_own_average_sensor_is_rejected(
    hass: HomeAssistant, coordinator
) -> None:
    """A counter cannot be switched to a Modningsteller sensor."""
    own = _register(hass, DOMAIN, "rype_average", "measurement", "Rype Middeltemperatur")

    with pytest.raises(ServiceValidationError):
        await coordinator.async_change_temperature_entity(own)


@pytest.mark.usefixtures("enable_custom_integrations")
def test_temperature_select_shows_area_inherited_from_device(
    hass: HomeAssistant, coordinator
) -> None:
    """A sensor without its own area gets the area of its device."""
    config_entry = MockConfigEntry(domain="zigbee")
    config_entry.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Garasje")
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("zigbee", "hygrostat")},
        name="Hygrostat",
    )
    dr.async_get(hass).async_update_device(device.id, area_id=area.id)
    entry = er.async_get(hass).async_get_or_create(
        "sensor",
        "zigbee",
        "hygrostat_temperature",
        suggested_object_id="hygrostat_temperature",
        original_device_class="temperature",
        device_id=device.id,
    )
    hass.states.async_set(
        entry.entity_id,
        "4.0",
        {
            "device_class": "temperature",
            "state_class": "measurement",
            "friendly_name": "Hygrostat Temperatur",
        },
    )

    select = TemperatureSensorSelect(coordinator)
    select.hass = hass
    select._update_options()

    assert "Hygrostat Temperatur (Garasje)" in select.options


@pytest.mark.usefixtures("enable_custom_integrations")
def test_temperature_select_shows_area_even_when_in_name(
    hass: HomeAssistant, coordinator
) -> None:
    """The area is always shown, so the list is consistent."""
    area = ar.async_get(hass).async_create("Garasje")
    entry = er.async_get(hass).async_get_or_create(
        "sensor",
        "zigbee",
        "garage_temperature",
        suggested_object_id="garage_temperature",
        original_device_class="temperature",
    )
    er.async_get(hass).async_update_entity(entry.entity_id, area_id=area.id)
    hass.states.async_set(
        entry.entity_id,
        "4.0",
        {
            "device_class": "temperature",
            "state_class": "measurement",
            "friendly_name": "Temperaturmåler Garasje",
        },
    )

    select = TemperatureSensorSelect(coordinator)
    select.hass = hass
    select._update_options()

    assert "Temperaturmåler Garasje (Garasje)" in select.options

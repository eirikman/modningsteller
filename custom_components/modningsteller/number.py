"""Number entities for Modningsteller."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ModningstellerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Modningsteller number entities."""
    coordinator: ModningstellerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CalibrationValueNumber(coordinator)])


class CalibrationValueNumber(
    CoordinatorEntity[ModningstellerCoordinator], NumberEntity
):
    """Proposed degree-day value for calibration."""

    _attr_has_entity_name = True
    _attr_translation_key = "calibration_value"
    _attr_icon = "mdi:tune-variant"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 10000.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "°C·d"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_calibration_value"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Modningsteller",
            model="Mørningsteller",
        )
        self._value = round(coordinator.calibration_value, 3)

    @property
    def native_value(self) -> float:
        return self.coordinator.calibration_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the proposed calibration value; apply with the Calibrate button."""
        self._value = round(float(value), 3)
        self.coordinator.calibration_value = self._value
        self.async_write_ha_state()

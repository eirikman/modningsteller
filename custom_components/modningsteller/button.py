"""Buttons for Modningsteller."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.button import ButtonEntity
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
    """Set up Modningsteller buttons."""
    coordinator: ModningstellerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            StartButton(coordinator),
            PauseButton(coordinator),
            ResetButton(coordinator),
            CalibrateButton(coordinator),
        ]
    )


class BaseModningstellerButton(
    CoordinatorEntity[ModningstellerCoordinator], ButtonEntity
):
    """Base class for Modningsteller buttons."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ModningstellerCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Modningsteller",
            model="Mørningsteller",
        )


class StartButton(BaseModningstellerButton):
    """Start or resume the counter."""

    _attr_translation_key = "start"
    _attr_icon = "mdi:play"

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "start")

    async def async_press(self) -> None:
        """Start the counter."""
        await self.coordinator.async_start()


class PauseButton(BaseModningstellerButton):
    """Pause the counter."""

    _attr_translation_key = "pause"
    _attr_icon = "mdi:pause"

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "pause")

    async def async_press(self) -> None:
        """Pause the counter."""
        await self.coordinator.async_pause()


class ResetButton(BaseModningstellerButton):
    """Reset the counter to its configured initial value."""

    _attr_translation_key = "reset"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "reset")

    async def async_press(self) -> None:
        """Reset the counter."""
        await self.coordinator.async_reset()


class CalibrateButton(BaseModningstellerButton):
    """Apply the configured calibration value and comment."""

    _attr_translation_key = "calibrate"
    _attr_icon = "mdi:tune-variant"

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator, "calibrate")

    async def async_press(self) -> None:
        """Apply calibration."""
        await self.coordinator.async_calibrate(
            self.coordinator.calibration_value,
            self.coordinator.calibration_comment,
        )

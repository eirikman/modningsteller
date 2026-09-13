"""Text entities for Modningsteller."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
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
    """Set up Modningsteller text entities."""
    coordinator: ModningstellerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CalibrationCommentText(coordinator), NoteText(coordinator)])


class CalibrationCommentText(CoordinatorEntity[ModningstellerCoordinator], TextEntity):
    """Comment used for the next calibration."""

    _attr_has_entity_name = True
    _attr_translation_key = "calibration_comment"
    _attr_icon = "mdi:comment-edit-outline"
    _attr_mode = TextMode.TEXT
    _attr_native_max = 255
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_calibration_comment"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Modningsteller",
            model="Mørningsteller",
        )
        self._value = coordinator.calibration_comment

    @property
    def native_value(self) -> str:
        return self.coordinator.calibration_comment

    async def async_set_value(self, value: str) -> None:
        """Set the comment for the next calibration."""
        self._value = value[:255]
        self.coordinator.calibration_comment = self._value
        self.async_write_ha_state()


class NoteText(CoordinatorEntity[ModningstellerCoordinator], TextEntity):
    """Persistent note attached to the maturation counter."""

    _attr_has_entity_name = True
    _attr_translation_key = "note"
    _attr_icon = "mdi:note-text-outline"
    _attr_mode = TextMode.TEXT
    _attr_native_max = 1000

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_note"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Modningsteller",
            model="Mørningsteller",
        )

    @property
    def native_value(self) -> str:
        return self.coordinator.note

    async def async_set_value(self, value: str) -> None:
        """Save the note and record it as a maturation event."""
        await self.coordinator.async_set_note(value)

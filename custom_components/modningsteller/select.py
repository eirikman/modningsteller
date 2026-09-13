"""Select entities for Modningsteller."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.select import SelectEntity
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
    """Set up Modningsteller selects."""
    coordinator: ModningstellerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TemperatureSensorSelect(coordinator)])


class TemperatureSensorSelect(
    CoordinatorEntity[ModningstellerCoordinator], SelectEntity
):
    """Allow changing the active temperature sensor while running."""

    _attr_has_entity_name = True
    _attr_translation_key = "temperature_sensor"
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator: ModningstellerCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_temperature_sensor"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Modningsteller",
            model="Mørningsteller",
        )
        self._options: list[str] = []
        self._option_to_entity: dict[str, str] = {}
        self._entity_to_option: dict[str, str] = {}

    async def async_added_to_hass(self) -> None:
        """Set up the select entity after it has access to Home Assistant."""
        await super().async_added_to_hass()
        self._update_options()
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        """Return the friendly label for the currently selected sensor."""
        entity_id = self.coordinator.temperature_entity
        return self._entity_to_option.get(entity_id, entity_id)

    @property
    def options(self) -> list[str]:
        """Return friendly sensor names for the dropdown."""
        return self._options

    @callback
    def _sensor_display_name(self, entity_id: str) -> str:
        """Return a user-friendly, unique display name for a temperature sensor."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return entity_id

        # Prefer Home Assistant's display name instead of the entity ID.
        name = state.name or entity_id

        # Add the area when available; this makes identically named sensors easy to
        # distinguish without exposing entity IDs in the normal case.
        try:
            from homeassistant.helpers import area_registry as ar
            from homeassistant.helpers import entity_registry as er

            entity_registry = er.async_get(self.hass)
            entity_entry = entity_registry.async_get(entity_id)
            if entity_entry and entity_entry.area_id:
                area_registry = ar.async_get(self.hass)
                area = area_registry.async_get_area(entity_entry.area_id)
                if area and area.name and area.name.lower() not in name.lower():
                    name = f"{name} ({area.name})"
        except Exception:  # pragma: no cover - defensive for registry availability
            pass

        return name

    @callback
    def _update_options(self) -> None:
        """Refresh available temperature sensors using the same basic filter as the UI selector."""
        entities: dict[str, str] = {}
        current = self.coordinator.temperature_entity

        for state in self.hass.states.async_all("sensor"):
            # Match Home Assistant's temperature entity selection criteria.
            if state.attributes.get("device_class") != "temperature":
                continue

            entity_id = state.entity_id
            entities[entity_id] = self._sensor_display_name(entity_id)

        # Never lose the currently selected sensor from the list, even if it is
        # temporarily unavailable or has otherwise disappeared from the state machine.
        if current and current not in entities:
            entities[current] = self._sensor_display_name(current)

        # Make display labels unique. In the rare case where two entities have the
        # same name and area, append the entity ID only to the duplicate labels.
        grouped: dict[str, list[str]] = {}
        for entity_id, label in entities.items():
            grouped.setdefault(label, []).append(entity_id)

        self._option_to_entity.clear()
        self._entity_to_option.clear()
        options: list[str] = []

        for label, entity_ids in sorted(grouped.items(), key=lambda item: item[0].lower()):
            for entity_id in sorted(entity_ids):
                option = label if len(entity_ids) == 1 else f"{label} — {entity_id}"
                self._option_to_entity[option] = entity_id
                self._entity_to_option[entity_id] = option
                options.append(option)

        self._options = options

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh options and write the current select state."""
        self._update_options()
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Switch to the selected temperature sensor."""
        entity_id = self._option_to_entity.get(option)
        if entity_id is None:
            return

        await self.coordinator.async_change_temperature_entity(entity_id)
        self._update_options()
        self.async_write_ha_state()

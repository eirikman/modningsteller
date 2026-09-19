"""The Modningsteller integration."""

from __future__ import annotations

from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN
from .coordinator import ModningstellerCoordinator

PLATFORMS = ["sensor", "button", "number", "text", "select"]


def _notification_id(entry: ConfigEntry) -> str:
    return f"modningsteller_{entry.entry_id}_target"


def _notification_text(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: ModningstellerCoordinator,
) -> tuple[str, str]:
    """Return a localized target notification using the Home Assistant system language."""
    language = (hass.config.language or "en").lower()
    is_norwegian = language in {"nb", "no"} or language.startswith("nb-")
    if is_norwegian:
        title = f"Modning ferdig: {entry.title}"
        message = (
            f"{entry.title} har nådd {coordinator.target_degree_days:.1f} °C·d. "
            f"Telleren fortsetter å telle. Nåværende verdi er {coordinator.degree_days:.1f} °C·d. "
            f"Middeltemperatur siste time er {coordinator.average_temperature:.1f} °C."
        )
        return title, message
    title = f"Maturation target reached: {entry.title}"
    message = (
        f"{entry.title} has reached {coordinator.target_degree_days:.1f} °C·d. "
        f"The counter will continue. The current value is {coordinator.degree_days:.1f} °C·d. "
        f"The one-hour average temperature is {coordinator.average_temperature:.1f} °C."
    )
    return title, message


def _last_temperature_text(coordinator: ModningstellerCoordinator, norwegian: bool) -> str:
    """Return a localized description of the last known temperature."""
    if coordinator.last_valid_temperature is None:
        return "Ingen gyldig temperatur er kjent." if norwegian else "No valid temperature is known."
    if norwegian:
        return f"Siste kjente temperatur er {coordinator.last_valid_temperature:.1f} °C."
    return f"The last known temperature is {coordinator.last_valid_temperature:.1f} °C."


def _sensor_health_notification_id(entry: ConfigEntry) -> str:
    return f"modningsteller_{entry.entry_id}_sensor_health"


def _sensor_health_notification_text(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: ModningstellerCoordinator,
    health: str,
) -> tuple[str, str]:
    language = (hass.config.language or "en").lower()
    is_norwegian = language in {"nb", "no"} or language.startswith("nb-")
    sensor_name = coordinator.temperature_entity
    if health == "stale":
        if is_norwegian:
            return (
                f"Temperatursensor reagerer ikke: {entry.title}",
                f"Temperatursensoren {sensor_name} har ikke fått en ny verdi på mer enn "
                f"{coordinator.temperature_sensor_stale_after_seconds / 60:.0f} minutter. "
                "Døgngradtellingen fortsetter med siste kjente temperatur når denne finnes.",
            )
        return (
            f"Temperature sensor is stale: {entry.title}",
            f"The temperature sensor {sensor_name} has not received a new value for more than "
            f"{coordinator.temperature_sensor_stale_after_seconds / 60:.0f} minutes. "
            f"The counter continues using the last known temperature when available. {_last_temperature_text(coordinator, False)}",
        )
    if is_norwegian:
        return (
            f"Temperatursensor utilgjengelig: {entry.title}",
            f"Temperatursensoren {sensor_name} er utilgjengelig eller har en ugyldig verdi. "
            f"Telleren fortsetter med siste kjente temperatur når denne finnes. {_last_temperature_text(coordinator, True)}",
        )
    return (
        f"Temperature sensor unavailable: {entry.title}",
        f"The temperature sensor {sensor_name} is unavailable or has an invalid value. "
        f"The counter continues using the last known temperature when available. {_last_temperature_text(coordinator, False)}",
    )


async def _async_sensor_health_changed(
    hass: HomeAssistant,
    entry: ConfigEntry,
    old_health: str,
    new_health: str,
    reason: str | None,
) -> None:
    """Create or clear a persistent notification when sensor health changes."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    notification_id = _sensor_health_notification_id(entry)
    if new_health in {"unavailable", "stale"}:
        title, message = _sensor_health_notification_text(
            hass, entry, coordinator, new_health
        )
        async_create(
            hass,
            message,
            title=title,
            notification_id=notification_id,
        )
    elif old_health in {"unavailable", "stale"} and new_health == "ok":
        async_dismiss(hass, notification_id)


async def _async_target_reached(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Notify that a maturation counter reached its target."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    title, message = _notification_text(hass, entry, coordinator)

    async_create(
        hass,
        message,
        title=title,
        notification_id=_notification_id(entry),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modningsteller from a config entry."""
    coordinator = ModningstellerCoordinator(hass, entry)

    # Store the coordinator before the first refresh. The first refresh can
    # change sensor health and schedule notification callbacks, so those
    # callbacks must be able to resolve the coordinator from hass.data.
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    coordinator.on_target_reached = lambda: _async_target_reached(hass, entry)
    coordinator.on_sensor_health_changed = (
        lambda old_health, new_health, reason: _async_sensor_health_changed(
            hass, entry, old_health, new_health, reason
        )
    )

    await coordinator.async_config_entry_first_refresh()

    # Register the post-start refresh before forwarding the platforms. The
    # selected temperature integration can become available a little later
    # than Home Assistant itself, so the coordinator owns a short retry
    # window instead of assuming the first post-start refresh is definitive.
    async def _async_home_assistant_started(_hass: HomeAssistant) -> None:
        coordinator._cancel_startup_refresh = None
        if coordinator._startup_retry_task is None or coordinator._startup_retry_task.done():
            coordinator._startup_retry_task = hass.async_create_task(
                coordinator.async_startup_sensor_check()
            )

    coordinator._cancel_startup_refresh = async_at_started(
        hass, _async_home_assistant_started
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Modningsteller config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = hass.data[DOMAIN].get(entry.entry_id)
        if coordinator is not None:
            cancel_startup_refresh = getattr(coordinator, "_cancel_startup_refresh", None)
            if cancel_startup_refresh is not None:
                cancel_startup_refresh()
                coordinator._cancel_startup_refresh = None
            startup_retry_task = getattr(coordinator, "_startup_retry_task", None)
            if startup_retry_task is not None and not startup_retry_task.done():
                startup_retry_task.cancel()
            coordinator._startup_retry_task = None
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded

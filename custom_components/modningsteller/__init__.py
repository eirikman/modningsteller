"""The Modningsteller integration."""

from __future__ import annotations

from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN
from .coordinator import ModningstellerCoordinator

PLATFORMS = ["sensor", "button", "number", "text", "select"]


def _notification_id(entry: ConfigEntry) -> str:
    return f"modningsteller_{entry.entry_id}_target"


async def _async_translate(
    hass: HomeAssistant,
    key: str,
    placeholders: dict[str, object],
) -> str:
    """Return a localized integration string from the Home Assistant translation cache."""
    language = hass.config.language or "en"
    translations = await async_get_translations(
        hass, language, "common", {DOMAIN}
    )
    translation_key = f"component.{DOMAIN}.common.{key}"
    text = translations.get(translation_key)
    if text is None:
        raise KeyError(f"Missing Modningsteller translation: {translation_key}")
    return text.format(**placeholders)


async def _async_last_temperature_text(
    hass: HomeAssistant, coordinator: ModningstellerCoordinator
) -> str:
    """Return a localized description of the last known temperature."""
    if coordinator.last_valid_temperature is None:
        return await _async_translate(
            hass,
            "notifications.last_temperature.unknown",
            {},
        )
    return await _async_translate(
        hass,
        "notifications.last_temperature.known",
        {"temperature": coordinator.last_valid_temperature},
    )


async def _async_notification_text(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: ModningstellerCoordinator,
) -> tuple[str, str]:
    """Return a localized target notification using Home Assistant's language."""
    placeholders = {
        "name": entry.title,
        "target_degree_days": coordinator.target_degree_days,
        "degree_days": coordinator.degree_days,
        "average_temperature": coordinator.average_temperature,
    }
    return (
        await _async_translate(
            hass, "notifications.target_reached.title", placeholders
        ),
        await _async_translate(
            hass, "notifications.target_reached.message", placeholders
        ),
    )


async def _async_sensor_health_notification_text(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: ModningstellerCoordinator,
    health: str,
) -> tuple[str, str]:
    """Return a localized sensor health notification."""
    key = "stale" if health == "stale" else "unavailable"
    last_temperature = await _async_last_temperature_text(hass, coordinator)
    placeholders = {
        "name": entry.title,
        "sensor": coordinator.temperature_entity,
        "minutes": coordinator.temperature_sensor_stale_after_seconds / 60,
        "last_temperature": last_temperature,
    }
    return (
        await _async_translate(
            hass, f"notifications.sensor_health.{key}.title", placeholders
        ),
        await _async_translate(
            hass, f"notifications.sensor_health.{key}.message", placeholders
        ),
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
        title, message = await _async_sensor_health_notification_text(
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
    title, message = await _async_notification_text(hass, entry, coordinator)

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

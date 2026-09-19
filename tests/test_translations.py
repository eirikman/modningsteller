"""Tests for Modningsteller backend translations."""

from __future__ import annotations

import json
from pathlib import Path
from string import Formatter
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components import modningsteller
from custom_components.modningsteller.const import DOMAIN


TRANSLATIONS_DIR = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / DOMAIN
    / "translations"
)


def _flatten(value: object, prefix: str = "") -> dict[str, str]:
    if isinstance(value, dict):
        result: dict[str, str] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            result.update(_flatten(child, child_prefix))
        return result
    assert isinstance(value, str)
    return {prefix: value}


def _placeholders(value: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in Formatter().parse(value)
        if field_name is not None
    }


def test_notification_translations_have_matching_keys_and_placeholders() -> None:
    """English and Norwegian notification translations must stay in sync."""
    en = json.loads((TRANSLATIONS_DIR / "en.json").read_text(encoding="utf-8"))
    nb = json.loads((TRANSLATIONS_DIR / "nb.json").read_text(encoding="utf-8"))

    en_common = {
        key: value
        for key, value in en["common"].items()
        if key.startswith("notification_")
    }
    nb_common = {
        key: value
        for key, value in nb["common"].items()
        if key.startswith("notification_")
    }

    assert en_common.keys() == nb_common.keys()
    assert all(isinstance(value, str) for value in en_common.values())
    assert all(isinstance(value, str) for value in nb_common.values())
    for key in en_common:
        assert _placeholders(en_common[key]) == _placeholders(nb_common[key])


@pytest.mark.asyncio
async def test_target_notification_uses_translation_catalog(monkeypatch) -> None:
    """Target notification text comes from Home Assistant translations."""
    hass = MagicMock()
    hass.config.language = "nb"
    entry = MagicMock()
    entry.title = "Rype"
    coordinator = MagicMock()
    coordinator.target_degree_days = 40.0
    coordinator.degree_days = 41.2
    coordinator.average_temperature = 4.5

    translations = {
        f"component.{DOMAIN}.common.notification_target_reached_title": "NÅDD: {name}",
        f"component.{DOMAIN}.common.notification_target_reached_message": (
            "{name}: {target_degree_days:.1f}/{degree_days:.1f} at "
            "{average_temperature:.1f}"
        ),
    }
    loader = AsyncMock(return_value=translations)
    monkeypatch.setattr(modningsteller, "async_get_translations", loader)

    title, message = await modningsteller._async_notification_text(
        hass, entry, coordinator
    )

    assert title == "NÅDD: Rype"
    assert message == "Rype: 40.0/41.2 at 4.5"
    loader.assert_awaited_once_with(hass, "nb", "common", {DOMAIN})


@pytest.mark.asyncio
async def test_sensor_health_notification_uses_translation_catalog(monkeypatch) -> None:
    """Sensor health notification text comes from Home Assistant translations."""
    hass = MagicMock()
    hass.config.language = "en"
    entry = MagicMock()
    entry.title = "Rype"
    coordinator = MagicMock()
    coordinator.temperature_entity = "sensor.garage_temperature"
    coordinator.temperature_sensor_stale_after_seconds = 14400
    coordinator.last_valid_temperature = 14.4

    translations = {
        f"component.{DOMAIN}.common.notification_sensor_health_stale_title": (
            "STALE: {name}"
        ),
        f"component.{DOMAIN}.common.notification_sensor_health_stale_message": (
            "{sensor} {minutes:.0f} {last_temperature}"
        ),
        f"component.{DOMAIN}.common.notification_last_temperature_known": (
            "Known temperature: {temperature:.1f}"
        ),
    }
    loader = AsyncMock(return_value=translations)
    monkeypatch.setattr(modningsteller, "async_get_translations", loader)

    title, message = await modningsteller._async_sensor_health_notification_text(
        hass, entry, coordinator, "stale"
    )

    assert title == "STALE: Rype"
    assert message == "sensor.garage_temperature 240 Known temperature: 14.4"
    assert loader.await_count == 1

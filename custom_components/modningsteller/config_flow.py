"""Config flow for Modningsteller."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_INITIAL_DEGREE_DAYS,
    CONF_TARGET_DEGREE_DAYS,
    CONF_TEMPERATURE_ENTITY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_INITIAL_DEGREE_DAYS,
    DEFAULT_TARGET_DEGREE_DAYS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_TARGET_DEGREE_DAYS,
    MIN_UPDATE_INTERVAL,
)


class ModningstellerOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle options for an existing Modningsteller counter."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Allow changing the temperature sensor and runtime settings."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        data = self.config_entry.data

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TEMPERATURE_ENTITY,
                    default=current.get(
                        CONF_TEMPERATURE_ENTITY, data[CONF_TEMPERATURE_ENTITY]
                    ),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="temperature",
                    )
                ),
                vol.Required(
                    CONF_INITIAL_DEGREE_DAYS,
                    default=float(
                        current.get(
                            CONF_INITIAL_DEGREE_DAYS, data[CONF_INITIAL_DEGREE_DAYS]
                        )
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10000,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°C·d",
                    )
                ),
                vol.Required(
                    CONF_TARGET_DEGREE_DAYS,
                    default=float(
                        current.get(
                            CONF_TARGET_DEGREE_DAYS, data[CONF_TARGET_DEGREE_DAYS]
                        )
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_TARGET_DEGREE_DAYS,
                        max=10000,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°C·d",
                    )
                ),
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=int(
                        current.get(
                            CONF_UPDATE_INTERVAL, data[CONF_UPDATE_INTERVAL]
                        )
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_UPDATE_INTERVAL,
                        max=MAX_UPDATE_INTERVAL,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Modningsteller."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return ModningstellerOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
                vol.Required(CONF_TEMPERATURE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="temperature",
                    )
                ),
                vol.Required(
                    CONF_INITIAL_DEGREE_DAYS,
                    default=DEFAULT_INITIAL_DEGREE_DAYS,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=10000,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°C·d",
                    )
                ),
                vol.Required(
                    CONF_TARGET_DEGREE_DAYS,
                    default=DEFAULT_TARGET_DEGREE_DAYS,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_TARGET_DEGREE_DAYS,
                        max=10000,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°C·d",
                    )
                ),
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=DEFAULT_UPDATE_INTERVAL,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_UPDATE_INTERVAL,
                        max=MAX_UPDATE_INTERVAL,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

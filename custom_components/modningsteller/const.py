"""Constants for the Modningsteller integration."""

from typing import Final

DOMAIN: Final = "modningsteller"

CONF_NAME: Final = "name"
CONF_TEMPERATURE_ENTITY: Final = "temperature_entity"
CONF_INITIAL_DEGREE_DAYS: Final = "initial_degree_days"
CONF_TARGET_DEGREE_DAYS: Final = "target_degree_days"
CONF_UPDATE_INTERVAL: Final = "update_interval"

DEFAULT_INITIAL_DEGREE_DAYS: Final = 0.0
DEFAULT_TARGET_DEGREE_DAYS: Final = 40.0
DEFAULT_UPDATE_INTERVAL: Final = 10

MIN_TARGET_DEGREE_DAYS: Final = 0.1
MIN_UPDATE_INTERVAL: Final = 1
MAX_UPDATE_INTERVAL: Final = 60
AVERAGE_WINDOW_MINUTES: Final = 60
DEFAULT_SENSOR_STALE_MINUTES: Final = 120

STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = f"{DOMAIN}.state"

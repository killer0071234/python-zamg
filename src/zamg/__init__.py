"""Asynchronous Python client for GeoSphere Austria weather data."""

__version__ = "0.4.2"

from .exceptions import (
    ZamgApiError,
    ZamgError,
    ZamgNoDataError,
    ZamgStationNotFoundError,
    ZamgStationUnknownError,
)
from .nwp import NwpClient, NwpForecast, NwpForecastRecord
from .symbols import (
    SYMBOL_CONDITION,
    SYMBOL_TEXT_DE,
    SYMBOL_TEXT_EN,
    symbol_to_condition,
    symbol_to_text,
)
from .zamg import ZamgData

__all__ = [
    "ZamgApiError",
    "ZamgError",
    "ZamgNoDataError",
    "ZamgStationNotFoundError",
    "ZamgStationUnknownError",
    "ZamgData",
    "NwpClient",
    "NwpForecast",
    "NwpForecastRecord",
    "SYMBOL_CONDITION",
    "SYMBOL_TEXT_DE",
    "SYMBOL_TEXT_EN",
    "symbol_to_condition",
    "symbol_to_text",
]

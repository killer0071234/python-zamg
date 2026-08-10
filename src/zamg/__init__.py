"""Asynchronous Python client for GeoSphere Austria weather data."""

__version__ = "0.4.1"

from .exceptions import (
    ZamgApiError,
    ZamgError,
    ZamgNoDataError,
    ZamgStationNotFoundError,
    ZamgStationUnknownError,
)
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
    "SYMBOL_CONDITION",
    "SYMBOL_TEXT_DE",
    "SYMBOL_TEXT_EN",
    "symbol_to_condition",
    "symbol_to_text",
]

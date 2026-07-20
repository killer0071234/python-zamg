"""Asynchronous Python client for GeoSphere Austria weather data."""

__version__ = "0.4.1"

from .exceptions import (
    ZamgApiError,
    ZamgError,
    ZamgNoDataError,
    ZamgStationNotFoundError,
    ZamgStationUnknownError,
)
from .zamg import ZamgData

__all__ = [
    "ZamgApiError",
    "ZamgError",
    "ZamgNoDataError",
    "ZamgStationNotFoundError",
    "ZamgStationUnknownError",
    "ZamgData",
]

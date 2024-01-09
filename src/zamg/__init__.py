"""Asynchronous Python client for GeoSphere Austria weather data."""

__version__ = "0.3.3"

from .exceptions import ZamgApiError
from .exceptions import ZamgError
from .exceptions import ZamgNoDataError
from .exceptions import ZamgStationNotFoundError
from .exceptions import ZamgStationUnknownError
from .zamg import ZamgData


__all__ = [
    "ZamgApiError",
    "ZamgError",
    "ZamgNoDataError",
    "ZamgStationNotFoundError",
    "ZamgStationUnknownError",
    "ZamgData",
]

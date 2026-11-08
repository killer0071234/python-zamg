"""Exceptions for GeoSphere Austria."""

from __future__ import annotations


class ZamgError(Exception):
    """Generic GeoSphere Austria exception."""


class ZamgStationNotFoundError(ZamgError):
    """GeoSphere Austria weather station not found."""


class ZamgStationUnknownError(ZamgError):
    """GeoSphere Austria weather station is not known."""


class ZamgNoDataError(ZamgError):
    """GeoSphere Austria no data exception."""


class ZamgApiError(ZamgError):
    """GeoSphere Austria api exception."""

    def __init__(
        self,
        *args: object,
        status_code: int | None = None,
        rate_limit_reset: int | None = None,
    ) -> None:
        """Initialize an API error with optional HTTP response metadata."""
        super().__init__(*args)
        self.status_code = status_code
        self.rate_limit_reset = rate_limit_reset

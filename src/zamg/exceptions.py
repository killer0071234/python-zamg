"""Exceptions for GeoSphere Austria."""


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

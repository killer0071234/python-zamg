"""Exceptions for Zamg."""


class ZamgError(Exception):
    """Generic Zamg exception."""


class ZamgStationNotFoundError(ZamgError):
    """Zamg weather station not found."""


class ZamgStationUnknownError(ZamgError):
    """Zamg weather station is not known."""


class ZamgNoDataError(ZamgError):
    """Zamg no data exception."""


class ZamgApiError(ZamgError):
    """Zamg api exception."""

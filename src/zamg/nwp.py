"""GeoSphere Austria numerical weather prediction client."""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass
from datetime import datetime
from numbers import Real
from sys import version_info
from typing import Any

import aiohttp
import async_timeout
from aiohttp.hdrs import USER_AGENT

from . import __version__
from .exceptions import ZamgApiError, ZamgNoDataError
from .symbols import symbol_to_condition, symbol_to_text

FORECAST_URL = (
    "https://dataset.api.hub.geosphere.at/v1/timeseries/forecast/nwp-v2-1h-1km"
)
FORECAST_PARAMETERS = ("2t", "2r", "10u", "10v", "10fg", "tcc", "msl", "tp", "sy")
EXPECTED_UNITS = {
    "2t": "degree Celsius",
    "2r": "%",
    "10u": "m s-1",
    "10v": "m s-1",
    "10fg": "m s-1",
    "tcc": "%",
    "msl": "Pa",
    "tp": "kg m-2",
    "sy": "1",
}
CLIENT_AGENT = (
    f"Python/{version_info[0]}.{version_info[1]} "
    f"+https://github.com/killer0071234/python-zamg python-zamg/{__version__}"
)


@dataclass(frozen=True)
class NwpForecastRecord:
    """One hourly NWP forecast record in GeoSphere API native units."""

    valid_time: datetime
    temperature: float | None
    relative_humidity: float | None
    cloud_cover: float | None
    mean_sea_level_pressure: float | None
    wind_u: float | None
    wind_v: float | None
    wind_speed: float | None
    wind_bearing: float | None
    wind_gust: float | None
    precipitation: float | None
    symbol: float | None
    symbol_text: str | None
    condition: str | None


@dataclass(frozen=True)
class NwpForecast:
    """A coordinate-based NWP forecast."""

    reference_time: datetime
    requested_latitude: float
    requested_longitude: float
    resolved_latitude: float
    resolved_longitude: float
    records: tuple[NwpForecastRecord, ...]


class NwpClient:
    """Asynchronous client for GeoSphere Austria NWP v2 forecasts."""

    request_timeout: float = 8.0
    verify_ssl: bool | None = None

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Initialize the NWP client."""
        self.session = session
        self._close_session = False
        self.headers = {USER_AGENT: CLIENT_AGENT}

    async def get_forecast(self, *, latitude: float, longitude: float) -> NwpForecast:
        """Return an hourly forecast for the nearest model grid point."""
        requested_latitude = _validate_coordinate(latitude, "latitude", -90.0, 90.0)
        requested_longitude = _validate_coordinate(
            longitude, "longitude", -180.0, 180.0
        )
        session = self._get_session()
        request_options: dict[str, Any] = {
            "params": {
                "parameters": ",".join(FORECAST_PARAMETERS),
                "lat_lon": f"{requested_latitude},{requested_longitude}",
            },
            "headers": self.headers,
        }
        if self.verify_ssl is not None:
            request_options["ssl"] = self.verify_ssl

        try:
            async with async_timeout.timeout(self.request_timeout):
                async with session.get(FORECAST_URL, **request_options) as response:
                    body = await response.read()
                    if not 200 <= response.status < 300:
                        message = f"Got status {response.status} from GeoSphere Austria"
                        if response.status == 429:
                            reset = response.headers.get("ratelimit-reset")
                            if reset is not None:
                                message += f"; rate limit resets in {reset} seconds"
                        raise ZamgApiError(message)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise ZamgApiError(exc) from exc

        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ZamgNoDataError(exc) from exc

        return _parse_forecast(
            payload,
            requested_latitude=requested_latitude,
            requested_longitude=requested_longitude,
        )

    def _get_session(self) -> aiohttp.ClientSession:
        """Return the injected session or lazily create an owned session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            self._close_session = True
        return self.session

    async def close(self) -> None:
        """Close an internally created session."""
        if self.session is not None and self._close_session:
            await self.session.close()
            self.session = None
            self._close_session = False

    async def __aenter__(self) -> NwpClient:
        """Return the client as an asynchronous context manager."""
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Close an internally created session on context exit."""
        await self.close()


def _validate_coordinate(
    value: object, name: str, minimum: float, maximum: float
) -> float:
    """Validate and normalize a coordinate supplied by a caller."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a real number")
    normalized = float(value)
    if not math.isfinite(normalized) or not minimum <= normalized <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return normalized


def _parse_forecast(
    payload: object, *, requested_latitude: float, requested_longitude: float
) -> NwpForecast:
    """Parse a GeoSphere NWP v2 response into typed records."""
    try:
        if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
            raise ValueError("forecast response is not a FeatureCollection")

        reference_time = _parse_datetime(payload["reference_time"], "reference_time")
        timestamps = payload["timestamps"]
        if not isinstance(timestamps, list) or not timestamps:
            raise ValueError("timestamps must be a non-empty array")
        valid_times = tuple(
            _parse_datetime(value, "forecast timestamp") for value in timestamps
        )
        if any(
            current <= previous
            for previous, current in zip(valid_times, valid_times[1:])
        ):
            raise ValueError("forecast timestamps must be strictly increasing")

        resolved_latitude, resolved_longitude, parameter_values = _parse_feature(
            payload, len(valid_times)
        )
        records = _build_records(valid_times, parameter_values)
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ZamgNoDataError(exc) from exc

    return NwpForecast(
        reference_time=reference_time,
        requested_latitude=requested_latitude,
        requested_longitude=requested_longitude,
        resolved_latitude=resolved_latitude,
        resolved_longitude=resolved_longitude,
        records=records,
    )


def _parse_feature(
    payload: dict[str, object], expected_length: int
) -> tuple[float, float, dict[str, tuple[float | None, ...]]]:
    """Parse the single requested feature and its parameter arrays."""
    features = payload["features"]
    if not isinstance(features, list) or len(features) != 1:
        raise ValueError("forecast response must contain exactly one feature")
    feature = features[0]
    if not isinstance(feature, dict):
        raise ValueError("forecast feature must be an object")

    geometry = feature["geometry"]
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        raise ValueError("forecast geometry must be a Point")
    coordinates = geometry["coordinates"]
    if not isinstance(coordinates, list) or len(coordinates) != 2:
        raise ValueError("forecast Point must contain longitude and latitude")
    resolved_longitude = _validate_coordinate(
        coordinates[0], "resolved longitude", -180.0, 180.0
    )
    resolved_latitude = _validate_coordinate(
        coordinates[1], "resolved latitude", -90.0, 90.0
    )

    properties = feature["properties"]
    if not isinstance(properties, dict):
        raise ValueError("forecast properties must be an object")
    parameters = properties["parameters"]
    if not isinstance(parameters, dict):
        raise ValueError("forecast parameters must be an object")
    parameter_values = {
        name: _parse_parameter(parameters, name, expected_length)
        for name in FORECAST_PARAMETERS
    }
    return resolved_latitude, resolved_longitude, parameter_values


def _build_records(
    valid_times: tuple[datetime, ...],
    parameter_values: dict[str, tuple[float | None, ...]],
) -> tuple[NwpForecastRecord, ...]:
    """Build immutable hourly records from validated parameter arrays."""
    records = []
    for index, valid_time in enumerate(valid_times):
        wind_u = parameter_values["10u"][index]
        wind_v = parameter_values["10v"][index]
        wind_speed, wind_bearing = _wind(wind_u, wind_v)
        symbol = parameter_values["sy"][index]
        records.append(
            NwpForecastRecord(
                valid_time=valid_time,
                temperature=parameter_values["2t"][index],
                relative_humidity=parameter_values["2r"][index],
                cloud_cover=parameter_values["tcc"][index],
                mean_sea_level_pressure=parameter_values["msl"][index],
                wind_u=wind_u,
                wind_v=wind_v,
                wind_speed=wind_speed,
                wind_bearing=wind_bearing,
                wind_gust=parameter_values["10fg"][index],
                precipitation=parameter_values["tp"][index],
                symbol=symbol,
                symbol_text=symbol_to_text(symbol),
                condition=symbol_to_condition(symbol),
            )
        )
    return tuple(records)


def _parse_datetime(value: object, name: str) -> datetime:
    """Parse and require a timezone-aware ISO timestamp."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset")
    return parsed


def _parse_parameter(
    parameters: dict[str, object], name: str, expected_length: int
) -> tuple[float | None, ...]:
    """Validate one required parameter and return normalized values."""
    parameter = parameters[name]
    if not isinstance(parameter, dict):
        raise ValueError(f"parameter {name} must be an object")
    if parameter.get("unit") != EXPECTED_UNITS[name]:
        raise ValueError(f"parameter {name} has an unexpected unit")
    data = parameter.get("data")
    if not isinstance(data, list) or len(data) != expected_length:
        raise ValueError(f"parameter {name} data length does not match timestamps")
    return tuple(_optional_number(value, name) for value in data)


def _optional_number(value: object, name: str) -> float | None:
    """Return a finite number or preserve an explicit null."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"parameter {name} values must be numbers or null")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"parameter {name} values must be finite")
    return parsed


def _wind(
    wind_u: float | None, wind_v: float | None
) -> tuple[float | None, float | None]:
    """Return native wind speed and meteorological direction from components."""
    if wind_u is None or wind_v is None:
        return None, None
    if (speed := math.hypot(wind_u, wind_v)) == 0:
        return 0.0, None
    bearing = (270.0 - math.degrees(math.atan2(wind_v, wind_u))) % 360.0
    return speed, bearing

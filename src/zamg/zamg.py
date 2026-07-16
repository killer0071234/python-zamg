"""GeoSphere Austria Weather Data Client."""  # fmt: skip
from __future__ import annotations

import json
import zoneinfo
from datetime import datetime, timedelta
from sys import version_info

import aiohttp
import async_timeout
from aiohttp.client_exceptions import (
    ClientConnectorError,
    ServerDisconnectedError,
    ServerTimeoutError,
)
from aiohttp.hdrs import USER_AGENT

from . import __version__
from .exceptions import (
    ZamgApiError,
    ZamgNoDataError,
    ZamgStationNotFoundError,
    ZamgStationUnknownError,
)

CLIENT_AGENT = f"Python/{version_info[0]}.{version_info[1]} +https://github.com/killer0071234/python-zamg python-zamg/{__version__}"


class ZamgData:
    """The class for handling the data retrieval."""

    dataset_metadata_url: str = (
        "https://dataset.api.hub.geosphere.at/v1/station/current/tawes-v1-10min/metadata"
    )
    """API url to fetch possible stations and parameters."""
    dataset_data_url: str = (
        "https://dataset.api.hub.geosphere.at/v1/station/current/tawes-v1-10min?parameters="
    )
    """API url to fetch current conditions of a weather station."""
    forecast_metadata_url: str = (
        "https://dataset.api.hub.geosphere.at/v1/grid/forecast/nwp-v1-1h-2500m/metadata"
    )
    """API url to fetch possible stations and parameters."""
    forecast_url: str = (
        "https://dataset.api.hub.geosphere.at/v1/timeseries/forecast/nwp-v1-1h-2500m?parameters="
    )
    """API url to fetch current conditions of a weather station."""
    request_timeout: float = 8.0
    headers = {
        USER_AGENT: CLIENT_AGENT,
    }
    session: aiohttp.client.ClientSession | None = None
    _close_session: bool = False
    verify_ssl: bool | None = None
    """Set to False to ignore SSL errors."""
    station_parameters: str | None = None
    forecast_parameters: str | None = None
    """Comma separated list of station parameter to get from GeoSphere Austria."""
    _timestamp: str | None = None
    _timestamp_forecast: str | None = None
    _station_id: str = ""
    _all_station_parameters: str | None = None
    """Comma separated list of all possible station parameters."""
    _stations: tuple | None = None

    def __init__(
        self,
        default_station_id: str = "",
        session: aiohttp.client.ClientSession | None = None,
    ):
        """Initialize the api client."""
        self.data = {}
        self.data_forecast = {}
        self._station_id = default_station_id
        self.session = session

    def get_forecast_current(
        self,
        forecast_data: dict | None = None,
        parameters: tuple[str, ...] = ("t2m", "rh2m", "u10m", "v10m", "tcc", "rr_acc"),
    ) -> dict:
        """Return selected forecast parameters for the current/next timestamp.

        If there is no timestamp equal to "now", the next available one is used.
        """
        try:
            data = forecast_data if forecast_data is not None else self.data_forecast
            timestamps = data["timestamps"]
            parsed_timestamps = [
                datetime.strptime(timestamp, "%Y-%m-%dT%H:%M%z")
                for timestamp in timestamps
            ]

            now_utc = datetime.utcnow().replace(
                tzinfo=zoneinfo.ZoneInfo("UTC"), second=0, microsecond=0
            )
            index = next(
                (
                    idx
                    for idx, timestamp in enumerate(parsed_timestamps)
                    if timestamp >= now_utc
                ),
                len(parsed_timestamps) - 1,
            )

            forecast_parameters = data["features"][0]["properties"]["parameters"]

            result = {
                "reference_time": data.get("reference_time"),
                "timestamp": timestamps[index],
            }
            for parameter in parameters:
                result[parameter] = forecast_parameters[parameter]["data"][index]

            # Derive hourly rain from accumulated precipitation.
            prev_index = max(index - 1, 0)
            rr_acc = forecast_parameters["rr_acc"]["data"][index]
            rr_acc_prev = forecast_parameters["rr_acc"]["data"][prev_index]
            result["rr_acc_prev"] = rr_acc_prev
            rain = round(rr_acc - rr_acc_prev, 3)
            result["rain"] = rain if rain >= 0 else rr_acc
            # Calculate wind speed from u10m and v10m components.
            u10m = forecast_parameters["u10m"]["data"][index]
            v10m = forecast_parameters["v10m"]["data"][index]
            wind_speed = round(
                (u10m**2 + v10m**2) ** 0.5 * 3.6, 1
            )  # Convert from m/s to km/h
            result["wind_speed"] = wind_speed

            return result
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            raise ZamgNoDataError(exc) from exc

    def _get_forecast_from_now(self, forecast_data: dict | None = None) -> dict:
        """Return forecast payload trimmed to timestamps from now onward."""
        try:
            data = forecast_data if forecast_data is not None else self.data_forecast
            timestamps = data["timestamps"]
            parsed_timestamps = [
                datetime.strptime(timestamp, "%Y-%m-%dT%H:%M%z")
                for timestamp in timestamps
            ]

            now_utc = datetime.utcnow().replace(
                tzinfo=zoneinfo.ZoneInfo("UTC"), second=0, microsecond=0
            )
            index = next(
                (
                    idx
                    for idx, timestamp in enumerate(parsed_timestamps)
                    if timestamp >= now_utc
                ),
                len(parsed_timestamps) - 1,
            )

            trimmed_data = dict(data)
            trimmed_data["timestamps"] = timestamps[index:]

            trimmed_features = []
            for feature in data["features"]:
                trimmed_feature = dict(feature)
                properties = dict(feature["properties"])
                parameters = properties["parameters"]
                trimmed_parameters = {}

                for parameter_name, parameter_values in parameters.items():
                    trimmed_parameter_values = dict(parameter_values)
                    trimmed_parameter_values["data"] = parameter_values["data"][index:]
                    trimmed_parameters[parameter_name] = trimmed_parameter_values

                # Derive rain and wind_speed for each remaining forecast step.
                rr_acc_data = parameters["rr_acc"]["data"]
                rain_data = []
                for idx in range(index, len(rr_acc_data)):
                    prev_idx = max(idx - 1, 0)
                    rr_acc = rr_acc_data[idx]
                    rr_acc_prev = rr_acc_data[prev_idx]
                    rain = round(rr_acc - rr_acc_prev, 3)
                    rain_data.append(rain if rain >= 0 else rr_acc)
                trimmed_parameters["rain"] = {
                    "name": "hourly rain",
                    "unit": "kg m-2",
                    "data": rain_data,
                }

                u10m_data = parameters["u10m"]["data"]
                v10m_data = parameters["v10m"]["data"]
                wind_speed_data = [
                    round((u10m_data[idx] ** 2 + v10m_data[idx] ** 2) ** 0.5 * 3.6, 1)
                    for idx in range(index, len(u10m_data))
                ]
                trimmed_parameters["wind_speed"] = {
                    "name": "10m wind speed",
                    "unit": "km h-1",
                    "data": wind_speed_data,
                }

                properties["parameters"] = trimmed_parameters
                trimmed_feature["properties"] = properties
                trimmed_features.append(trimmed_feature)

            trimmed_data["features"] = trimmed_features
            return trimmed_data
        except (TypeError, ValueError, KeyError, IndexError) as exc:
            raise ZamgNoDataError(exc) from exc

    async def zamg_stations(self) -> dict[str:(float, float, str)]:
        """Return {station_id: (lat, lon, name)} for all public data stations.
        In addition we also get all possible readable parameters for a station."""

        def _to_float(val: str) -> str | float:
            try:
                return float(val.replace(",", "."))
            except ValueError:
                return val

        if self._stations is not None:
            return self._stations

        try:
            if self.session is None:
                self.session = aiohttp.client.ClientSession()
                self._close_session = True

            async with async_timeout.timeout(self.request_timeout):
                response = await self.session.get(
                    url=self.forecast_metadata_url,
                    allow_redirects=True,
                    headers=self.headers,
                    verify_ssl=self.verify_ssl,
                )
            if response.status in (200, 301):
                contents = await response.read()
                response.close()
                self._forecast_metadata = json.loads(contents)
                # extract all possible parameters
                parameter_list = json.loads(contents)["parameters"]
                station_parameters = ""
                for parameter in parameter_list:
                    station_parameters += parameter["name"] + ","
                station_parameters = station_parameters.rstrip(station_parameters[-1])
                self._all_forecast_parameters = station_parameters
                # also set default station parameter to read
                if self.forecast_parameters is None:
                    self.forecast_parameters = station_parameters

            async with async_timeout.timeout(self.request_timeout):
                response = await self.session.get(
                    url=self.dataset_metadata_url,
                    allow_redirects=True,
                    headers=self.headers,
                    verify_ssl=self.verify_ssl,
                )
            if response.status in (200, 301):
                contents = await response.read()
                response.close()
                # extract all possible parameters
                parameter_list = json.loads(contents)["parameters"]
                station_parameters = ""
                for parameter in parameter_list:
                    station_parameters += parameter["name"] + ","
                station_parameters = station_parameters.rstrip(station_parameters[-1])
                self._all_station_parameters = station_parameters
                # also set default station parameter to read
                if self.station_parameters is None:
                    self.station_parameters = station_parameters
                # extract all stations out of parameters
                station_list = json.loads(contents)["stations"]
                stations = {}
                for station in station_list:
                    stations[station["id"]] = tuple(
                        _to_float(str(station[coord]))
                        for coord in ("lat", "lon", "name")
                    )
                self._stations = stations
                return stations

        except (
            ClientConnectorError,
            ServerTimeoutError,
            ServerDisconnectedError,
        ) as exc:
            raise ZamgApiError(exc) from exc
        except ValueError as exc:
            raise ZamgNoDataError(exc) from exc

    @property
    def forecast_metadata(self) -> list[str]:
        return self._forecast_metadata

    async def closest_station(self, lat: float, lon: float) -> str:
        """Return the station_id of the closest station to our lat/lon."""

        try:
            stations = await self.zamg_stations()

            def _comparable_dist(zamg_id):
                """Calculate the pseudo-distance from lat/lon."""
                station_lat, station_lon, _ = stations[zamg_id]
                return (lat - station_lat) ** 2 + (lon - station_lon) ** 2

            self._station_id = min(stations, key=_comparable_dist)
            return self._station_id
        except (KeyError, TypeError, ValueError) as exc:
            raise ZamgStationNotFoundError(exc) from exc

    def get_data(self, parameter: str, data_type: str = "data") -> str | None:
        """Get a specific data entry.
        To get possible parameters use get_all_parameters()
        Possible data_types:
        - data: default, data value of parameter
        - name: name of parameter
        - unit: data value unit of parameter"""
        try:
            return self.data[self._station_id][parameter][data_type]
        except KeyError as exc:
            raise ZamgNoDataError(exc) from exc

    def get_all_parameters(self) -> list[str]:
        """Get a list of all possible Parameters which can be read from GeoSphere Austria."""
        if self._all_station_parameters is None:
            return {}
        return self._all_station_parameters.split(",")

    def get_parameters(self) -> list[str]:
        """Get a list of parameters which are read from GeoSphere Austria.
        The returned list are possible data_type parameter for function get_data()"""
        if self.station_parameters is None:
            return {}
        return self.station_parameters.split(",")

    def set_parameters(self, param: list[str]) -> None:
        """Set the list of parameters to read with uodate() function from GeoSphere Austria."""
        station_parameters = ""
        for parameter in param:
            station_parameters += parameter + ","
        self.station_parameters = station_parameters.rstrip(station_parameters[-1])

    def get_forecast_all_parameters(self) -> list[str]:
        """Get a list of all possible Parameters which can be read from GeoSphere Austria."""
        if self._all_forecast_parameters is None:
            return {}
        return self._all_forecast_parameters.split(",")

    def get_forecast_parameters(self) -> list[str]:
        """Get a list of parameters which are read from GeoSphere Austria.
        The returned list are possible data_type parameter for function get_data()"""
        if self.forecast_parameters is None:
            return {}
        return self.forecast_parameters.split(",")

    def set_forecast_parameters(self, param: list[str]) -> None:
        """Set the list of parameters to read with uodate() function from GeoSphere Austria."""
        forecast_parameters = ""
        for parameter in param:
            forecast_parameters += parameter + ","
        self.forecast_parameters = forecast_parameters.rstrip(forecast_parameters[-1])

    @property
    def get_station_name(self) -> str:
        """Return the current Station name."""
        try:
            _, _, name = self._stations[self._station_id]
            return name
        except (KeyError, TypeError) as exc:
            raise ZamgStationUnknownError(exc) from exc

    def set_default_station(self, station_id: str):
        """Set the default station_id for update()."""
        self._station_id = station_id

    @property
    def last_update(self) -> datetime | None:
        """Return the timestamp of the most recent data."""
        if self._timestamp is not None:
            return datetime.strptime(self._timestamp, "%Y-%m-%dT%H:%M%z")
        return None

    @property
    def last_forecast_update(self) -> datetime | None:
        """Return the timestamp of the most recent data."""
        if self._timestamp_forecast is not None:
            return datetime.strptime(self._timestamp_forecast, "%Y-%m-%dT%H:%M%z")
        return None

    async def update(self) -> dict | None:
        """Return a list of all current observations of the default station id."""
        if self._station_id == "":
            return None
        if self.last_update and (
            self.last_update + timedelta(minutes=5)
            > datetime.utcnow().replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        ):
            return (
                self.data
            )  # Not time to update yet; we are just reading every 5 minutes
        try:
            # initialize station parameters
            if self.station_parameters is None:
                await self.zamg_stations()
            if self.station_parameters is None:
                raise ZamgApiError(
                    "Failed to initialize station parameters from metadata"
                )

            if self.session is None:
                self.session = aiohttp.client.ClientSession()
                self._close_session = True

            async with async_timeout.timeout(self.request_timeout):
                response = await self.session.get(
                    url=self.dataset_data_url
                    + str(self.station_parameters)
                    + "&station_ids="
                    + str(self._station_id),
                    allow_redirects=True,
                    headers=self.headers,
                    verify_ssl=self.verify_ssl,
                )
            if response.status in (200, 301):
                contents = await response.read()
                response.close()

                observations = json.loads(contents)["features"][0]["properties"][
                    "parameters"
                ]

                self._timestamp = json.loads(contents)["timestamps"][0]

                self.data[self._station_id] = dict(observations)

                for observation in observations:
                    # hack to put data into one single slot, maybe there are easier solutions, but hey it works ;-)
                    self.data[self._station_id][observation]["data"] = self.data[
                        self._station_id
                    ][observation]["data"][0]

                return self.data
            raise ZamgApiError(f"Got status {response.status} from GeoSphere Austria")
        except (ClientConnectorError, ServerTimeoutError, ZamgApiError) as exc:
            raise ZamgApiError(exc) from exc
        except (TypeError, ValueError, KeyError) as exc:
            raise ZamgNoDataError(exc) from exc

    async def get_forecast(
        self, lat_lon: str, current_only: bool = False
    ) -> dict | None:
        """Return a list of all current observations of the default station id."""
        if self.last_forecast_update and (
            self.last_forecast_update + timedelta(minutes=5)
            > datetime.utcnow().replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        ):
            if current_only:
                return self.get_forecast_current()
            return (
                self._get_forecast_from_now()
            )  # Not time to update yet; we are just reading every 5 minutes
        try:

            if self.session is None:
                self.session = aiohttp.client.ClientSession()
                self._close_session = True

            async with async_timeout.timeout(self.request_timeout):
                forecast_params = (
                    self.forecast_parameters or "t2m,rr_acc,u10m,v10m,tcc,rh2m"
                )
                response = await self.session.get(
                    url=self.forecast_url + forecast_params + "&lat_lon=" + lat_lon,
                    allow_redirects=True,
                    headers=self.headers,
                    verify_ssl=self.verify_ssl,
                )
            if response.status in (200, 301):
                contents = await response.read()
                response.close()

                self.data_forecast = json.loads(contents)
                self._timestamp_forecast = (
                    datetime.utcnow()
                    .replace(tzinfo=zoneinfo.ZoneInfo("UTC"), second=0, microsecond=0)
                    .strftime("%Y-%m-%dT%H:%M%z")
                )
                if current_only:
                    return self.get_forecast_current()
                return self._get_forecast_from_now()

            raise ZamgApiError(f"Got status {response.status} from GeoSphere Austria")
        except (ClientConnectorError, ServerTimeoutError, ZamgApiError) as exc:
            raise ZamgApiError(exc) from exc
        except (TypeError, ValueError, KeyError) as exc:
            raise ZamgNoDataError(exc) from exc

    async def __aenter__(self) -> ZamgData:
        """Async enter.

        Returns:
            The GeoSphere Austria object.
        """
        return self

    async def __aexit__(self, *_exc_info) -> None:
        """Async exit.

        Args:
            _exc_info: Exec type.
        """
        if self.session is not None and self._close_session:
            await self.session.close()
            self.session = None

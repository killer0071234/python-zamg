"""Zamg Weather Data Client."""
from __future__ import annotations

import json
import zoneinfo
from datetime import datetime
from datetime import timedelta

import aiohttp
import async_timeout
from aiohttp.client_exceptions import ClientConnectorError
from aiohttp.client_exceptions import ServerTimeoutError
from aiohttp.hdrs import USER_AGENT


class ZamgData:
    """The class for handling the data retrieval."""

    dataset_metadata_url: str = (
        "https://dataset.api.hub.zamg.ac.at/v1/station/current/tawes-v1-10min/metadata"
    )
    """API url to fetch possible stations and parameters."""
    dataset_data_url: str = "https://dataset.api.hub.zamg.ac.at/v1/station/current/tawes-v1-10min?parameters="
    """API url to fetch current conditions of a weather station."""
    request_timeout: float = 8.0
    headers = {
        USER_AGENT: "python-zamg",
    }
    session: aiohttp.client.ClientSession | None = None
    _timestamp: str | None = None
    _station_id: str = ""
    _station_parameters: str | None = None
    _stations: tuple | None = None

    def __init__(
        self,
        default_station_id: str = "",
        session: aiohttp.client.ClientSession | None = None,
    ):
        """Initialize the api client."""
        self.data = {}
        self._station_id = default_station_id
        self.session = session

    async def zamg_stations(self) -> dict[str:(float, float, str)]:
        """Return {station_id: (lat, lon, name)} for all public data stations."""

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

            async with async_timeout.timeout(self.request_timeout):
                response = await self.session.get(
                    url=self.dataset_metadata_url,
                    allow_redirects=False,
                    headers=self.headers,
                )
            if response.status == 200:
                contents = await response.read()
                response.close()
                # extract all possible parameters
                parameter_list = json.loads(contents)["parameters"]
                station_parameters = ""
                for parameter in parameter_list:
                    station_parameters += parameter["name"] + ","
                station_parameters = station_parameters.rstrip(station_parameters[-1])
                self._station_parameters = station_parameters
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

        except (ClientConnectorError, ServerTimeoutError, ValueError):
            if self.session is not None:
                await self.session.close()
                self.session = None
            return {"0": (0.0, 0.0, "None")}

    async def closest_station(self, lat: float, lon: float) -> str:
        """Return the station_id of the closest station to our lat/lon."""
        if lat is None or lon is None:
            return ""

        if (stations := await self.zamg_stations()) is None:
            return ""

        def _comparable_dist(zamg_id):
            """Calculate the pseudo-distance from lat/lon."""
            station_lat, station_lon, _ = stations[zamg_id]
            return (lat - station_lat) ** 2 + (lon - station_lon) ** 2

        self._station_id = min(stations, key=_comparable_dist)
        return self._station_id

    def get_data(self, parameter: str, data_type: str = "data") -> str | None:
        """Get a specific data entry.
        To get possible parameters use get_all_parameters()
        Possible data_types:
        - data: default, data value of parameter
        - name: name of parameter
        - unit: data value unit of parameter"""
        try:
            return self.data[self._station_id][parameter][data_type]
        except (KeyError):
            return None

    def get_all_parameters(self) -> list[str]:
        """Get a list of all possible Parameters.
        The returned list are possible data_type parameter for function get_data()"""
        if self._station_parameters is None:
            return {}
        return self._station_parameters.split(",")

    @property
    def get_station_name(self) -> str:
        """Return the current Station name."""
        try:
            _, _, name = self._stations[self._station_id]
            return name
        except (KeyError, TypeError):
            return f"Unknown station with id: {self._station_id}"

    def set_default_station(self, station_id: str):
        """Set the default station_id for update()."""
        self._station_id = station_id

    @property
    def last_update(self) -> datetime | None:
        """Return the timestamp of the most recent data."""
        if self._timestamp is not None:
            return datetime.strptime(
                self._timestamp, "%Y-%m-%dT%H:%M:%S+00:00"
            ).replace(tzinfo=zoneinfo.ZoneInfo("Europe/Vienna"))
        return None

    async def update(self) -> dict | None:
        """Return a list of all current observations of the default station id."""
        if self._station_id is None:
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
            if self._station_parameters is None:
                await self.zamg_stations()

            if self.session is None:
                self.session = aiohttp.client.ClientSession()

            async with async_timeout.timeout(self.request_timeout):
                response = await self.session.get(
                    url=self.dataset_data_url
                    + self._station_parameters
                    + "&station_ids="
                    + str(self._station_id),
                    allow_redirects=False,
                    headers=self.headers,
                )
            if response.status == 200:
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
        except (ClientConnectorError, ServerTimeoutError, TypeError, ValueError):
            if self.session is not None:
                await self.session.close()
                self.session = None
            return {}

    async def __aenter__(self) -> ZamgData:
        """Async enter.

        Returns:
            The ZAMG object.
        """
        return self

    async def __aexit__(self, *_exc_info) -> None:
        """Async exit.

        Args:
            _exc_info: Exec type.
        """
        if self.session is not None:
            await self.session.close()
            self.session = None

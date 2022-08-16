"""Zamg Weather Data Client."""
from __future__ import annotations

import csv
import gzip
import json
import os
import zoneinfo
from datetime import datetime
from datetime import timedelta

import aiohttp
import async_timeout
from aiohttp.hdrs import USER_AGENT


class ZamgData:
    """The class for handling the data retrieval."""

    api_url: str = "https://www.zamg.ac.at/ogd/"
    """API url to fetch hourly condiotions."""
    api_station_url: str = "https://www.zamg.ac.at/cms/de/dokumente/klima/dok_messnetze/Stationsliste_20220101.csv"
    """API url to get a list of all possible stations."""
    request_timeout: float = 8.0
    headers = {
        USER_AGENT: "python-zamg",
    }
    session: aiohttp.client.ClientSession | None = None
    _update_date: str | None = None
    _update_time: str | None = None
    _station_id: str = ""

    def __init__(
        self,
        default_station_id: str = "",
        session: aiohttp.client.ClientSession | None = None,
    ):
        """Initialize the probe."""
        self.data = {}
        self._station_id = default_station_id
        self.session = session

    async def zamg_stations(self, cache_dir: str = ""):
        """Return {station_id: (lat, lon, name)} for all public data stations.

        Results from internet requests are cached as compressed json, making
        subsequent calls very much faster.
        """
        cache_file = os.path.join(cache_dir, ".zamg-stations_20220101.json.gz")
        if os.path.isfile(cache_file):
            try:
                with gzip.open(cache_file, "rt") as cache:
                    station_list = {k: tuple(v) for k, v in json.load(cache).items()}
                    for station in station_list:
                        if len(station) != 3:
                            raise ValueError(
                                "old cache file found, reloading from zamg"
                            )
                    return station_list
            except (ValueError):
                os.remove(cache_file)
        if not os.path.isfile(cache_file):
            stations = await self._get_zamg_stations()
            with gzip.open(cache_file, "wt") as cache:
                json.dump(stations, cache, sort_keys=True)
            return stations
        with gzip.open(cache_file, "rt") as cache:
            return {k: tuple(v) for k, v in json.load(cache).items()}

    async def closest_station(self, lat: float, lon: float, cache_dir: str = ""):
        """Return the station_id of the closest station to our lat/lon."""
        if lat is None or lon is None or not os.path.isdir(cache_dir):
            return
        stations = await self.zamg_stations(cache_dir)

        def comparable_dist(zamg_id):
            """Calculate the pseudo-distance from lat/lon."""
            station_lat, station_lon, _ = stations[zamg_id]
            return (lat - station_lat) ** 2 + (lon - station_lon) ** 2

        return min(stations, key=comparable_dist)

    def get_data(self, variable: str, station_id: str | None = None):
        """Get the data."""
        try:

            return self.data[station_id if station_id else self._station_id][variable]
        except (KeyError):
            return None

    def set_default_station(self, station_id: str):
        """Set the default station_id for get_data(), if there is no one given."""
        self._station_id = station_id

    @property
    def last_update(self) -> datetime | None:
        """Return the timestamp of the most recent data."""
        if self._update_date is not None and self._update_time is not None:
            return datetime.strptime(
                self._update_date + self._update_time, "%d-%m-%Y%H:%M"
            ).replace(tzinfo=zoneinfo.ZoneInfo("Europe/Vienna"))
        return None

    async def update(self):
        """Return a list of all current observations."""
        if self.last_update and (
            self.last_update + timedelta(hours=1)
            > datetime.utcnow().replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        ):
            return self.data  # Not time to update yet; data is only hourly
        try:
            if self.session is None:
                self.session = aiohttp.client.ClientSession()

            async with async_timeout.timeout(self.request_timeout):
                response = await self.session.get(
                    url=self.api_url,
                    allow_redirects=False,
                    headers=self.headers,
                )
            if response.status == 200:
                contents = await response.read()
                response.close()
                dat = csv.DictReader(
                    contents.decode("utf8").splitlines(), delimiter=";", quotechar='"'
                )
                for row in dat:
                    self.data[row.get("Station")] = dict(row.items())
                    self._update_date = row.get("Datum")
                    self._update_time = row.get("Zeit")
                return self.data
        except (ValueError):
            if self.session is not None:
                await self.session.close()
                self.session = None
            return None

    async def _get_ogd_stations(self):
        """Return all station IDs in the OGD dataset."""
        return set(await self.update())

    async def _get_zamg_stations(self):
        """Return {station_id: (lat, lon, name)} for all public data stations."""
        capital_stations = await self._get_ogd_stations()

        def to_float(val: str):
            try:
                return float(val.replace(",", "."))
            except ValueError:
                return val

        try:
            if self.session is None:
                self.session = aiohttp.client.ClientSession()

            async with async_timeout.timeout(self.request_timeout):
                response = await self.session.get(
                    url=self.api_station_url,
                    allow_redirects=False,
                    headers=self.headers,
                )

            if response.status == 200:
                contents = await response.read()
                response.close()
                dat = csv.DictReader(
                    contents.decode("iso-8859-1").splitlines(),
                    delimiter=";",
                    quotechar='"',
                )
                stations = {}
                for row in dat:

                    if row.get("SYNNR") in capital_stations:
                        stations[row["SYNNR"]] = tuple(
                            to_float(row[coord])
                            for coord in ("BREITE DEZI", "LÄNGE DEZI", "NAME")
                        )
                return stations
        except (ValueError):
            if self.session is not None:
                await self.session.close()
                self.session = None
            return None

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

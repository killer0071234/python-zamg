"""Tests GeoSphere Austria."""  # fmt: skip
import json
import pathlib
import zoneinfo
from datetime import datetime, timedelta

import aiohttp
import pytest
from aiohttp.client_exceptions import ServerTimeoutError

from src.zamg.exceptions import (
    ZamgApiError,
    ZamgNoDataError,
    ZamgStationNotFoundError,
    ZamgStationUnknownError,
)
from src.zamg.zamg import ZamgData


@pytest.mark.asyncio
async def test_update(fix_data, fix_metadata) -> None:
    """Test update function."""

    zamg = ZamgData()
    zamg.set_default_station("11240")
    await zamg.update()
    # picking few values to compare
    assert zamg.get_data("TL") == 8.6
    assert zamg.get_data("P") == 987.3


@pytest.mark.asyncio
async def test_update_twice(fix_data, fix_metadata) -> None:
    """Test update function with short interval."""

    zamg = ZamgData()
    zamg.set_default_station("11240")
    await zamg.update()
    zamg._timestamp = (
        datetime.utcnow()
        .replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
        .strftime("%Y-%m-%dT%H:%M%z")
    )
    await zamg.update()
    # picking few values to compare
    assert zamg.get_data("TL") == 8.6
    assert zamg.get_data("P") == 987.3


@pytest.mark.asyncio
async def test_update_aenter(fix_data, fix_metadata) -> None:
    """Test update function."""

    async with ZamgData(session=aiohttp.client.ClientSession()) as zamg:
        zamg.set_default_station("11240")
        zamg._close_session = True


@pytest.mark.asyncio
async def test_update_aenter_session(fix_data, fix_metadata) -> None:
    """Test update function."""

    async with ZamgData() as zamg:
        zamg.set_default_station("11240")


@pytest.mark.asyncio
async def test_update_fixed_param(fix_data) -> None:
    """Test update function."""

    zamg = ZamgData()
    zamg.set_default_station("11240")
    zamg.set_parameters(["P"])
    await zamg.update()
    assert zamg.get_data("P") == 987.3


@pytest.mark.asyncio
async def test_update_fail(aresponses) -> None:
    """Test update function."""
    aresponses.add(
        "dataset.api.hub.geosphere.at",
        "/v1/station/current/tawes-v1-10min",
        "GET",
        aresponses.Response(text="error", status=500),
    )
    zamg = ZamgData()
    zamg.set_default_station("11240")
    zamg.set_parameters(["P"])
    with pytest.raises(ZamgApiError):
        await zamg.update()


@pytest.mark.asyncio
async def test_update_fail_1(aresponses) -> None:
    """Test update function."""
    aresponses.add(
        "dataset.api.hub.geosphere.at",
        "/v1/station/current/tawes-v1-10min",
        "GET",
        aresponses.Response(text="error", status=500),
    )
    zamg = ZamgData(session=aiohttp.client.ClientSession())
    zamg.set_default_station("11240")
    zamg.set_parameters(["P"])
    with pytest.raises(ZamgApiError):
        await zamg.update()


@pytest.mark.asyncio
async def test_update_fail_2(aresponses) -> None:
    """Test update function."""
    aresponses.add(
        "dataset.api.hub.geosphere.at",
        "/v1/station/current/tawes-v1-10min",
        "GET",
        aresponses.Response(text="{}", status=200),
    )
    zamg = ZamgData(session=aiohttp.client.ClientSession())
    zamg.set_default_station("11240")
    zamg.set_parameters(["P"])
    with pytest.raises(ZamgNoDataError):
        await zamg.update()


@pytest.mark.asyncio
async def test_update_fail_3(aresponses) -> None:
    """Test update function."""
    aresponses.add(
        "dataset.api.hub.geosphere.at",
        "/v1/station/current/tawes-v1-10min",
        "GET",
        aresponses.Response(text="{}", status=200),
    )
    zamg = ZamgData(session=aiohttp.client.ClientSession())
    zamg.set_default_station("11240")
    with pytest.raises(ZamgApiError):
        await zamg.update()


@pytest.mark.asyncio
async def test_properties(fix_metadata) -> None:
    """Test getting properties."""

    zamg = ZamgData()
    await zamg.zamg_stations()
    stations = await zamg.zamg_stations()
    # check that we get at least one correct station
    assert stations.get("11240") == (
        46.980555555555554,
        15.44,
        "GRAZ-THALERHOF-FLUGHAFEN",
    )


@pytest.mark.asyncio
async def test_properties_pre_loaded(fix_metadata) -> None:
    """Test getting properties."""

    zamg = ZamgData()
    zamg.set_parameters(["TL"])
    await zamg.zamg_stations()
    stations = await zamg.zamg_stations()
    # check that we get at least one correct station
    assert stations.get("11240") == (
        46.980555555555554,
        15.44,
        "GRAZ-THALERHOF-FLUGHAFEN",
    )


@pytest.mark.asyncio
async def test_properties_fail_1(aresponses) -> None:
    """Test getting properties."""
    aresponses.add(
        "dataset.api.hub.geosphere.at",
        "/v1/station/current/tawes-v1-10min/metadata",
        "GET",
        response=aresponses.Response(text="", status=404),
    )

    zamg = ZamgData(session=aiohttp.client.ClientSession())
    stations = await zamg.zamg_stations()
    assert stations is None


@pytest.mark.asyncio
async def test_properties_fail_2() -> None:
    """Test getting properties."""

    class TimeoutSession:
        async def get(self, **_kwargs):
            raise ServerTimeoutError()

    zamg = ZamgData(session=TimeoutSession())
    with pytest.raises(ZamgApiError):
        await zamg.zamg_stations()


@pytest.mark.asyncio
async def test_properties_fail_3(aresponses) -> None:
    """Test getting properties."""
    aresponses.add(
        "dataset.api.hub.geosphere.at",
        "/v1/station/current/tawes-v1-10min/metadata",
        "GET",
        response=aresponses.Response(text=""),
    )

    zamg = ZamgData(session=aiohttp.client.ClientSession())
    with pytest.raises(ZamgNoDataError):
        await zamg.zamg_stations()


@pytest.mark.asyncio
async def test_properties_fail_4(fix_metadata) -> None:
    """Test getting properties."""

    zamg = ZamgData()
    await zamg.zamg_stations()
    with pytest.raises(ZamgNoDataError):
        zamg.get_data("not_in_list")


def test_get_all_parameters_empty() -> None:
    """Test getting get_all_parameters is empty."""

    zamg = ZamgData()
    assert zamg.get_all_parameters() == {}


def test_get_parameters_empty() -> None:
    """Test getting get_parameters is empty."""

    zamg = ZamgData()
    assert zamg.get_parameters() == {}


@pytest.mark.asyncio
async def test_get_all_parameters(fix_metadata) -> None:
    """Test getting get_all_parameters."""

    zamg = ZamgData()
    await zamg.zamg_stations()
    params = zamg.get_all_parameters()

    in_list = False
    if "TL" in params:
        in_list = True
    assert in_list is True


@pytest.mark.asyncio
async def test_get_parameters(fix_metadata) -> None:
    """Test getting get_parameters."""

    zamg = ZamgData()
    await zamg.zamg_stations()
    params = zamg.get_parameters()

    in_list = False
    if "TL" in params:
        in_list = True
    assert in_list is True


@pytest.mark.asyncio
async def test_closest_station(fix_metadata) -> None:
    """Test getting closest station."""

    zamg = ZamgData()
    station = await zamg.closest_station(46.9, 15.4)
    assert station == "11240"


@pytest.mark.asyncio
async def test_closest_station_not_found(aresponses) -> None:
    """Test getting closest station."""
    aresponses.add(
        "dataset.api.hub.geosphere.at",
        "/v1/station/current/tawes-v1-10min/metadata",
        "GET",
        response={"title": "TAWES", "stations": []},
    )

    zamg = ZamgData()
    with pytest.raises(ZamgStationNotFoundError):
        await zamg.closest_station(46.9, 15.4)


@pytest.mark.asyncio
async def test_get_station_name(fix_metadata) -> None:
    """Test getting get_station_name."""

    zamg = ZamgData()
    await zamg.zamg_stations()
    zamg.set_default_station("11240")
    assert zamg.get_station_name == "GRAZ-THALERHOF-FLUGHAFEN"


@pytest.mark.asyncio
async def test_get_station_name_unknown(fix_metadata) -> None:
    """Test getting get_station_name."""

    zamg = ZamgData()
    await zamg.zamg_stations()
    with pytest.raises(ZamgStationUnknownError):
        _ = zamg.get_station_name


@pytest.mark.asyncio
async def test_get_station_location(fix_metadata) -> None:
    """Test getting get_station_location."""

    zamg = ZamgData()
    await zamg.zamg_stations()
    zamg.set_default_station("11240")
    assert zamg.get_station_location == (46.980555555555554, 15.44)


@pytest.mark.asyncio
async def test_get_station_location_unknown(fix_metadata) -> None:
    """Test getting get_station_location."""

    zamg = ZamgData()
    await zamg.zamg_stations()
    with pytest.raises(ZamgStationUnknownError):
        _ = zamg.get_station_location


@pytest.mark.asyncio
async def test_get_forecast_uses_station_location(aresponses) -> None:
    """Test get_forecast uses default station location when lat_lon isn't provided."""

    async with ZamgData() as zamg:
        zamg._stations = {
            "11240": (46.980555555555554, 15.44, "GRAZ-THALERHOF-FLUGHAFEN")
        }
        zamg.set_default_station("11240")

        now_utc = datetime.utcnow().replace(
            tzinfo=zoneinfo.ZoneInfo("UTC"), second=0, microsecond=0
        )
        timestamp = now_utc.strftime("%Y-%m-%dT%H:%M%z")

        aresponses.add(
            "dataset.api.hub.geosphere.at",
            "/v1/timeseries/forecast/nwp-v1-1h-2500m",
            "GET",
            response={
                "reference_time": timestamp,
                "timestamps": [timestamp],
                "features": [
                    {
                        "properties": {
                            "parameters": {
                                "t2m": {"data": [0.0]},
                                "rh2m": {"data": [0.0]},
                                "u10m": {"data": [0.0]},
                                "v10m": {"data": [0.0]},
                                "tcc": {"data": [0.0]},
                                "sy": {"data": [0.0]},
                                "rr_acc": {"data": [0.0]},
                            }
                        }
                    }
                ],
            },
        )

        result = await zamg.get_forecast(current_only=True)
        assert result["timestamp"] == timestamp


@pytest.mark.asyncio
async def test_last_update(fix_data, fix_metadata) -> None:
    """Test getting last_update."""

    zamg = ZamgData()
    zamg.set_default_station("11240")
    await zamg.update()
    assert zamg.last_update == datetime(
        2022, 11, 13, 10, 20, tzinfo=zoneinfo.ZoneInfo(key="UTC")
    )


@pytest.mark.asyncio
async def test_update_no_station(fix_data, fix_metadata) -> None:
    """Test getting update."""

    zamg = ZamgData()
    data = await zamg.update()
    assert data is None


def test_last_update_unknown() -> None:
    """Test getting last_update."""

    zamg = ZamgData()
    update = zamg.last_update
    assert update is None


def test_get_forecast_current() -> None:
    """Test extracting current forecast values."""

    zamg = ZamgData()
    now_utc = datetime.utcnow().replace(
        tzinfo=zoneinfo.ZoneInfo("UTC"), second=0, microsecond=0
    )
    timestamps = [
        (now_utc - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M%z"),
        (now_utc + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M%z"),
        (now_utc + timedelta(hours=1, minutes=1)).strftime("%Y-%m-%dT%H:%M%z"),
    ]
    forecast_data = {
        "reference_time": now_utc.strftime("%Y-%m-%dT%H:%M%z"),
        "timestamps": timestamps,
        "features": [
            {
                "properties": {
                    "parameters": {
                        "t2m": {"data": [10.0, 11.0, 12.0]},
                        "rh2m": {"data": [80.0, 81.0, 82.0]},
                        "u10m": {"data": [1.0, 2.0, 3.0]},
                        "v10m": {"data": [4.0, 5.0, 6.0]},
                        "tcc": {"data": [0.1, 0.2, 0.3]},
                        "sy": {"data": [1.0, 2.0, 3.0]},
                        "rr_acc": {"data": [0.5, 0.9, 1.4]},
                    }
                }
            }
        ],
    }

    result = zamg.get_forecast_current(forecast_data)

    assert result["timestamp"] == timestamps[1]
    assert result["t2m"] == 11.0
    assert result["rh2m"] == 81.0
    assert result["u10m"] == 2.0
    assert result["v10m"] == 5.0
    assert result["rain"] == 0.4


@pytest.mark.asyncio
async def test_get_forecast_trims_past_data() -> None:
    """Test get_forecast returns only timestamps from now onward."""

    zamg = ZamgData()
    now_utc = datetime.utcnow().replace(
        tzinfo=zoneinfo.ZoneInfo("UTC"), second=0, microsecond=0
    )
    timestamps = [
        (now_utc - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M%z"),
        (now_utc + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M%z"),
        (now_utc + timedelta(hours=1, minutes=1)).strftime("%Y-%m-%dT%H:%M%z"),
    ]

    zamg.data_forecast = {
        "reference_time": now_utc.strftime("%Y-%m-%dT%H:%M%z"),
        "timestamps": timestamps,
        "features": [
            {
                "properties": {
                    "parameters": {
                        "t2m": {"data": [10.0, 11.0, 12.0]},
                        "rh2m": {"data": [80.0, 81.0, 82.0]},
                        "u10m": {"data": [1.0, 2.0, 3.0]},
                        "v10m": {"data": [4.0, 5.0, 6.0]},
                        "tcc": {"data": [0.1, 0.2, 0.3]},
                        "rr_acc": {"data": [0.5, 0.9, 1.4]},
                    }
                }
            }
        ],
    }
    zamg._timestamp_forecast = now_utc.strftime("%Y-%m-%dT%H:%M%z")

    result = await zamg.get_forecast("46.99,15.499", current_only=False)

    assert result["timestamps"] == timestamps[1:]
    assert result["features"][0]["properties"]["parameters"]["t2m"]["data"] == [
        11.0,
        12.0,
    ]
    assert result["features"][0]["properties"]["parameters"]["rain"]["data"] == [
        0.4,
        0.5,
    ]
    assert result["features"][0]["properties"]["parameters"]["wind_speed"]["data"] == [
        19.4,
        24.1,
    ]


@pytest.fixture
def fix_metadata(aresponses):
    """Fixture to get metadata."""
    data_metadata = json.loads(
        pathlib.Path(__file__)
        .parent.joinpath("data_metadata.json")
        .read_text(encoding="utf-8")
    )
    aresponses.add(
        "dataset.api.hub.geosphere.at",
        "/v1/station/current/tawes-v1-10min/metadata",
        "GET",
        response=data_metadata,
    )


@pytest.fixture
def fix_data(aresponses):
    """Fixture to get data of a station."""
    data_station = json.loads(
        pathlib.Path(__file__)
        .parent.joinpath("data_station.json")
        .read_text(encoding="utf-8")
    )
    aresponses.add(
        "dataset.api.hub.geosphere.at",
        "/v1/station/current/tawes-v1-10min",
        "GET",
        response=data_station,
    )

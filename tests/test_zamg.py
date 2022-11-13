"""Tests Zamg."""
import json
import pathlib
import zoneinfo
from datetime import datetime

import aiohttp
import pytest
from aiohttp.client_exceptions import ClientConnectorError
from src.zamg.exceptions import ZamgApiError
from src.zamg.exceptions import ZamgNoDataError
from src.zamg.exceptions import ZamgStationNotFoundError
from src.zamg.exceptions import ZamgStationUnknownError
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
        "dataset.api.hub.zamg.ac.at",
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
        "dataset.api.hub.zamg.ac.at",
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
        "dataset.api.hub.zamg.ac.at",
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
        "dataset.api.hub.zamg.ac.at",
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
        "dataset.api.hub.zamg.ac.at",
        "/v1/station/current/tawes-v1-10min/metadata",
        "GET",
        response=aresponses.Response(text="", status=404),
    )

    zamg = ZamgData(session=aiohttp.client.ClientSession())
    stations = await zamg.zamg_stations()
    assert stations is None


@pytest.mark.asyncio
async def test_properties_fail_2(aresponses) -> None:
    """Test getting properties."""
    aresponses.side_effect = ClientConnectorError

    zamg = ZamgData(session=aiohttp.client.ClientSession())
    with pytest.raises(ZamgApiError):
        await zamg.zamg_stations()


@pytest.mark.asyncio
async def test_properties_fail_3(aresponses) -> None:
    """Test getting properties."""
    aresponses.add(
        "dataset.api.hub.zamg.ac.at",
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
        "dataset.api.hub.zamg.ac.at",
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
async def test_last_update(fix_data, fix_metadata) -> None:
    """Test getting last_update."""

    zamg = ZamgData()
    zamg.set_default_station("11240")
    await zamg.update()
    assert zamg.last_update == datetime(
        2022, 11, 13, 10, 20, tzinfo=zoneinfo.ZoneInfo(key="Europe/Vienna")
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


@pytest.fixture
def fix_metadata(aresponses):
    """Fixture to get metadata."""
    data_metadata = json.loads(
        pathlib.Path(__file__)
        .parent.joinpath("data_metadata.json")
        .read_text(encoding="utf-8")
    )
    aresponses.add(
        "dataset.api.hub.zamg.ac.at",
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
        "dataset.api.hub.zamg.ac.at",
        "/v1/station/current/tawes-v1-10min",
        "GET",
        response=data_station,
    )

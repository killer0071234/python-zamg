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
from src.zamg.symbols import symbol_to_condition, symbol_to_text
from src.zamg.zamg import ZamgData

API_HOST = "dataset.api.hub.geosphere.at"
STATION_METADATA_PATH = "/v1/station/current/tawes-v1-10min/metadata"
STATION_DATA_PATH = "/v1/station/current/tawes-v1-10min"
FORECAST_METADATA_PATH = "/v1/grid/forecast/nwp-v1-1h-2500m/metadata"
FORECAST_PATH = "/v1/timeseries/forecast/nwp-v1-1h-2500m"
GRAZ = (46.980555555555554, 15.44, "GRAZ-THALERHOF-FLUGHAFEN")


def _load_json(name: str) -> dict:
    """Load a JSON test fixture from the tests directory."""
    return json.loads(
        pathlib.Path(__file__).parent.joinpath(name).read_text(encoding="utf-8")
    )


def _forecast_payload(include_sy: bool = True) -> dict:
    """Build a forecast response with one past and two upcoming timestamps."""
    now_utc = datetime.now(zoneinfo.ZoneInfo("UTC")).replace(second=0, microsecond=0)
    timestamps = [
        (now_utc - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M%z"),
        (now_utc + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M%z"),
        (now_utc + timedelta(hours=1, minutes=1)).strftime("%Y-%m-%dT%H:%M%z"),
    ]
    parameters = {
        "t2m": {"data": [10.0, 11.0, 12.0]},
        "rh2m": {"data": [80.0, 81.0, 82.0]},
        "u10m": {"data": [1.0, 2.0, 3.0]},
        "v10m": {"data": [4.0, 5.0, 6.0]},
        "tcc": {"data": [0.1, 0.2, 0.3]},
        "sy": {"data": [1.0, 2.0, 3.0]},
        "rr_acc": {"data": [0.5, 0.9, 1.4]},
    }
    if not include_sy:
        del parameters["sy"]
    return {
        "reference_time": now_utc.strftime("%Y-%m-%dT%H:%M%z"),
        "timestamps": timestamps,
        "features": [{"properties": {"parameters": parameters}}],
    }


@pytest.mark.asyncio
async def test_update(fix_data, fix_metadata) -> None:
    """Test update function."""

    async with ZamgData() as zamg:
        zamg.set_default_station("11240")
        await zamg.update()
        # picking few values to compare
        assert zamg.get_data("TL") == 8.6
        assert zamg.get_data("P") == 987.3
        assert zamg.get_data("TL", data_type="unit") == "°C"


@pytest.mark.asyncio
async def test_update_twice(fix_data, fix_metadata) -> None:
    """Test a second update within 5 minutes returns cached data without a request."""

    async with ZamgData() as zamg:
        zamg.set_default_station("11240")
        await zamg.update()
        zamg._timestamp = datetime.now(zoneinfo.ZoneInfo("UTC")).strftime(
            "%Y-%m-%dT%H:%M%z"
        )
        # fix_data only answers once, so a second request would fail
        await zamg.update()
        assert zamg.get_data("TL") == 8.6
        assert zamg.get_data("P") == 987.3


@pytest.mark.asyncio
async def test_aexit_closes_own_session(fix_data) -> None:
    """Test the context manager closes a session it created itself."""

    async with ZamgData() as zamg:
        zamg.set_default_station("11240")
        zamg.set_parameters(["P"])
        await zamg.update()
        session = zamg.session
        assert session is not None
    assert session.closed
    assert zamg.session is None


@pytest.mark.asyncio
async def test_aexit_keeps_caller_session(fix_data) -> None:
    """Test the context manager leaves a caller-provided session open."""

    async with aiohttp.ClientSession() as session:
        async with ZamgData(session=session) as zamg:
            zamg.set_default_station("11240")
            zamg.set_parameters(["P"])
            await zamg.update()
        assert not session.closed
        assert zamg.session is session


@pytest.mark.asyncio
async def test_update_fixed_param(fix_data) -> None:
    """Test update function."""

    async with ZamgData() as zamg:
        zamg.set_default_station("11240")
        zamg.set_parameters(["P"])
        await zamg.update()
        assert zamg.get_data("P") == 987.3


@pytest.mark.asyncio
@pytest.mark.parametrize("own_session", [True, False])
async def test_update_fail(aresponses, own_session) -> None:
    """Test update raises ZamgApiError on an error status."""
    aresponses.add(
        API_HOST,
        STATION_DATA_PATH,
        "GET",
        aresponses.Response(text="error", status=500),
    )
    session = None if own_session else aiohttp.ClientSession()
    async with ZamgData(session=session) as zamg:
        zamg.set_default_station("11240")
        zamg.set_parameters(["P"])
        with pytest.raises(ZamgApiError):
            await zamg.update()
    if session is not None:
        await session.close()


@pytest.mark.asyncio
async def test_update_fail_2(aresponses) -> None:
    """Test update raises ZamgNoDataError on an empty response."""
    aresponses.add(
        API_HOST,
        STATION_DATA_PATH,
        "GET",
        aresponses.Response(text="{}", status=200),
    )
    async with ZamgData() as zamg:
        zamg.set_default_station("11240")
        zamg.set_parameters(["P"])
        with pytest.raises(ZamgNoDataError):
            await zamg.update()


@pytest.mark.asyncio
async def test_update_fail_3(aresponses) -> None:
    """Test update raises ZamgApiError when metadata can't be loaded."""
    aresponses.add(
        API_HOST,
        FORECAST_METADATA_PATH,
        "GET",
        aresponses.Response(text="error", status=500),
    )
    aresponses.add(
        API_HOST,
        STATION_METADATA_PATH,
        "GET",
        aresponses.Response(text="error", status=500),
    )
    async with ZamgData() as zamg:
        zamg.set_default_station("11240")
        with pytest.raises(ZamgApiError):
            await zamg.update()


@pytest.mark.asyncio
async def test_properties(fix_metadata) -> None:
    """Test getting stations, which are cached after the first call."""

    async with ZamgData() as zamg:
        stations = await zamg.zamg_stations()
        # fix_metadata only answers once, so a second request would fail
        assert await zamg.zamg_stations() is stations
        # check that we get at least one correct station
        assert stations.get("11240") == GRAZ


@pytest.mark.asyncio
async def test_properties_pre_loaded(fix_metadata) -> None:
    """Test preset station parameters are not overwritten by metadata."""

    async with ZamgData() as zamg:
        zamg.set_parameters(["TL"])
        stations = await zamg.zamg_stations()
        assert stations.get("11240") == GRAZ
        assert zamg.station_parameters == "TL"
        assert zamg.get_parameters() == ["TL"]


@pytest.mark.asyncio
async def test_properties_fail_1(aresponses) -> None:
    """Test getting stations returns None on an error status."""
    aresponses.add(
        API_HOST,
        FORECAST_METADATA_PATH,
        "GET",
        response=aresponses.Response(text="", status=404),
    )
    aresponses.add(
        API_HOST,
        STATION_METADATA_PATH,
        "GET",
        response=aresponses.Response(text="", status=404),
    )

    async with ZamgData() as zamg:
        assert await zamg.zamg_stations() is None
        assert zamg.forecast_metadata is None


@pytest.mark.asyncio
async def test_properties_fail_2() -> None:
    """Test getting stations raises ZamgApiError on a timeout."""

    class TimeoutSession:
        async def get(self, **_kwargs):
            raise ServerTimeoutError()

    zamg = ZamgData(session=TimeoutSession())
    with pytest.raises(ZamgApiError):
        await zamg.zamg_stations()


@pytest.mark.asyncio
async def test_properties_fail_3(aresponses) -> None:
    """Test getting stations raises ZamgNoDataError on an invalid response."""
    aresponses.add(
        API_HOST,
        FORECAST_METADATA_PATH,
        "GET",
        response=aresponses.Response(text=""),
    )

    async with ZamgData() as zamg:
        with pytest.raises(ZamgNoDataError):
            await zamg.zamg_stations()


@pytest.mark.asyncio
async def test_get_data_unknown_parameter(fix_metadata) -> None:
    """Test get_data raises ZamgNoDataError for an unknown parameter."""

    async with ZamgData() as zamg:
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

    async with ZamgData() as zamg:
        await zamg.zamg_stations()
        assert "TL" in zamg.get_all_parameters()


@pytest.mark.asyncio
async def test_get_parameters(fix_metadata) -> None:
    """Test getting get_parameters."""

    async with ZamgData() as zamg:
        await zamg.zamg_stations()
        assert "TL" in zamg.get_parameters()


def test_set_parameters() -> None:
    """Test setting station parameters."""

    zamg = ZamgData()
    zamg.set_parameters(("TL", "SO"))
    assert zamg.station_parameters == "TL,SO"
    assert zamg.get_parameters() == ["TL", "SO"]
    zamg.set_parameters([])
    assert zamg.station_parameters == ""


@pytest.mark.asyncio
async def test_forecast_metadata(fix_metadata) -> None:
    """Test forecast metadata and parameters are loaded with the stations."""

    async with ZamgData() as zamg:
        await zamg.zamg_stations()
        assert zamg.forecast_metadata["title"] == "numerical weather prediction"
        all_parameters = zamg.get_forecast_all_parameters()
        assert len(all_parameters) == 19
        assert {"t2m", "rr_acc", "u10m", "v10m", "sy"} <= set(all_parameters)
        # without preset forecast parameters all of them are read
        assert zamg.get_forecast_parameters() == all_parameters


@pytest.mark.asyncio
async def test_forecast_metadata_pre_loaded(fix_metadata) -> None:
    """Test preset forecast parameters are not overwritten by metadata."""

    async with ZamgData() as zamg:
        zamg.set_forecast_parameters(["t2m", "sy"])
        await zamg.zamg_stations()
        assert zamg.get_forecast_parameters() == ["t2m", "sy"]
        assert len(zamg.get_forecast_all_parameters()) == 19


def test_forecast_parameters_empty() -> None:
    """Test forecast parameter getters before metadata is loaded."""

    zamg = ZamgData()
    assert zamg.forecast_metadata is None
    assert zamg.get_forecast_all_parameters() == {}
    assert zamg.get_forecast_parameters() == {}


def test_set_forecast_parameters() -> None:
    """Test setting forecast parameters."""

    zamg = ZamgData()
    zamg.set_forecast_parameters(("t2m", "sy"))
    assert zamg.forecast_parameters == "t2m,sy"
    zamg.set_forecast_parameters([])
    assert zamg.forecast_parameters == ""


@pytest.mark.asyncio
async def test_closest_station(fix_metadata) -> None:
    """Test getting closest station."""

    async with ZamgData() as zamg:
        station = await zamg.closest_station(46.9, 15.4)
        assert station == "11240"


@pytest.mark.asyncio
async def test_closest_station_not_found(aresponses) -> None:
    """Test getting closest station."""
    aresponses.add(
        API_HOST,
        FORECAST_METADATA_PATH,
        "GET",
        response=_load_json("data_forecast_metadata.json"),
    )
    aresponses.add(
        API_HOST,
        STATION_METADATA_PATH,
        "GET",
        response={"title": "TAWES", "parameters": [{"name": "TL"}], "stations": []},
    )

    async with ZamgData() as zamg:
        with pytest.raises(ZamgStationNotFoundError):
            await zamg.closest_station(46.9, 15.4)


@pytest.mark.asyncio
async def test_get_station_name(fix_metadata) -> None:
    """Test getting get_station_name."""

    async with ZamgData() as zamg:
        await zamg.zamg_stations()
        zamg.set_default_station("11240")
        assert zamg.get_station_name == "GRAZ-THALERHOF-FLUGHAFEN"


@pytest.mark.asyncio
async def test_get_station_name_unknown(fix_metadata) -> None:
    """Test getting get_station_name."""

    async with ZamgData() as zamg:
        await zamg.zamg_stations()
        with pytest.raises(ZamgStationUnknownError):
            _ = zamg.get_station_name


@pytest.mark.asyncio
async def test_get_station_location(fix_metadata) -> None:
    """Test getting get_station_location."""

    async with ZamgData() as zamg:
        await zamg.zamg_stations()
        zamg.set_default_station("11240")
        assert zamg.get_station_location == (46.980555555555554, 15.44)


@pytest.mark.asyncio
async def test_get_station_location_unknown(fix_metadata) -> None:
    """Test getting get_station_location."""

    async with ZamgData() as zamg:
        await zamg.zamg_stations()
        with pytest.raises(ZamgStationUnknownError):
            _ = zamg.get_station_location


@pytest.mark.asyncio
async def test_get_forecast_uses_station_location(aresponses) -> None:
    """Test get_forecast uses default station location when lat_lon isn't provided."""

    payload = _forecast_payload()
    aresponses.add(API_HOST, FORECAST_PATH, "GET", response=payload)

    async with ZamgData() as zamg:
        zamg._stations = {"11240": GRAZ}
        zamg.set_default_station("11240")

        result = await zamg.get_forecast(current_only=True)

    assert result["timestamp"] == payload["timestamps"][1]
    assert result["t2m"] == 11.0
    request = aresponses.history[-1].request
    assert request.query["lat_lon"] == "46.980555555555554,15.44"
    assert request.query["parameters"] == "t2m,rr_acc,u10m,v10m,tcc,sy,rh2m"
    assert zamg.last_forecast_update is not None


@pytest.mark.asyncio
async def test_get_forecast_fetch(aresponses) -> None:
    """Test get_forecast fetches and trims data for an explicit location."""

    payload = _forecast_payload()
    aresponses.add(API_HOST, FORECAST_PATH, "GET", response=payload)

    async with aiohttp.ClientSession() as session:
        zamg = ZamgData(session=session)
        zamg.set_forecast_parameters(["t2m", "rr_acc", "u10m", "v10m"])
        result = await zamg.get_forecast("47.0,15.5")

    request = aresponses.history[-1].request
    assert request.query["lat_lon"] == "47.0,15.5"
    assert request.query["parameters"] == "t2m,rr_acc,u10m,v10m"
    assert result["timestamps"] == payload["timestamps"][1:]
    parameters = result["features"][0]["properties"]["parameters"]
    assert parameters["t2m"]["data"] == [11.0, 12.0]
    assert parameters["rain"]["data"] == [0.4, 0.5]


@pytest.mark.asyncio
async def test_get_forecast_cached_current(aresponses) -> None:
    """Test get_forecast returns the cached current forecast within 5 minutes."""

    payload = _forecast_payload()
    aresponses.add(API_HOST, FORECAST_PATH, "GET", response=payload)

    async with ZamgData() as zamg:
        first = await zamg.get_forecast("47.0,15.5", current_only=True)
        # the forecast is only answered once, so a second request would fail
        second = await zamg.get_forecast("47.0,15.5", current_only=True)

    assert first == second
    assert second["timestamp"] == payload["timestamps"][1]


@pytest.mark.asyncio
async def test_get_forecast_fail_status(aresponses) -> None:
    """Test get_forecast raises ZamgApiError on an error status."""
    aresponses.add(
        API_HOST,
        FORECAST_PATH,
        "GET",
        aresponses.Response(text="error", status=500),
    )

    async with ZamgData() as zamg:
        with pytest.raises(ZamgApiError):
            await zamg.get_forecast("47.0,15.5")
    assert zamg.last_forecast_update is None


@pytest.mark.asyncio
async def test_get_forecast_fail_invalid_json(aresponses) -> None:
    """Test get_forecast raises ZamgNoDataError on an invalid response."""
    aresponses.add(
        API_HOST,
        FORECAST_PATH,
        "GET",
        aresponses.Response(text="not json", status=200),
    )

    async with ZamgData() as zamg:
        with pytest.raises(ZamgNoDataError):
            await zamg.get_forecast("47.0,15.5")


@pytest.mark.asyncio
async def test_get_forecast_fail_no_data(aresponses) -> None:
    """Test get_forecast raises ZamgNoDataError on a response without data."""
    aresponses.add(API_HOST, FORECAST_PATH, "GET", response={})

    async with ZamgData() as zamg:
        with pytest.raises(ZamgNoDataError):
            await zamg.get_forecast("47.0,15.5")


@pytest.mark.asyncio
async def test_get_forecast_no_station(aresponses) -> None:
    """Test get_forecast without lat_lon and without a known station."""

    async with ZamgData() as zamg:
        with pytest.raises(ZamgStationUnknownError):
            await zamg.get_forecast()


@pytest.mark.asyncio
async def test_last_update(fix_data, fix_metadata) -> None:
    """Test getting last_update."""

    async with ZamgData() as zamg:
        zamg.set_default_station("11240")
        await zamg.update()
        assert zamg.last_update == datetime(
            2022, 11, 13, 10, 20, tzinfo=zoneinfo.ZoneInfo(key="UTC")
        )


@pytest.mark.asyncio
async def test_update_no_station() -> None:
    """Test update without a default station returns None."""

    async with ZamgData() as zamg:
        assert await zamg.update() is None


def test_last_update_unknown() -> None:
    """Test getting last_update."""

    zamg = ZamgData()
    assert zamg.last_update is None
    assert zamg.last_forecast_update is None


def test_get_forecast_current() -> None:
    """Test extracting current forecast values."""

    zamg = ZamgData()
    forecast_data = _forecast_payload()

    result = zamg.get_forecast_current(forecast_data)

    assert result["timestamp"] == forecast_data["timestamps"][1]
    assert result["reference_time"] == forecast_data["reference_time"]
    assert result["t2m"] == 11.0
    assert result["rh2m"] == 81.0
    assert result["u10m"] == 2.0
    assert result["v10m"] == 5.0
    assert result["rain"] == 0.4
    assert result["rr_acc_prev"] == 0.5
    assert result["wind_speed"] == 19.4
    assert result["tcc"] == 0.2
    assert result["sy"] == 2.0
    assert result["sy_text"] == "Mostly clear"
    assert result["condition"] == "sunny"


def test_get_forecast_current_without_symbol() -> None:
    """Test extracting current forecast values without a weather symbol."""

    zamg = ZamgData()
    result = zamg.get_forecast_current(
        _forecast_payload(include_sy=False),
        parameters=("t2m", "rr_acc"),
    )

    assert result["t2m"] == 11.0
    assert "sy_text" not in result
    assert "condition" not in result


@pytest.mark.parametrize(
    "forecast_data",
    [
        {},
        {"timestamps": ["not a timestamp"], "features": []},
        {"timestamps": [], "features": []},
    ],
)
def test_get_forecast_current_invalid(forecast_data) -> None:
    """Test extracting current forecast values from invalid data."""

    zamg = ZamgData()
    with pytest.raises(ZamgNoDataError):
        zamg.get_forecast_current(forecast_data)


@pytest.mark.asyncio
async def test_get_forecast_trims_past_data() -> None:
    """Test get_forecast returns only timestamps from now onward."""

    async with ZamgData() as zamg:
        zamg.data_forecast = _forecast_payload()
        timestamps = zamg.data_forecast["timestamps"]
        zamg._timestamp_forecast = zamg.data_forecast["reference_time"]

        result = await zamg.get_forecast("46.99,15.499", current_only=False)

        parameters = result["features"][0]["properties"]["parameters"]
        assert result["timestamps"] == timestamps[1:]
        assert parameters["t2m"]["data"] == [11.0, 12.0]
        assert parameters["rain"]["data"] == [0.4, 0.5]
        assert parameters["wind_speed"]["data"] == [19.4, 24.1]
        assert parameters["tcc"]["data"] == [0.2, 0.3]
        assert parameters["sy"]["data"] == [2.0, 3.0]
        assert parameters["sy_text"]["data"] == ["Mostly clear", "Partly cloudy"]
        assert parameters["condition"]["data"] == ["sunny", "partlycloudy"]
        # the cached source data is left untouched
        assert zamg.data_forecast["timestamps"] == timestamps


def test_get_forecast_from_now_without_symbol() -> None:
    """Test trimming forecast data without a weather symbol."""

    zamg = ZamgData()
    result = zamg._get_forecast_from_now(_forecast_payload(include_sy=False))

    parameters = result["features"][0]["properties"]["parameters"]
    assert parameters["t2m"]["data"] == [11.0, 12.0]
    assert "sy_text" not in parameters
    assert "condition" not in parameters


def test_get_forecast_from_now_invalid() -> None:
    """Test trimming invalid forecast data."""

    zamg = ZamgData()
    with pytest.raises(ZamgNoDataError):
        zamg._get_forecast_from_now({"timestamps": [], "features": [{}]})


def test_symbol_to_text() -> None:
    """Test translating weather symbol codes to descriptions."""

    assert symbol_to_text(1) == "Clear"
    assert symbol_to_text(26.0) == "Thunderstorm"
    assert symbol_to_text(32) == "Heavy thunderstorm with snowfall"
    assert symbol_to_text(1, lang="de") == "Wolkenlos"
    assert symbol_to_text(26.0, lang="de") == "Gewitter"
    assert symbol_to_text(None) is None
    assert symbol_to_text(0) is None
    assert symbol_to_text(33) is None


def test_symbol_to_condition() -> None:
    """Test translating weather symbol codes to weather conditions."""

    assert symbol_to_condition(1) == "sunny"
    assert symbol_to_condition(3) == "partlycloudy"
    assert symbol_to_condition(6.0) == "fog"
    assert symbol_to_condition(10) == "pouring"
    assert symbol_to_condition(16) == "snowy"
    assert symbol_to_condition(20) == "snowy-rainy"
    assert symbol_to_condition(28) == "lightning-rainy"
    assert symbol_to_condition(None) is None
    assert symbol_to_condition(0) is None
    assert symbol_to_condition(33) is None


@pytest.fixture(autouse=True)
def fix_strict_requests(aresponses):
    """Fail tests that send unmocked requests or leave mocked routes unused."""
    yield
    aresponses.assert_no_unused_routes()
    aresponses.assert_all_requests_matched()


@pytest.fixture
def fix_metadata(aresponses):
    """Fixture to get forecast and station metadata."""
    aresponses.add(
        API_HOST,
        FORECAST_METADATA_PATH,
        "GET",
        response=_load_json("data_forecast_metadata.json"),
    )
    aresponses.add(
        API_HOST,
        STATION_METADATA_PATH,
        "GET",
        response=_load_json("data_metadata.json"),
    )


@pytest.fixture
def fix_data(aresponses):
    """Fixture to get data of a station."""
    aresponses.add(
        API_HOST,
        STATION_DATA_PATH,
        "GET",
        response=_load_json("data_station.json"),
    )

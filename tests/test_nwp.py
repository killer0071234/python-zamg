"""Tests for the GeoSphere Austria NWP v2 client."""

import asyncio
import copy
import json
import math
import pathlib
from datetime import datetime

import aiohttp
import pytest
from aiohttp.client_exceptions import ServerDisconnectedError, ServerTimeoutError

from src.zamg import NwpClient, NwpForecast, NwpForecastRecord
from src.zamg.exceptions import ZamgApiError, ZamgNoDataError
from src.zamg.nwp import FORECAST_PARAMETERS

FORECAST_HOST = "dataset.api.hub.geosphere.at"
FORECAST_PATH = "/v1/timeseries/forecast/nwp-v2-1h-1km"


@pytest.fixture
def nwp_payload() -> dict:
    """Return a production-shaped sanitized NWP v2 response."""
    return json.loads(
        pathlib.Path(__file__)
        .parent.joinpath("data_nwp_forecast.json")
        .read_text(encoding="utf-8")
    )


def add_forecast_response(aresponses, payload, *, status=200, headers=None) -> None:
    """Register one forecast response."""
    if isinstance(payload, (dict, list)) and status == 200 and headers is None:
        response = payload
    else:
        response = aresponses.Response(
            text=payload if isinstance(payload, str) else json.dumps(payload),
            status=status,
            headers=headers,
        )
    aresponses.add(FORECAST_HOST, FORECAST_PATH, "GET", response=response)


@pytest.mark.asyncio
async def test_get_forecast_parses_native_v2_data(aresponses, nwp_payload) -> None:
    """Test a forecast is requested and parsed in native units."""
    add_forecast_response(aresponses, nwp_payload)

    async with NwpClient() as client:
        forecast = await client.get_forecast(latitude=47.5, longitude=14.0)

    assert isinstance(forecast, NwpForecast)
    assert isinstance(forecast.records[0], NwpForecastRecord)
    assert forecast.reference_time == datetime.fromisoformat("2026-09-26T00:00+00:00")
    assert forecast.requested_latitude == 47.5
    assert forecast.requested_longitude == 14.0
    assert forecast.resolved_latitude == 47.502
    assert forecast.resolved_longitude == 14.0045
    assert len(forecast.records) == 4

    record = forecast.records[1]
    assert record.valid_time == datetime.fromisoformat("2026-09-26T05:00+00:00")
    assert record.temperature == 7.2
    assert record.relative_humidity == 95.0
    assert record.cloud_cover == 100.0
    assert record.mean_sea_level_pressure == 102432.01
    assert record.wind_u == -1.0
    assert record.wind_v == 0.0
    assert record.wind_speed == 1.0
    assert record.wind_bearing == 90.0
    assert record.wind_gust == 1.3
    assert record.precipitation == 0.006
    assert (
        record.precipitation
        != nwp_payload["features"][0]["properties"]["parameters"]["rain"]["data"][1]
    )
    assert record.symbol == 3.0
    assert record.symbol_text == "Partly cloudy"
    assert record.condition == "partlycloudy"

    request = aresponses.history[0].request
    assert request.query["lat_lon"] == "47.5,14.0"
    assert request.query["parameters"] == ",".join(FORECAST_PARAMETERS)


@pytest.mark.asyncio
async def test_wind_bearings_cover_quadrants(aresponses, nwp_payload) -> None:
    """Test meteorological wind-from bearings for all cardinal quadrants."""
    add_forecast_response(aresponses, nwp_payload)

    async with NwpClient() as client:
        forecast = await client.get_forecast(latitude=47.5, longitude=14.0)

    assert [record.wind_bearing for record in forecast.records] == [
        0.0,
        90.0,
        180.0,
        270.0,
    ]


@pytest.mark.asyncio
async def test_wind_calm_and_null_components(aresponses, nwp_payload) -> None:
    """Test calm wind and nullable wind components."""
    parameters = nwp_payload["features"][0]["properties"]["parameters"]
    parameters["10u"]["data"] = [0.0, None, 0.0, 1.0]
    parameters["10v"]["data"] = [0.0, 1.0, 1.0, 0.0]
    add_forecast_response(aresponses, nwp_payload)

    async with NwpClient() as client:
        forecast = await client.get_forecast(latitude=47.5, longitude=14.0)

    assert forecast.records[0].wind_speed == 0.0
    assert forecast.records[0].wind_bearing is None
    assert forecast.records[1].wind_u is None
    assert forecast.records[1].wind_v == 1.0
    assert forecast.records[1].wind_speed is None
    assert forecast.records[1].wind_bearing is None


@pytest.mark.asyncio
async def test_wind_speed_is_not_rounded(aresponses, nwp_payload) -> None:
    """Test derived native wind speed retains its calculated precision."""
    parameters = nwp_payload["features"][0]["properties"]["parameters"]
    parameters["10u"]["data"][0] = 1.0
    parameters["10v"]["data"][0] = 1.0
    add_forecast_response(aresponses, nwp_payload)

    async with NwpClient() as client:
        forecast = await client.get_forecast(latitude=47.5, longitude=14.0)

    assert forecast.records[0].wind_speed == math.sqrt(2)


@pytest.mark.asyncio
async def test_null_and_unknown_symbol_values(aresponses, nwp_payload) -> None:
    """Test null weather values and unknown weather symbols are preserved."""
    add_forecast_response(aresponses, nwp_payload)

    async with NwpClient() as client:
        forecast = await client.get_forecast(latitude=47.5, longitude=14.0)

    assert forecast.records[2].temperature is None
    assert forecast.records[2].symbol == 99.0
    assert forecast.records[2].symbol_text is None
    assert forecast.records[2].condition is None
    assert forecast.records[3].symbol is None
    assert forecast.records[3].symbol_text is None
    assert forecast.records[3].condition is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (True, 14.0),
        (math.inf, 14.0),
        (91.0, 14.0),
        (47.5, -181.0),
        ("47.5", 14.0),
    ],
)
async def test_invalid_coordinates(latitude, longitude) -> None:
    """Test invalid caller coordinates fail before a session is created."""
    client = NwpClient()

    with pytest.raises(ValueError):
        await client.get_forecast(latitude=latitude, longitude=longitude)

    assert client.session is None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 422, 500])
async def test_http_errors(aresponses, status) -> None:
    """Test API status failures use the public API exception."""
    add_forecast_response(aresponses, "error", status=status)

    async with NwpClient() as client:
        with pytest.raises(ZamgApiError, match=f"status {status}"):
            await client.get_forecast(latitude=47.5, longitude=14.0)


@pytest.mark.asyncio
async def test_rate_limit_reset_is_retained(aresponses) -> None:
    """Test a rate-limit reset is included without retrying."""
    add_forecast_response(
        aresponses,
        "rate limited",
        status=429,
        headers={"ratelimit-reset": "42"},
    )

    async with NwpClient() as client:
        with pytest.raises(ZamgApiError, match="resets in 42 seconds"):
            await client.get_forecast(latitude=47.5, longitude=14.0)

    assert len(aresponses.history) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [ServerTimeoutError(), ServerDisconnectedError(), asyncio.TimeoutError()],
)
async def test_transport_errors(failure) -> None:
    """Test transport failures use the public API exception."""

    class FailingSession:
        def get(self, *_args, **_kwargs):
            raise failure

    client = NwpClient(session=FailingSession())

    with pytest.raises(ZamgApiError):
        await client.get_forecast(latitude=47.5, longitude=14.0)


@pytest.mark.asyncio
async def test_request_timeout_expiration() -> None:
    """Test expiration of the timeout context uses the API exception."""

    class SlowRequest:
        async def __aenter__(self):
            await asyncio.sleep(0.02)

        async def __aexit__(self, *_exc_info):
            return None

    class SlowSession:
        def get(self, *_args, **_kwargs):
            return SlowRequest()

    client = NwpClient(session=SlowSession())
    client.request_timeout = 0.001

    with pytest.raises(ZamgApiError):
        await client.get_forecast(latitude=47.5, longitude=14.0)


@pytest.mark.asyncio
async def test_invalid_json(aresponses) -> None:
    """Test invalid successful JSON uses the no-data exception."""
    add_forecast_response(aresponses, "not json")

    async with NwpClient() as client:
        with pytest.raises(ZamgNoDataError):
            await client.get_forecast(latitude=47.5, longitude=14.0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "unequal_array",
        "missing_parameter",
        "unexpected_unit",
        "naive_timestamp",
        "duplicate_timestamp",
        "boolean_value",
        "multiple_features",
        "invalid_grid_coordinate",
        "naive_reference_time",
        "non_finite_value",
    ],
)
async def test_malformed_successful_responses(
    aresponses, nwp_payload, mutation
) -> None:
    """Test malformed successful payloads fail atomically."""
    payload = copy.deepcopy(nwp_payload)
    parameters = payload["features"][0]["properties"]["parameters"]
    if mutation == "unequal_array":
        parameters["2t"]["data"].pop()
    elif mutation == "missing_parameter":
        del parameters["msl"]
    elif mutation == "unexpected_unit":
        parameters["tcc"]["unit"] = "1"
    elif mutation == "naive_timestamp":
        payload["timestamps"][0] = "2026-09-26T04:00"
    elif mutation == "duplicate_timestamp":
        payload["timestamps"][1] = payload["timestamps"][0]
    elif mutation == "boolean_value":
        parameters["2r"]["data"][0] = True
    elif mutation == "multiple_features":
        payload["features"].append(copy.deepcopy(payload["features"][0]))
    elif mutation == "invalid_grid_coordinate":
        payload["features"][0]["geometry"]["coordinates"][0] = 181.0
    elif mutation == "naive_reference_time":
        payload["reference_time"] = "2026-09-26T00:00"
    elif mutation == "non_finite_value":
        parameters["2t"]["data"][0] = math.inf
    add_forecast_response(aresponses, payload)

    async with NwpClient() as client:
        with pytest.raises(ZamgNoDataError):
            await client.get_forecast(latitude=47.5, longitude=14.0)


@pytest.mark.asyncio
async def test_injected_session_is_not_closed(aresponses, nwp_payload) -> None:
    """Test an injected session remains owned by its caller."""
    add_forecast_response(aresponses, nwp_payload)
    session = aiohttp.ClientSession()
    client = NwpClient(session=session)
    try:
        await client.get_forecast(latitude=47.5, longitude=14.0)
        await client.close()
        assert not session.closed
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_owned_session_is_closed(aresponses, nwp_payload) -> None:
    """Test a lazily created session closes on context exit."""
    add_forecast_response(aresponses, nwp_payload)
    client = NwpClient()

    async with client as entered_client:
        assert entered_client is client
        await client.get_forecast(latitude=47.5, longitude=14.0)
        owned_session = client.session
        assert owned_session is not None
        assert not owned_session.closed

    assert owned_session.closed
    assert client.session is None
    await client.close()

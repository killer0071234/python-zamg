"""Tests for the GeoSphere Austria NWP v2 client."""

import asyncio
import copy
import json
import math
import pathlib
import sys
from datetime import datetime
from unittest.mock import patch

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
    assert record.wind_gust == 1.3
    assert record.wind_u == -1.0
    assert record.wind_v == 0.0
    assert record.relative_humidity == 95.0
    assert record.temperature == 7.2
    assert record.convective_available_potential_energy == 5.4
    assert record.mean_sea_level_pressure == 102432.01
    assert record.severe_precipitation_type == 0.0
    assert record.rainfall == 0.001
    assert record.snowfall == 0.005
    assert record.snow_limit == 3359.8
    assert record.surface_global_radiation == 265.4
    assert record.sunshine_duration == 3587.5
    assert record.symbol == 3.0
    assert record.cloud_cover == 100.0
    assert record.precipitation == 0.006
    assert not hasattr(record, "wind_speed")
    assert not hasattr(record, "wind_bearing")
    assert not hasattr(record, "symbol_text")
    assert not hasattr(record, "condition")

    request = aresponses.history[0].request
    assert request.query["lat_lon"] == "47.5,14.0"
    assert request.query["parameters"] == ",".join(FORECAST_PARAMETERS)
    assert FORECAST_PARAMETERS == (
        "10fg",
        "10u",
        "10v",
        "2r",
        "2t",
        "cape",
        "msl",
        "pt",
        "rain",
        "sf",
        "snowlmt",
        "ssrd",
        "sund",
        "sy",
        "tcc",
        "tp",
    )


@pytest.mark.asyncio
async def test_null_and_unknown_raw_values(aresponses, nwp_payload) -> None:
    """Test null weather values and unknown raw codes are preserved."""
    add_forecast_response(aresponses, nwp_payload)

    async with NwpClient() as client:
        forecast = await client.get_forecast(latitude=47.5, longitude=14.0)

    assert forecast.records[2].temperature is None
    assert forecast.records[2].convective_available_potential_energy is None
    assert forecast.records[2].severe_precipitation_type is None
    assert forecast.records[2].rainfall is None
    assert forecast.records[2].snowfall is None
    assert forecast.records[2].snow_limit is None
    assert forecast.records[2].surface_global_radiation is None
    assert forecast.records[2].sunshine_duration is None
    assert forecast.records[2].symbol == 99.0
    assert forecast.records[3].symbol is None


@pytest.mark.asyncio
@pytest.mark.parametrize("verify_ssl", [None, True, False])
async def test_ssl_verification_option(aresponses, nwp_payload, verify_ssl) -> None:
    """Test the SSL override is forwarded only when explicitly configured."""
    add_forecast_response(aresponses, nwp_payload)

    async with aiohttp.ClientSession() as session:
        with patch.object(session, "get", wraps=session.get) as get:
            async with NwpClient(session=session) as client:
                client.verify_ssl = verify_ssl
                forecast = await client.get_forecast(latitude=47.5, longitude=14.0)

        get.assert_called_once()
        if verify_ssl is None:
            assert "ssl" not in get.call_args.kwargs
        else:
            assert get.call_args.kwargs["ssl"] is verify_ssl

    assert len(forecast.records) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (True, 14.0),
        (math.inf, 14.0),
        (91.0, 14.0),
        (47.5, -181.0),
        ("47.5", 14.0),
        (10**400, 14.0),
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
        with pytest.raises(ZamgApiError, match=f"status {status}") as exc_info:
            await client.get_forecast(latitude=47.5, longitude=14.0)

    assert exc_info.value.status_code == status
    assert exc_info.value.rate_limit_reset is None


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
        with pytest.raises(ZamgApiError, match="resets in 42 seconds") as exc_info:
            await client.get_forecast(latitude=47.5, longitude=14.0)

    assert exc_info.value.status_code == 429
    assert exc_info.value.rate_limit_reset == 42
    assert len(aresponses.history) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("reset", [None, "", "-1", "+1", "1.5", "invalid"])
async def test_invalid_rate_limit_reset_is_ignored(aresponses, reset) -> None:
    """Test invalid reset metadata does not mask the rate-limit failure."""
    headers = {} if reset is None else {"ratelimit-reset": reset}
    add_forecast_response(aresponses, "rate limited", status=429, headers=headers)

    async with NwpClient() as client:
        with pytest.raises(ZamgApiError, match="status 429") as exc_info:
            await client.get_forecast(latitude=47.5, longitude=14.0)

    assert exc_info.value.status_code == 429
    assert exc_info.value.rate_limit_reset is None


@pytest.mark.asyncio
async def test_oversized_rate_limit_reset_is_ignored(aresponses) -> None:
    """Test integer conversion limits do not mask the rate-limit failure."""
    original_limit = sys.get_int_max_str_digits()
    limit = sys.int_info.str_digits_check_threshold
    sys.set_int_max_str_digits(limit)
    try:
        add_forecast_response(
            aresponses,
            "rate limited",
            status=429,
            headers={"ratelimit-reset": "9" * (limit + 1)},
        )

        async with NwpClient() as client:
            with pytest.raises(ZamgApiError, match="status 429") as exc_info:
                await client.get_forecast(latitude=47.5, longitude=14.0)

        assert exc_info.value.status_code == 429
        assert exc_info.value.rate_limit_reset is None
        assert len(aresponses.history) == 1
    finally:
        sys.set_int_max_str_digits(original_limit)


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

    with pytest.raises(ZamgApiError) as exc_info:
        await client.get_forecast(latitude=47.5, longitude=14.0)

    assert exc_info.value.status_code is None
    assert exc_info.value.rate_limit_reset is None


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

    with pytest.raises(ZamgApiError) as exc_info:
        await client.get_forecast(latitude=47.5, longitude=14.0)

    assert exc_info.value.status_code is None
    assert exc_info.value.rate_limit_reset is None


@pytest.mark.asyncio
async def test_invalid_json(aresponses) -> None:
    """Test invalid successful JSON uses the no-data exception."""
    add_forecast_response(aresponses, "not json")

    async with NwpClient() as client:
        with pytest.raises(ZamgNoDataError):
            await client.get_forecast(latitude=47.5, longitude=14.0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("unequal_array", "parameter 2t data length does not match timestamps"),
        ("missing_parameter", "msl"),
        ("unexpected_unit", "parameter tcc has an unexpected unit"),
        ("naive_timestamp", "forecast timestamp must include a timezone offset"),
        ("duplicate_timestamp", "forecast timestamps must be strictly increasing"),
        ("boolean_value", "parameter 2r values must be numbers or null"),
        ("multiple_features", "forecast response must contain exactly one feature"),
        ("invalid_grid_coordinate", "resolved longitude must be between"),
        ("naive_reference_time", "reference_time must include a timezone offset"),
        ("non_finite_value", "parameter 2t values must be finite"),
        ("overflowing_value", "parameter 2t values must be finite"),
        ("invalid_payload", "forecast response is not a FeatureCollection"),
        ("invalid_payload_type", "forecast response is not a FeatureCollection"),
        ("empty_timestamps", "timestamps must be a non-empty array"),
        ("invalid_timestamps", "timestamps must be a non-empty array"),
        ("invalid_feature", "forecast feature must be an object"),
        ("invalid_geometry", "forecast geometry must be a Point"),
        ("invalid_geometry_type", "forecast geometry must be a Point"),
        (
            "invalid_coordinates",
            "forecast Point must contain longitude and latitude",
        ),
        (
            "invalid_coordinates_length",
            "forecast Point must contain longitude and latitude",
        ),
        ("invalid_properties", "forecast properties must be an object"),
        ("invalid_parameters", "forecast parameters must be an object"),
        ("invalid_parameter", "parameter 2t must be an object"),
        ("non_string_timestamp", "forecast timestamp must be a string"),
        ("non_string_reference_time", "reference_time must be a string"),
    ],
)
async def test_malformed_successful_responses(
    aresponses, nwp_payload, mutation, message
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
    elif mutation == "overflowing_value":
        parameters["2t"]["data"][0] = 10**400
    elif mutation == "invalid_payload":
        payload = []
    elif mutation == "invalid_payload_type":
        payload["type"] = "Feature"
    elif mutation == "empty_timestamps":
        payload["timestamps"] = []
    elif mutation == "invalid_timestamps":
        payload["timestamps"] = None
    elif mutation == "invalid_feature":
        payload["features"][0] = None
    elif mutation == "invalid_geometry":
        payload["features"][0]["geometry"] = None
    elif mutation == "invalid_geometry_type":
        payload["features"][0]["geometry"]["type"] = "LineString"
    elif mutation == "invalid_coordinates":
        payload["features"][0]["geometry"]["coordinates"] = None
    elif mutation == "invalid_coordinates_length":
        payload["features"][0]["geometry"]["coordinates"] = [14.0]
    elif mutation == "invalid_properties":
        payload["features"][0]["properties"] = None
    elif mutation == "invalid_parameters":
        payload["features"][0]["properties"]["parameters"] = None
    elif mutation == "invalid_parameter":
        parameters["2t"] = None
    elif mutation == "non_string_timestamp":
        payload["timestamps"][0] = None
    elif mutation == "non_string_reference_time":
        payload["reference_time"] = None
    add_forecast_response(aresponses, payload)

    async with NwpClient() as client:
        with pytest.raises(ZamgNoDataError, match=message):
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

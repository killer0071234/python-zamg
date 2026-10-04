# python-zamg

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]
[![Code Coverage][codecov-shield]][codecov]

[![Project Maintenance][maintenance-shield]][user_profile]

Python library for GeoSphere Austria station observations and coordinate-based
numerical weather prediction forecasts.

## About

This package reads weather-station observations and independent NWP forecasts
from the GeoSphere Austria weather service.
GeoSphere Austria joins Zentralanstalt für Meteorologie und Geodynamik (ZAMG) and the Geologische Bundesanstalt (GBA)
since 1st January 2023.

## Installation

```bash
pip install zamg
```

## Usage

### NWP v2 forecast

Use `NwpClient` for an independent coordinate-based hourly forecast. It uses
GeoSphere Austria's `nwp-v2-1h-1km` model and does not select or request a
weather station.

```python
import asyncio

from zamg import NwpClient


async def main():
    async with NwpClient() as client:
        forecast = await client.get_forecast(
            latitude=48.2082,
            longitude=16.3738,
        )

    print(forecast.reference_time)
    print(forecast.resolved_latitude, forecast.resolved_longitude)
    for record in forecast.records:
        print(record.valid_time, record.temperature, record.symbol)


if __name__ == "__main__":
    asyncio.run(main())
```

Every request includes all 16 parameters currently exposed by the dataset.
Typed records preserve each raw value independently in GeoSphere API native
units:

| API parameter | Record field                            | Native unit/meaning                                      |
| ------------- | --------------------------------------- | -------------------------------------------------------- |
| `10fg`        | `wind_gust`                             | m/s, maximum in the forecast interval                    |
| `10u`         | `wind_u`                                | m/s, eastward component                                  |
| `10v`         | `wind_v`                                | m/s, northward component                                 |
| `2r`          | `relative_humidity`                     | percent                                                  |
| `2t`          | `temperature`                           | degrees Celsius                                          |
| `cape`        | `convective_available_potential_energy` | m²/s²                                                    |
| `msl`         | `mean_sea_level_pressure`               | Pa                                                       |
| `pt`          | `severe_precipitation_type`             | raw dimensionless provider code                          |
| `rain`        | `rainfall`                              | kg/m² in the forecast interval                           |
| `sf`          | `snowfall`                              | kg/m² in the forecast interval                           |
| `snowlmt`     | `snow_limit`                            | m above ground                                           |
| `ssrd`        | `surface_global_radiation`              | W/m²                                                     |
| `sund`        | `sunshine_duration`                     | seconds in the forecast interval                         |
| `sy`          | `symbol`                                | raw dimensionless GeoSphere weather-symbol code          |
| `tcc`         | `cloud_cover`                           | percent                                                  |
| `tp`          | `precipitation`                         | kg/m², total liquid and solid precipitation per interval |

The client does not combine precipitation values, calculate wind speed or
bearing, or interpret provider codes. Consumers can choose which raw fields to
use.

Meteorological values may be `None` when the API reports missing data. Both the
requested coordinates and the resolved model-grid coordinates are available on
`NwpForecast`. Forecast timestamps and the model reference time are
timezone-aware.

`NwpClient` performs no polling, retries, or caching. Applications should set
their own update policy and should respect GeoSphere Austria's published rate
limits. A rate-limit response is raised as `ZamgApiError` and includes the reset
duration when supplied by the API. HTTP failures expose their integer status as
`ZamgApiError.status_code`. For a 429 response with a valid non-negative integer
`ratelimit-reset` header, `ZamgApiError.rate_limit_reset` contains that delay in
seconds; otherwise it is `None`. Both attributes are `None` for transport and
timeout failures.

### Station observations

Simple usage example to fetch specific data from the closest station.

```python
"""Asynchronous Python client for GeoSphere Austria weather data."""

import asyncio

import zamg.zamg
from zamg.exceptions import ZamgError


async def main():
    """Sample of getting data"""
    try:
        async with zamg.ZamgData() as zamg_instance:
            # option to disable verify of ssl check
            zamg_instance.verify_ssl = False
            # trying to read GeoSphere Austria station id of the closest station
            data = await zamg_instance.closest_station(46.99, 15.499)
            # set closest station as default one to read
            zamg_instance.set_default_station(data)
            # print station location of the closest station
            print("get_station_location = " + str(zamg_instance.get_station_location))
            print("closest_station = " + str(zamg_instance.get_station_name) + " / " + str(data))
            # print list with all possible parameters
            print(f"Possible station parameters: {zamg_instance.get_all_parameters()}")
            # set parameters directly
            zamg_instance.station_parameters = "TL,SO"
            # or set parameters as list
            zamg_instance.set_parameters(("TL", "SO"))
            # if none of the above parameters are set, all possible parameters are read
            # do an update
            await zamg_instance.update()

            print(f"---------- Weather for station {zamg_instance.get_station_name} ({data})")
            for param in zamg_instance.get_parameters():
                print(
                    str(param)
                    + " -> "
                    + str(zamg_instance.get_data(parameter=param, data_type="name"))
                    + " -> "
                    + str(zamg_instance.get_data(parameter=param))
                    + " "
                    + str(zamg_instance.get_data(parameter=param, data_type="unit"))
                )
            print(f"last update: {zamg_instance.last_update}")
    except ZamgError as exc:
        print(exc)


if __name__ == "__main__":
    asyncio.run(main())

```

### Legacy forecast API

The existing `ZamgData.get_forecast()` API remains available unchanged while
its NWP v2 compatibility behavior is finalized.

Simple usage example to fetch weather forecast for a specific location.

```python
"""Asynchronous Python client for GeoSphere Austria forecast weather data."""

import asyncio

import zamg.zamg
from zamg.exceptions import ZamgError


async def main():
    """Sample of getting data"""
    try:
        async with zamg.zamg.ZamgData() as zamg_instance:
            # option to disable verify of ssl check
            zamg_instance.verify_ssl = False
            # trying to read GeoSphere Austria station id of the closest station
            data = await zamg_instance.closest_station(46.99, 15.499)
            # set closest station as default one to read
            zamg_instance.set_default_station(data)
            # print(f"forecast_metadata: {zamg_instance.forecast_metadata}")
            # print(f"get_forecast_all_parameters: {zamg_instance.get_forecast_all_parameters()}")

            data = await zamg_instance.get_forecast("46.99,15.499", current_only=True)
            print(f"get_forecast(current_only=True): {data}")
            # get forecast for the default station (closest station) with all parameters
            data = await zamg_instance.get_forecast(current_only=False)
            print(f"get_forecast(current_only=False): {data}")

    except ZamgError as exc:
        print(exc)


if __name__ == "__main__":
    asyncio.run(main())

```

The forecast contains the GeoSphere Austria weather symbol (`sy` parameter)
as a numeric code. It is automatically translated into a textual description
(`sy_text`) and a [Home Assistant weather condition](https://www.home-assistant.io/integrations/weather/#condition-mapping)
(`condition`). The translation helpers can also be used directly:

```python
from zamg import symbol_to_condition, symbol_to_text

print(symbol_to_text(3))  # "Partly cloudy"
print(symbol_to_text(3, lang="de"))  # "Wolkig"
print(symbol_to_condition(3))  # "partlycloudy"
```

The official (German) symbol code list is documented in
[Geosphere-Austria/dataset-api-docs#30](https://github.com/Geosphere-Austria/dataset-api-docs/issues/30).

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](https://github.com/killer0071234/python-zamg/blob/master/CONTRIBUTING.md)

## Contributors

Thanks to everyone who has contributed to this project:

- [Daniel Gangl (@killer0071234)](https://github.com/killer0071234) – maintainer
- [Tim-Matthias Klecka (@tklecka)](https://github.com/tklecka)
- [Daniel Lang (@dlang-geosphereat)](https://github.com/dlang-geosphereat)
- [Felix Hochgruber (@felix-hoc)](https://github.com/felix-hoc)
- [Marc Mueller (@cdce8p)](https://github.com/cdce8p)

See the full list on the [contributors page](https://github.com/killer0071234/python-zamg/graphs/contributors).

## Credits

Code template to read dataset API was mainly taken from [@LuisTheOne](https://github.com/LuisThe0ne)'s [zamg-api-cli-client][zamg_api_cli_client]

[Dataset API Dokumentation][dataset_api_doc]

---

[black]: https://github.com/psf/black
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/killer0071234/python-zamg.svg?style=for-the-badge
[commits]: https://github.com/killer0071234/python-zamg/commits/main
[codecov-shield]: https://img.shields.io/codecov/c/gh/killer0071234/python-zamg?style=for-the-badge&token=O5YDLF0X9G
[codecov]: https://codecov.io/gh/killer0071234/python-zamg
[license-shield]: https://img.shields.io/github/license/killer0071234/python-zamg.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-@killer0071234-blue.svg?style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/killer0071234/python-zamg.svg?style=for-the-badge
[releases]: https://github.com/killer0071234/python-zamg/releases
[user_profile]: https://github.com/killer0071234
[zamg_api_cli_client]: https://github.com/LuisThe0ne/zamg-api-cli-client
[dataset_api_doc]: https://github.com/Geosphere-Austria/dataset-api-docs

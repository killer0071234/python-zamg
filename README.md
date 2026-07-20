# python-zamg

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]
[![Code Coverage][codecov-shield]][codecov]

[![Project Maintenance][maintenance-shield]][user_profile]

Python library to read 10 min weather data from GeoSphere Austria former ZAMG

## About

This package allows you to read the weather data from weather stations of GeoSphere Austria weather service.
GeoSphere Austria joins Zentralanstalt für Meteorologie und Geodynamik (ZAMG) and the Geologische Bundesanstalt (GBA)
since 1st January 2023.

## Installation

```bash
pip install zamg
```

## Usage

Simple usage example to fetch specific data from the closest station.

```python
"""Asynchronous Python client for GeoSphere Austria weather data."""

import asyncio

import src.zamg.zamg
from src.zamg.exceptions import ZamgError


async def main():
    """Sample of getting data"""
    try:
        async with src.zamg.zamg.ZamgData() as zamg_instance:
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
            print("last update: %s", zamg_instance.last_update)
    except ZamgError as exc:
        print(exc)


if __name__ == "__main__":
    asyncio.run(main())

```

Simple usage example to fetch weather forecast for a specific location.

```python
"""Asynchronous Python client for GeoSphere Austria forecast weather data."""

import asyncio

import src.zamg.zamg
from src.zamg.exceptions import ZamgError


async def main():
    """Sample of getting data"""
    try:
        async with src.zamg.zamg.ZamgData() as zamg_instance:
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

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](https://github.com/killer0071234/python-zamg/blob/master/CONTRIBUTING.md)

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

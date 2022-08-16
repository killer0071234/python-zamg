# python-zamg

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]

[![Project Maintenance][maintenance-shield]][user_profile]

Python library to read hourly weather data from ZAMG

## About

This package allows you to read the weather data from the major weather stations of ZAMG weather service.
ZAMG is the Zentralanstalt für Meteorologie und Geodynamik in Austria.

## Installation

```bash
pip install zamg
```

## Usage

```python
import asyncio
from os import curdir
import src.zamg.zamg

async def main():
    """Sample of getting data"""
    async with src.zamg.zamg.ZamgData() as zamg:
        data = await zamg.closest_station(46.99, 15.499, curdir)
        print(f"closest_station = {data} -> {zamg.get_data('Name', data)}")
        print("---------- Weather for all stations")
        stations = await zamg.zamg_stations(curdir)
        for station in stations:
            print(f"{station} -> {stations[station][2]}")
            print(f"      ->  T:      {zamg.get_data('T °C', station)} °C")
            print(f"      ->  RF:     {zamg.get_data('RF %', station)} %")
            print(f"      ->  LDstat: {zamg.get_data('LDstat hPa', station)} hPa")
            print(f"      ->  LDred:  {zamg.get_data('LDred hPa', station)} hPa")
            print(f"      ->  WG:     {zamg.get_data('WG km/h', station)} km/h")
            print(f"      ->  WSG:    {zamg.get_data('WSG km/h', station)} km/h")
            print(f"      ->  SO:     {zamg.get_data('SO %', station)} %")
            print(f"      ->  TP:     {zamg.get_data('TP °C', station)} °C")

        print(
            f"---------- Weather for a specific station ({zamg.get_data('Name', data)})"
        )
        zamg.set_default_station(data)
        print(f"T °C = {zamg.get_data('T °C')} °C")
        print(f"RF % = {zamg.get_data('RF %')} %")
        print(f"LDstat hPa = {zamg.get_data('LDstat hPa')} hPa")
        print(f"LDred hPa = {zamg.get_data('LDred hPa')} hPa")
        print(f"WG km/h = {zamg.get_data('WG km/h')} km/h")
        print(f"WSG km/h = {zamg.get_data('WSG km/h')} km/h")
        print(f"SO % = {zamg.get_data('SO %')} %")
        print(f"TP °C = {zamg.get_data('TP °C')} °C")

if __name__ == "__main__":
    asyncio.run(main())
```

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](https://github.com/killer0071234/python-zamg/blob/master/CONTRIBUTING.md)

[black]: https://github.com/psf/black
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/killer0071234/python-zamg.svg?style=for-the-badge
[commits]: https://github.com/killer0071234/python-cybro/commits/main
[license-shield]: https://img.shields.io/github/license/killer0071234/python-zamg.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-@killer0071234-blue.svg?style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/killer0071234/python-zamg.svg?style=for-the-badge
[releases]: https://github.com/killer0071234/python-zamg/releases
[user_profile]: https://github.com/killer0071234

# python-zamg

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

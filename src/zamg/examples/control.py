# pylint: disable=W0621
"""Asynchronous Python client for ZAMG weather data."""

import asyncio
from os import curdir
import src.zamg.zamg


async def main():
    """Sample of getting data"""
    async with src.zamg.zamg.ZamgData() as zamg:
        data = await zamg.closest_station(46.99, 15.499, curdir)
        print(f"closest_station={data}")
        print(f"RF %={zamg.get_data(data, 'RF %')}")
        print(f"LDstat hPa={zamg.get_data(data, 'LDstat hPa')}")
        print(f"LDred hPa={zamg.get_data(data, 'LDred hPa')}")
        print(f"WG km/h={zamg.get_data(data, 'WG km/h')}")
        print(f"WSG km/h={zamg.get_data(data, 'WSG km/h')}")
        print(f"SO %={zamg.get_data(data, 'SO %')}")
        print(f"T °C={zamg.get_data(data, 'T °C')}")
        print(f"TP °C={zamg.get_data(data, 'TP °C')}")


if __name__ == "__main__":
    asyncio.run(main())

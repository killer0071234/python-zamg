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
        zamg.set_default_station(data)
        print("RF %=%s", zamg.get_data("RF %"))
        print("LDstat hPa=%s", zamg.get_data("LDstat hPa"))
        print("LDred hPa=%s", zamg.get_data("LDred hPa"))
        print("WG km/h=%s", zamg.get_data("WG km/h"))
        print("WSG km/h=%s", zamg.get_data("WSG km/h"))
        print("SO %=%s", zamg.get_data("SO %"))
        print("T °C=%s", zamg.get_data("T °C"))
        print("TP °C=%s", zamg.get_data("TP °C"))


if __name__ == "__main__":
    asyncio.run(main())

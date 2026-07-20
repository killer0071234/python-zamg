# pylint: disable=W0621
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

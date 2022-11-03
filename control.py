# pylint: disable=W0621
"""Asynchronous Python client for ZAMG weather data."""
import asyncio

import src.zamg.zamg


async def main():
    """Sample of getting data"""
    async with src.zamg.zamg.ZamgData() as zamg:
        data = await zamg.closest_station(46.99, 15.499)
        zamg.set_default_station(data)
        print("closest_station = " + str(zamg.get_station_name) + " / " + str(data))
        await zamg.update()

        print(f"---------- Weather for station {zamg.get_station_name} ({data})")
        for param in zamg.get_all_parameters():
            print(
                str(param)
                + " -> "
                + str(zamg.get_data(parameter=param, data_type="name"))
                + " -> "
                + str(zamg.get_data(parameter=param))
                + " "
                + str(zamg.get_data(parameter=param, data_type="unit"))
            )
        print("last update: %s", zamg.last_update)


if __name__ == "__main__":
    asyncio.run(main())

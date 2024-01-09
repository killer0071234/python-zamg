# pylint: disable=W0621
"""Asynchronous Python client for GeoSphere Austria weather data."""
import asyncio

import src.zamg.zamg
from src.zamg.exceptions import ZamgError


async def main():
    """Sample of getting data"""
    try:
        async with src.zamg.zamg.ZamgData() as zamg:
            # option to disable verify of ssl check
            zamg.verify_ssl = False
            # trying to read GeoSphere Austria station id of the closest station
            data = await zamg.closest_station(46.99, 15.499)
            # set closest station as default one to read
            zamg.set_default_station(data)
            print("closest_station = " + str(zamg.get_station_name) + " / " + str(data))
            # print list with all possible parameters
            print(f"Possible station parameters: {zamg.get_all_parameters()}")
            # set parameters directly
            zamg.station_parameters = "TL,SO"
            # or set parameters as list
            zamg.set_parameters(("TL", "SO"))
            # if none of the above parameters are set, all possible parameters are read
            # do an update
            await zamg.update()

            print(f"---------- Weather for station {zamg.get_station_name} ({data})")
            for param in zamg.get_parameters():
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
    except ZamgError as exc:
        print(exc)


if __name__ == "__main__":
    asyncio.run(main())

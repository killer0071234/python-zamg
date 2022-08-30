# pylint: disable=W0621
"""Asynchronous Python client for ZAMG weather data."""
import asyncio
import logging

import src.zamg.zamg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s (%(threadName)s) [%(name)s] %(message)s",
    datefmt="%y-%m-%d %H:%M:%S"
    # filename=('log.log'),
    # filemode=('w')
)
log = logging.getLogger(__name__)


async def main():
    """Sample of getting data"""
    async with src.zamg.zamg.ZamgData() as zamg:
        data = await zamg.closest_station(46.99, 15.499)
        log.info("closest_station = %s", str(data))
        zamg.set_default_station(data)
        await zamg.update()
        for param in zamg.get_all_parameters():
            name = zamg.get_data(parameter=param, data_type="name")
            unit = zamg.get_data(parameter=param, data_type="unit")
            val = zamg.get_data(parameter=param)
            log.info("%s --> %s %s", str(name), str(val), str(unit))
        log.info("last update: %s", zamg.last_update)


if __name__ == "__main__":
    asyncio.run(main())

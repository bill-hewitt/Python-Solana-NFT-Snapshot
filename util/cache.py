import json
import logging
from pathlib import Path


logger = logging.getLogger("nft_snapshot.cache")

CACHE_DIR = "cache"


# TODO: Make this a class and store the path as a var


def load_request_cache(cache_file_key: str) -> dict:
    """Load the previously-fetched data from the cache and return it.

    :param cache_file_key: Name of the file to write to in the cache
    :return: dict filled with token data fetched from the cache
    """
    filename = "{}_cache.json".format(cache_file_key)
    try:
        path = Path(CACHE_DIR) / filename
        with path.open() as file:
            cache_data = json.load(file)
            logger.debug("Loaded cache data from %s", filename)
            return cache_data
    except Exception as e:
        logger.debug("Unable to load cache file %s: %s", filename, e)
        return {}


def save_request_cache(cache_file_key: str, cache_data: dict) -> None:
    """Save the passed-in dictionary data to the cache, overwriting current contents.

    :param cache_file_key: Name of the file to write to in the cache
    :param cache_data: The full set of token data to write to the cache
    """
    filename = "{}_cache.json".format(cache_file_key)
    try:
        path = Path(CACHE_DIR)
        path.mkdir(exist_ok=True)
        path = path / filename
        with path.open("w") as file:
            json.dump(cache_data, file)
            logger.debug("Wrote cache data to %s", path)
    except Exception as e:
        logger.warning("Unable to write cache file %s: %s", filename, e)

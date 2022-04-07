import asyncio
import logging
import pickle
from pathlib import Path

logger = logging.getLogger("nft_snapshot.util.cache")

CACHE_DIR = "cache"


def write_token_list(token_file_name, token_list):
    """

    :param token_file_name:
    :param token_list:
    """
    with open(token_file_name, "w") as token_list_file:
        token_list_file.write("\n".join(token_list))


def read_token_list(token_file_name) -> list[str]:
    """

    :param token_file_name:
    :return: List of token strings fetched from the file
    """
    with open(token_file_name) as token_list_file:
        return token_list_file.read().splitlines()


class TokenCache:
    filename: str
    path: Path
    _initialized: bool = False

    def initialize(self, cache_file_key):
        self._initialized = True
        self.filename = "{}_cache.p".format(cache_file_key)

        # Make sure the cache directory and file exist
        self.path = Path(CACHE_DIR)
        self.path.mkdir(exist_ok=True)
        self.path = self.path / self.filename

    async def periodic_cache_task(self, all_tokens: dict):
        while True:
            await asyncio.sleep(20)
            self.save(all_tokens)

    def load(self) -> dict:
        """Load the previously-fetched data from the cache and return it.

        :return: dict filled with token data fetched from the cache
        """
        if not self._initialized:
            raise RuntimeError("Trying to use cache before initializing it")

        try:
            with self.path.open("rb") as file:
                all_tokens = pickle.load(file)
                logger.debug("Loaded cache data from %s", self.filename)
                return all_tokens
        except Exception as e:
            logger.debug("Unable to load cache file %s: %s", self.filename, e)
            return {}

    def save(self, all_tokens: dict) -> None:
        """Save the passed-in dictionary data to the cache, overwriting current contents.

        :param all_tokens: The full set of token data to write to the cache
        """
        if not self._initialized:
            raise RuntimeError("Trying to use cache before initializing it")

        try:
            with self.path.open("wb") as file:
                pickle.dump(all_tokens, file)
                logger.debug("Wrote cache data to %s", self.path)
        except Exception as e:
            logger.warning("Unable to write cache file %s: %s", self.filename, e)


token_cache = TokenCache()

import logging
from time import sleep

import aiohttp
from tenacity import after_log
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_random_exponential


logger = logging.getLogger("nft_snapshot.http_helpers")


def create_http_client():
    """

    :return:
    """
    conn = aiohttp.TCPConnector(limit=50)
    timeout = aiohttp.ClientTimeout(total=60)
    return aiohttp.ClientSession(connector=conn, timeout=timeout)


@retry(
    stop=stop_after_attempt(10),
    after=after_log(logger, logging.DEBUG),
    wait=wait_random_exponential(min=4, max=32),
)
async def async_http_request(session: aiohttp.ClientSession, url: str) -> dict:
    """

    :param session:
    :param url:
    :return:
    """
    async with session.get(url) as resp:
        if resp.status != 200:
            if resp.status == 429:
                # If we failed for some reason, try again
                logger.debug(
                    "Got status code %s for url %s, sleeping and retrying", resp.status, url
                )
                sleep(3)
                raise TimeoutError()
            else:
                logger.error(
                    "HTTP request for %s failed with status %s: %s", url, resp.status, resp.json()
                )
        logging.debug("Successful response for url %s", url)
        body = await resp.json()
    return body

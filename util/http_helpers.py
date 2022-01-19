import logging

import aiohttp
from tenacity import after_log
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_random_exponential


logger = logging.getLogger("nft_snapshot.http_helpers")


class RateLimitingError(RuntimeError):
    pass


class RequestFailedError(RuntimeError):
    pass


def create_http_client() -> aiohttp.ClientSession:
    """Create the aiohttp client used to make asynchronous HTTP requests, configured to play nice with our needs

    :return: an aiohttp.ClientSession
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
    """Make an HTTP request to fetch a requested resource

    :param session: The client session used to make requests
    :param url: The URL to fetch data from
    :return: The response dict that came back
    """
    async with session.get(url) as resp:
        if resp.status != 200:
            if resp.status == 429:
                # If we failed for some reason, try again
                logger.debug(
                    "Got status code %s for url %s, sleeping and retrying", resp.status, url
                )
                raise RateLimitingError()
            else:
                logger.error(
                    "HTTP request for %s failed with status %s: %s", url, resp.status, resp.json()
                )
                raise RequestFailedError()
        logging.debug("Successful response for url %s", url)
        body = await resp.json()
    return body
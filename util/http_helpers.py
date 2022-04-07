import logging
import resource

import aiohttp
from tenacity import after_log
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_random_exponential


logger = logging.getLogger("nft_snapshot.util.http_helpers")


class RateLimitingError(RuntimeError):
    pass


class RequestFailedError(RuntimeError):
    pass


def create_http_client() -> aiohttp.ClientSession:
    """Create the aiohttp client used to make asynchronous HTTP requests, configured to play nice with our needs

    :return: an aiohttp.ClientSession
    """

    # Bump up the open file limits or you'll get a bunch of DNS-looking errors
    # From https://github.com/aio-libs/aiohttp/issues/3549#issuecomment-603103175
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (2**14, resource.RLIM_INFINITY))
    except ValueError:
        logger.warning("Unable to raise open file limits")

    conn = aiohttp.TCPConnector(limit=100)
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
                logger.debug(
                    "Got status code %s for url %s, sleeping and retrying", resp.status, url
                )
                raise RateLimitingError()
            elif resp.status == 404:
                logger.debug(
                    "Got status code %s for url %s, has metadata been uploaded?", resp.status, url
                )
                return {}
            else:
                logger.error(
                    "HTTP request for %s failed with status %s: %s", url, resp.status, resp.json()
                )
                raise RequestFailedError()
        logging.debug("Successful response for url %s", url)
        body = await resp.json()
    return body

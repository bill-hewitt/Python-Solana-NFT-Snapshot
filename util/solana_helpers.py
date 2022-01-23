import base64
import logging
import time

import base58
from aiolimiter import AsyncLimiter
from solana.publickey import PublicKey
from solana.rpc import api
from solana.rpc import async_api
from solana.rpc.types import DataSliceOpts
from solana.rpc.types import MemcmpOpts
from tenacity import after_log
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_random_exponential

from util import metadata


logger = logging.getLogger("nft_snapshot.solana_helpers")

SOLANA_RPC_ENDPOINT = "https://ssc-dao.genesysgo.net/"


@retry(
    stop=stop_after_attempt(3),
    after=after_log(logger, logging.DEBUG),
    wait=wait_random_exponential(min=1, max=10),
)
def get_token_list_from_candymachine_id(cm_id: str, use_v2: bool = False) -> list:
    """Fetch the list of tokens minted from the given Candy Machine ID
    Adapted from https://github.com/solana-dev-adv/solana-cookbook/tree/master/code/nfts/nfts-mint-addresses

    :param cm_id: The Candy Machine ID to fetch tokens for
    :param use_v2: Whether the Candy Machine uses the v2 codebase or not (changes fetching methodology)
    :return: A list of the token IDs
    """
    start_time = time.time()

    logger.info(f"Fetching tokens from CM {cm_id} (v2? {use_v2})")

    client = api.Client(SOLANA_RPC_ENDPOINT, timeout=120)

    # Bunch of constants to get us looking in the right place...
    MAX_NAME_LENGTH = 32
    MAX_URI_LENGTH = 200
    MAX_SYMBOL_LENGTH = 10
    MAX_CREATOR_LEN = 32 + 1 + 1
    MAX_CREATOR_LIMIT = 5
    MAX_DATA_SIZE = (
        4
        + MAX_NAME_LENGTH
        + 4
        + MAX_SYMBOL_LENGTH
        + 4
        + MAX_URI_LENGTH
        + 2
        + 1
        + 4
        + MAX_CREATOR_LIMIT * MAX_CREATOR_LEN
    )
    MAX_METADATA_LEN = 1 + 32 + 32 + MAX_DATA_SIZE + 1 + 1 + 9 + 172
    CREATOR_ARRAY_START = (
        1 + 32 + 32 + 4 + MAX_NAME_LENGTH + 4 + MAX_URI_LENGTH + 4 + MAX_SYMBOL_LENGTH + 2 + 1 + 4
    )

    TOKEN_METADATA_PROGRAM = PublicKey("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
    CANDY_MACHINE_V2_PROGRAM = PublicKey("cndy3Z4yapfJBmL3ShUp5exZKqR3z33thTzeNMm2gRZ")

    cm_pk = PublicKey(cm_id)
    if use_v2:
        cm_pk = cm_pk.find_program_address(
            [b"candy_machine", bytes(cm_pk)], CANDY_MACHINE_V2_PROGRAM
        )[0]

    # Set some options for exactly where to look within the data, and then fetch it
    memcmp_opts = [MemcmpOpts(offset=CREATOR_ARRAY_START, bytes=str(cm_pk))]
    data_slice_opts = DataSliceOpts(offset=33, length=32)
    metadata_accounts = client.get_program_accounts(
        TOKEN_METADATA_PROGRAM,
        encoding="base64",
        data_slice=data_slice_opts,
        data_size=MAX_METADATA_LEN,
        memcmp_opts=memcmp_opts,
    )
    logging.info("--- %s seconds ---", (time.time() - start_time))

    return [
        str(base58.b58encode(base64.b64decode(v["account"]["data"][0])), "UTF-8")
        for v in metadata_accounts["result"]
    ]


def create_solana_client() -> async_api.AsyncClient:
    """Make an async Solana client configured for our purposes

    :return: AsyncClient
    """
    return async_api.AsyncClient(SOLANA_RPC_ENDPOINT, timeout=30)


@retry(
    stop=stop_after_attempt(3),
    after=after_log(logger, logging.DEBUG),
    wait=wait_random_exponential(min=1, max=10),
)
async def get_holder_info_from_solana_async(
    client: async_api.AsyncClient, data_dict: dict, limiter: AsyncLimiter
) -> dict:
    """Fetch info about a token's holder from the Solana network

    :param client: The Solana client used to make requests
    :param data_dict: The data sub-dict for the single desired token
    :param limiter: An AsyncLimiter used to prevent hitting request limits, and generally be a good citizen.
    :return: The data dict with the "holders" key populated with response data
    """
    async with limiter:
        largest_account = await client.get_token_largest_accounts(data_dict["token"])
        if largest_account["result"]["value"]:
            account_info = await client.get_account_info(
                largest_account["result"]["value"][0]["address"], encoding="jsonParsed"
            )
            data_dict["holders"] = account_info["result"]["value"]["data"]["parsed"]
            return data_dict
        else:
            logger.warning(
                "No holder info for {}. Response: {}".format(data_dict["token"], largest_account)
            )
            data_dict["holders"] = {}
            return data_dict


@retry(
    stop=stop_after_attempt(3),
    after=after_log(logger, logging.DEBUG),
    wait=wait_random_exponential(min=1, max=10),
)
async def get_account_info_from_solana_async(
    client: async_api.AsyncClient, data_dict: dict, limiter: AsyncLimiter
) -> dict:
    """Fetch info about a token's metadata account from the Solana network

    :param client: The Solana client used to make requests
    :param data_dict: The data sub-dict for the single desired token
    :param limiter: An AsyncLimiter used to prevent hitting request limits, and generally be a good citizen.
    :return: The data dict with the "account" key populated with response data
    """
    async with limiter:
        metadata_account = metadata.get_metadata_account(data_dict["token"])
        data = await client.get_account_info(metadata_account)
        decoded_data = base64.b64decode(data["result"]["value"]["data"][0])
        unpacked_data = metadata.unpack_metadata_account(decoded_data)

        # This unfortunately leaves us with bytes, which are not JSON-serializable for caching...
        for k, v in unpacked_data.items():
            try:
                unpacked_data[k] = v.decode()
            except (UnicodeDecodeError, AttributeError):
                pass
        data_dict["account"] = unpacked_data
        return data_dict

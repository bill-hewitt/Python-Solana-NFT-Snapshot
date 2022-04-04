import base64
import itertools
import logging
import time

import base58
from aiolimiter import AsyncLimiter
from solana.publickey import PublicKey
from solana.rpc import api
from solana.rpc import async_api
from solana.rpc.types import MemcmpOpts
from tenacity import after_log
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_random_exponential
from tqdm import tqdm

from util import metadata
from util.token import Token

# from solana.rpc.types import DataSliceOpts


logger = logging.getLogger("nft_snapshot.solana_helpers")

SOLANA_RPC_ENDPOINT = "https://ssc-dao.genesysgo.net/"

# Separate RPC endpoint for getProgramAccount, since other providers have it turned off
# Also much faster for requests it supports, so generally use this one
GPA_RPC_ENDPOINT = "https://rpc.theindex.io"


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

    client = api.Client(GPA_RPC_ENDPOINT, timeout=30)

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
    # NOTE: data_slice doesn't seem to do anything anymore, which seems...bad? Anyway, I just
    #     filter in the output below so we're all good.
    # data_slice_opts = DataSliceOpts(offset=33, length=32)
    metadata_accounts = client.get_program_accounts(
        TOKEN_METADATA_PROGRAM,
        encoding="base64",
        # data_slice=data_slice_opts,
        data_size=MAX_METADATA_LEN,
        memcmp_opts=memcmp_opts,
    )
    logging.info("--- %s seconds ---", (time.time() - start_time))

    return [
        str(base58.b58encode(base64.b64decode(v["account"]["data"][0])[33:65]), "UTF-8")
        for v in metadata_accounts["result"]
    ]


def create_solana_client() -> async_api.AsyncClient:
    """Make an async Solana client configured for our purposes

    :return: AsyncClient
    """
    return async_api.AsyncClient(GPA_RPC_ENDPOINT, timeout=30)


@retry(
    stop=stop_after_attempt(3),
    after=after_log(logger, logging.DEBUG),
    wait=wait_random_exponential(min=1, max=10),
)
async def get_token_account_from_solana_async(
    client: async_api.AsyncClient, token: Token, limiter: AsyncLimiter
) -> Token:
    """Fetch info about a token's holder from the Solana network

    :param client: The Solana client used to make requests
    :param token: The Token object for which data is being requested
    :param limiter: An AsyncLimiter used to prevent hitting request limits, and generally be a good citizen.
    :return: The data dict with the "holders" key populated with response data
    """
    async with limiter:
        largest_account_resp = await client.get_token_largest_accounts(token.token)
    if not largest_account_resp["result"]["value"]:
        token_account = ""
    else:
        token_account = largest_account_resp["result"]["value"][0]["address"]
    token.token_account = token_account
    return token


def get_holder_account_info_from_solana(all_tokens: dict) -> dict:
    """Fetch info about the token account for all tokens in a batched fashion

    :param all_tokens: A dict of all the token data being operated upon
    :return: The all_tokens dict populated for each token
    """
    owner_accounts = {}
    for token in all_tokens.values():
        if token.holder_address is not None:
            continue
        if token.token_account == "":
            token.holder_address = ""
            token.amount = 0
            continue
        if not owner_accounts.get(token.token_account):
            owner_accounts[token.token_account] = []
        owner_accounts[token.token_account].append(token.token)

    # Chunk into sets of 100
    client = api.Client(SOLANA_RPC_ENDPOINT, timeout=30)
    chunks = list(itertools.zip_longest(*[iter(owner_accounts.keys())] * 100))
    for chunk in tqdm(chunks, total=len(chunks)):
        chunk = list(chunk)
        while chunk and chunk[-1] is None:
            chunk.pop()
        result = client.get_multiple_accounts(chunk, encoding="jsonParsed")
        for i, owner_account in enumerate(chunk):
            tokens = owner_accounts[owner_account]
            for token in tokens:
                if not result["result"]["value"][i]:
                    all_tokens[token].holder_address = ""
                    all_tokens[token].amount = 0
                else:
                    token_holders = result["result"]["value"][i]["data"]["parsed"]

                    # Why is this empty sometimes? Because tokens get nuked, so there is no "holder" to fetch
                    if token_holders.get("info") and token_holders["info"].get("owner"):
                        all_tokens[token].holder_address = token_holders["info"]["owner"]
                        all_tokens[token].amount = (
                            token_holders["info"].get("tokenAmount").get("amount")
                        )
                    else:
                        all_tokens[token].holder_address = ""
                        all_tokens[token].amount = 0
    return all_tokens


@retry(
    stop=stop_after_attempt(3),
    after=after_log(logger, logging.DEBUG),
    wait=wait_random_exponential(min=1, max=10),
)
async def get_account_info_from_solana_async(
    client: async_api.AsyncClient, token: Token, limiter: AsyncLimiter
) -> Token:
    """Fetch info about a token's metadata account from the Solana network

    :param client: The Solana client used to make requests
    :param token: The Token object for which data is being requested
    :param limiter: An AsyncLimiter used to prevent hitting request limits, and generally be a good citizen.
    :return: The data dict with the "account" key populated with response data
    """
    async with limiter:
        metadata_account = metadata.get_metadata_account(token.token)
        data = await client.get_account_info(metadata_account)
        decoded_data = base64.b64decode(data["result"]["value"]["data"][0])
        unpacked_data = metadata.unpack_metadata_account(decoded_data)

        if unpacked_data.get("data") is not None:
            token.name = unpacked_data["data"].get("name")
            token.id = token.name[token.name.find("#") + 1 : :]
            token.data_uri = unpacked_data["data"].get("uri")
        return token

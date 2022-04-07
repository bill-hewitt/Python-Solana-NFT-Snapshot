"""
Script to fetch data about an NFT mint on the Solana network. Capabilities include:
- Fetching mint token list from a CandyMachine ID
- Printing an ordered list of how many NFTs each wallet is holding
- Printing a rarity assessment of the different traits from metadata
- Outputting a CSV snapshotting token info and current holders

Originally based on https://github.com/GMnky/Python-Solana-NFT-Snapshot but significantly overhauled since
"""
import asyncio
import logging
import time
from argparse import ArgumentParser
from typing import Callable

import aiohttp
import tqdm
from aiolimiter import AsyncLimiter

from util import http_helpers as hh
from util import output
from util import solana_helpers as sh
from util.cache import read_token_list
from util.cache import token_cache
from util.cache import write_token_list
from util.token import get_attribute_counts
from util.token import Token

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    filename="app.log",
)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger("").addHandler(ch)

logger = logging.getLogger("nft_snapshot")


def main(
    get_token_list: bool,
    get_holder_counts: bool,
    get_attribute_distribution: bool,
    get_holder_snapshot: bool,
    get_rarity: bool,
    candymachine_id: str,
    token_id: str,
    cmv2: bool,
    outfile_name: str,
    token_file_name: str,
    bust_cache: bool,
) -> None:
    """Central piece of the script: run the specified pieces of functionality specified from the options passed in.
    Will fetch needed data, if required (although fetched data is cached to disk so analysis can be run multiple
    times from those snapshots).

    :param get_token_list: Whether to fetch the token list for the given CM ID (requires candymachine_id)
    :param get_holder_counts: Whether to print the number of NFTs held per wallet
    :param get_attribute_distribution: Whether to print the rarity of all attributes found in the metadata
    :param get_holder_snapshot: Whether to output a CSV snapshot of information for each token
    :param get_rarity: Whether to display rarity information for the given token
    :param candymachine_id: The Candy Machine ID to fetch tokens for
    :param token_id: The token to fetch rarity information for
    :param cmv2: Whether the specified candymachine_id uses v2 or not
    :param outfile_name: Name to output the CSV snapshot to
    :param token_file_name: Name to output the token list to
    :param bust_cache: Whether to clear out the cache prior to running so you get fresh data
    :return:
    """
    token_list = []
    all_tokens = {}

    # If required, bust cache. otherwise, load it
    token_cache.initialize(token_file_name.split(".")[0])
    if bust_cache:
        # all_tokens is empty, so we can just overwrite the cache with it
        token_cache.save(all_tokens)
    else:
        all_tokens = token_cache.load()

    if get_token_list:
        if candymachine_id:
            token_list = sh.get_token_list_from_candymachine_id(candymachine_id, cmv2)
        else:
            print("ERROR: You asked for the token list but didn't give CM ID to look up by")
            exit(1)

        # Write the token file (note that this will blow away whatever is there now)
        write_token_list(token_file_name, token_list)

    # If we're looking up based on an existing token list from disk, read it in
    if not token_list:
        token_list = read_token_list(token_file_name)

    for token in token_list:
        if token not in all_tokens:
            all_tokens[token] = Token(token)

    holders_populated = False
    accounts_populated = False

    if get_holder_counts:
        if not holders_populated:
            populate_holders_details_async(all_tokens)
            holders_populated = True
        print(holder_counts(all_tokens))

    if get_attribute_distribution:
        if not accounts_populated:
            populate_account_details_async(all_tokens)
            accounts_populated = True
        print(attribute_distribution(all_tokens))

    if get_holder_snapshot:
        if not holders_populated:
            populate_holders_details_async(all_tokens)
            holders_populated = True
        if not accounts_populated:
            populate_account_details_async(all_tokens)
            accounts_populated = True
        output.holder_snapshot(all_tokens, outfile_name)

    if get_rarity:
        if not token_id:
            raise ValueError("No tokenid supplied")
        if not holders_populated:
            populate_holders_details_async(all_tokens)
            holders_populated = True
        if not accounts_populated:
            populate_account_details_async(all_tokens)
            accounts_populated = True
        print(output.format_token_rarity(token_id, all_tokens))


def populate_holders_details_async(all_tokens: dict) -> dict:
    """Fetch data about which wallets own the NFTs specified by the given token IDs. Fetched data is cached at the end.

    :param all_tokens: A dict of all the token data being operated upon
    :return: The all_tokens dict populated for each token
    """
    start_time = time.time()
    logging.info("\nPopulating token account details...")
    asyncio.run(
        fetch_token_data_from_network_async(
            sh.create_solana_client,
            all_tokens,
            "token_account",
            sh.get_token_account_from_solana_async,
        )
    )
    token_cache.save(all_tokens)
    logging.info("--- %s seconds ---", (time.time() - start_time))

    start_time = time.time()
    logging.info("\nPopulating holders details...")
    result = sh.get_holder_account_info_from_solana(all_tokens)
    token_cache.save(all_tokens)
    logging.info("--- %s seconds ---", (time.time() - start_time))
    return result


def populate_account_details_async(all_tokens: dict) -> dict:
    """Fetch metadata about the given token IDs, including attributes. Fetched data is cached at the end.

    :param all_tokens: A dict of all the token data being operated upon
    :return: The all_tokens dict populated for each token
    """
    start_time = time.time()
    logging.info("\nPopulating account details...")
    asyncio.run(
        fetch_token_data_from_network_async(
            sh.create_solana_client,
            all_tokens,
            "name",
            sh.get_account_info_from_solana_async,
        )
    )
    token_cache.save(all_tokens)
    logging.info("--- %s seconds ---", (time.time() - start_time))

    start_time = time.time()
    logging.info("\nPopulating token metadata details...")
    result = asyncio.run(
        fetch_token_data_from_network_async(
            hh.create_http_client, all_tokens, "image", get_arweave_metadata
        )
    )
    token_cache.save(all_tokens)
    logging.info("--- %s seconds ---", (time.time() - start_time))

    return result


async def fetch_token_data_from_network_async(
    create_client_fn: Callable, all_tokens: dict, key: str, get_data_fn: Callable
) -> dict:
    """Method to abstract the async client and task management for data fetching. Creates a task for each token

    :param create_client_fn: Function that creates and returns the async network client used to fetch data
    :param all_tokens: A dict of all the token data being operated upon
    :param key: The key in token_data to save the fetched data to
    :param get_data_fn: The function to call in order to fetch the data
    :return: The all_tokens dict populated for each token
    """
    limiter = AsyncLimiter(100, 1)
    cache_task = asyncio.create_task(token_cache.periodic_cache_task(all_tokens))
    async with create_client_fn() as client:
        tasks = []
        for token in all_tokens.keys():
            if getattr(all_tokens[token], key) is None:
                tasks.append(asyncio.create_task(get_data_fn(client, all_tokens[token], limiter)))
        [await f for f in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks))]
    try:
        cache_task.cancel()
    except asyncio.CancelledError:
        pass
    return all_tokens


async def get_arweave_metadata(
    http_client: aiohttp.ClientSession, token: Token, limiter: AsyncLimiter
) -> Token:
    """Fetches token metadata for a particular token (primarily used for traits) from Arweave if a URL is present.

    :param http_client: The aiohttp client used to make requests
    :param token: The Token instance for the single desired token
    :param limiter: An AsyncLimiter used to prevent hitting request limits, and generally be a good citizen.
    :return: The data dict with the "arweave" key populated with response data (if applicable)
    """
    if token.data_uri:
        async with limiter:
            response = await hh.async_http_request(http_client, token.data_uri)
            token.image = response.get("image")
            attributes = response.get("attributes")
            if attributes:
                token.traits = {}
                for attribute in attributes:
                    trait_type = attribute["trait_type"]
                    value = attribute["value"] if attribute["value"] is not None else ""
                    token.traits[trait_type] = value
    else:
        token.image = ""
        token.traits = {}

    return token


def holder_counts(all_tokens: dict) -> str:
    """Analyze the token data to determine how many NFTs are in each wallet, and print it out.

    :param all_tokens: The preassembled data dict for all tokens
    :return: A string containing the formatted output
    """
    counts = {}
    for token in all_tokens.values():
        if not counts.get(token.holder_address):
            counts[token.holder_address] = 0
        counts[token.holder_address] += 1

    return output.format_biggest_holders(len(all_tokens), counts)


def attribute_distribution(all_tokens: dict) -> str:
    """Analyze the token data to determine the statistical rarity of the possible NFT traits, and print it out.

    :param all_tokens: The preassembled data dict for all tokens
    :return: A string containing the formatted output
    """
    trait_map = output.get_trait_map(all_tokens)
    token_with_attr_count, attribute_counts = get_attribute_counts(trait_map, all_tokens)
    return output.format_trait_frequency(token_with_attr_count, attribute_counts)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "token_file",
        metavar="TOKEN_FILE",
        type=str,
        help="file to read token IDs from (and write them to, if applicable)",
    )
    parser.add_argument(
        "-t",
        dest="token_list",
        action="store_true",
        default=False,
        help="get the token list for the given CM ID (requires passing --cmid)",
    )
    parser.add_argument(
        "-o",
        dest="holder_counts",
        action="store_true",
        default=False,
        help="get and print the overall holder counts",
    )
    parser.add_argument(
        "-a",
        dest="attributes",
        action="store_true",
        default=False,
        help="get and print the overall metadata attribute distribution",
    )
    parser.add_argument(
        "-s",
        dest="snapshot",
        action="store_true",
        default=False,
        help="get and output the snapshot file to the outfile name from -f",
    )
    parser.add_argument(
        "-r",
        dest="rarity",
        action="store_true",
        default=False,
        help="get and output the rarity of the given token ID (requires passing --tokenid)",
    )
    parser.add_argument(
        "-f",
        "--file",
        dest="outfile_name",
        default="snapshot.csv",
        help="write snapshot to FILE (defaults to snapshot.csv)",
        metavar="SNAP_FILE",
    )
    parser.add_argument(
        "--cmid",
        dest="candymachine_id",
        help="use CANDYMACHINE_ID to fetch tokens",
        metavar="CANDYMACHINE_ID",
    )
    parser.add_argument(
        "--tokenid",
        dest="token_id",
        help="the token ID to fetch rarity information for",
        metavar="TOKEN_ID",
    )
    parser.add_argument(
        "--cmv2",
        dest="cm_v2",
        action="store_true",
        default=False,
        help="use Candy Machine v2 method to fetch tokens from CM ID",
    )
    parser.add_argument(
        "--bust-cache",
        dest="bust_cache",
        action="store_true",
        default=False,
        help="clear out any existing cache data for this token file",
    )

    args = parser.parse_args()

    main(
        args.token_list,
        args.holder_counts,
        args.attributes,
        args.snapshot,
        args.rarity,
        args.candymachine_id,
        args.token_id,
        args.cm_v2,
        args.outfile_name,
        args.token_file,
        args.bust_cache,
    )

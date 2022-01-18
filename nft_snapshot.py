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
from optparse import OptionParser
from typing import Callable

import aiohttp
import tqdm
from aiolimiter import AsyncLimiter
from solana.rpc.async_api import AsyncClient

from util import cache
from util import http_helpers as hh
from util import output
from util import solana_helpers as sh

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
    candymachine_id: str,
    cmv2: bool,
    outfile_name: str,
    token_file_name: str,
    bust_cache: bool,
) -> None:
    """

    :param get_token_list:
    :param get_holder_counts:
    :param get_attribute_distribution:
    :param get_holder_snapshot:
    :param candymachine_id:
    :param cmv2:
    :param outfile_name:
    :param token_file_name:
    :param bust_cache:
    :return:
    """
    cache_file_key = token_file_name
    token_list = []

    if get_token_list:
        if candymachine_id:
            token_list = sh.get_token_list_from_candymachine_id(candymachine_id, cmv2)
        else:
            print("ERROR: You asked for the token list but didn't give CM ID to look up by")
            exit(1)

        # Write the token file (note that this will blow away whatever is there now)
        with open(token_file_name, "w") as token_list_file:
            token_list_file.write("\n".join(token_list))

    # If we're looking up based on an existing token list from disk, read it in
    if not token_list:
        with open(token_file_name) as token_list_file:
            token_list = token_list_file.read().splitlines()

    holders_populated = False
    accounts_populated = False

    # If required, bust cache. otherwise, load it
    if bust_cache:
        all_token_data = {}
        cache.save_request_cache(cache_file_key, all_token_data)
    else:
        all_token_data = cache.load_request_cache(cache_file_key)

    for token in token_list:
        if token not in all_token_data:
            all_token_data[token] = {"token": token}

    if get_holder_counts:
        if not holders_populated:
            populate_holders_details_async(all_token_data, cache_file_key)
            holders_populated = True
        holder_counts(all_token_data)

    if get_attribute_distribution:
        if not accounts_populated:
            populate_account_details_async(all_token_data, cache_file_key)
            accounts_populated = True
        attribute_distribution(all_token_data)

    if get_holder_snapshot:
        if not holders_populated:
            populate_holders_details_async(all_token_data, cache_file_key)
            holders_populated = True
        if not accounts_populated:
            populate_account_details_async(all_token_data, cache_file_key)
            accounts_populated = True
        output.holder_snapshot(all_token_data, outfile_name)


def populate_holders_details_async(all_token_data: dict, cache_file_key: str) -> dict:
    """

    :param all_token_data:
    :param cache_file_key:
    :return:
    """
    start_time = time.time()

    logging.info("\nPopulating holders details...")

    async def inner(token_data):
        limiter = AsyncLimiter(100, 1)
        async with AsyncClient(sh.SOLANA_RPC_ENDPOINT, timeout=60) as client:
            tasks = []
            for token in token_data.keys():
                if token_data[token].get("holders") is None:
                    tasks.append(
                        asyncio.create_task(
                            sh.get_holder_info_from_solana_async(client, token_data[token], limiter)
                        )
                    )
            [await f for f in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks))]
        cache.save_request_cache(cache_file_key, token_data)
        return token_data

    result = asyncio.run(inner(all_token_data))
    cache.save_request_cache(cache_file_key, all_token_data)

    logging.info("--- %s seconds ---", (time.time() - start_time))
    return result


def populate_account_details_async(all_token_data: dict, cache_file_key: str) -> dict:
    """

    :param all_token_data:
    :param cache_file_key:
    :return:
    """

    async def inner(
        create_client_fn: Callable, token_data: dict, key: str, get_data_fn: Callable
    ) -> dict:
        """

        :param create_client_fn:
        :param token_data:
        :param key:
        :param get_data_fn:
        :return:
        """
        limiter = AsyncLimiter(100, 1)
        async with create_client_fn() as client:
            tasks = []
            for token in token_data.keys():
                if token_data[token].get(key) is None:
                    tasks.append(
                        asyncio.create_task(get_data_fn(client, token_data[token], limiter))
                    )
            [await f for f in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks))]

        cache.save_request_cache(cache_file_key, token_data)
        return token_data

    start_time = time.time()
    logging.info("\nPopulating account details...")
    asyncio.run(
        inner(
            sh.create_solana_client,
            all_token_data,
            "account",
            sh.get_account_info_from_solana_async,
        )
    )
    logging.info("--- %s seconds ---", (time.time() - start_time))

    start_time = time.time()
    logging.info("\nPopulating token metadata details...")
    result = asyncio.run(
        inner(hh.create_http_client, all_token_data, "arweave", get_arweave_metadata)
    )
    cache.save_request_cache(cache_file_key, all_token_data)
    logging.info("--- %s seconds ---", (time.time() - start_time))

    return result


async def get_arweave_metadata(
    http_client: aiohttp.ClientSession, data_dict: dict, limiter: AsyncLimiter
) -> dict:
    """

    :param http_client:
    :param data_dict:
    :param limiter:
    :return:
    """
    arweave_uri = data_dict["account"]["data"].get("uri")
    if data_dict.get("arweave") is None:
        data_dict["arweave"] = {}
    if arweave_uri:
        async with limiter:
            data_dict["arweave"] = await hh.async_http_request(http_client, arweave_uri)
    return data_dict


def holder_counts(all_token_data: dict) -> None:
    """

    :param all_token_data:
    :return:
    """
    counts = {}
    for token, data_dict in all_token_data.items():
        token_holders = data_dict["holders"]
        # Why is this empty sometimes? Because tokens get nuked, so there is no "holder" to fetch
        if token_holders.get("info") and token_holders["info"].get("owner"):
            holder_address = token_holders["info"]["owner"]
        else:
            holder_address = "UNKNOWN_ADDRESS"

        if not counts.get(holder_address):
            counts[holder_address] = 0
        counts[holder_address] += 1

    output.print_biggest_holders(len(all_token_data), counts)


def attribute_distribution(all_token_data: dict) -> None:
    """

    :param all_token_data:
    :return:
    """
    tokens_with_attributes_total = 0
    attribute_counts = {}

    for token, data_dict in all_token_data.items():
        arweave_data = data_dict["arweave"]
        attributes = arweave_data.get("attributes")
        if attributes:
            tokens_with_attributes_total += 1
            for attribute in attributes:
                trait_type = attribute["trait_type"]
                value = attribute["value"] if attribute["value"] is not None else ""
                if not attribute_counts.get(trait_type):
                    attribute_counts[trait_type] = {}
                if not attribute_counts[trait_type].get(value):
                    attribute_counts[trait_type][value] = 0
                attribute_counts[trait_type][value] += 1
        else:
            logging.info("Token %s has no attributes", token)

    output.print_trait_frequency(tokens_with_attributes_total, attribute_counts)


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option(
        "-t",
        dest="token_list",
        action="store_true",
        default=False,
        help="Get the token list for the give CM ID (requires passing --cmid)",
    )
    parser.add_option(
        "-o",
        dest="holder_counts",
        action="store_true",
        default=False,
        help="Get and print the overall holder counts",
    )
    parser.add_option(
        "-a",
        dest="attributes",
        action="store_true",
        default=False,
        help="Get and print the overall metadata attribute distribution",
    )
    parser.add_option(
        "-s",
        dest="snapshot",
        action="store_true",
        default=False,
        help="Get and output the snapshot file to the outfile name from -f",
    )
    parser.add_option(
        "-f",
        "--file",
        dest="outfile_name",
        default="snapshot.csv",
        help="Write snapshot to FILE (defaults to snapshot.csv)",
        metavar="FILE",
    )
    parser.add_option(
        "--cmid",
        dest="candymachine_id",
        help="Use CANDYMACHINE_ID to fetch tokens",
        metavar="CANDYMACHINE_ID",
    )
    parser.add_option(
        "--cmv2",
        dest="cm_v2",
        action="store_true",
        default=False,
        help="Use Candy Machine v2 method to fetch tokens from CM ID",
    )
    parser.add_option(
        "--bust-cache",
        dest="bust_cache",
        action="store_true",
        default=False,
        help="Clear out any existing cache data for this token file",
    )

    (options, args) = parser.parse_args()

    if not args:
        print("ERROR: Please pass in a token file name")
        exit(1)

    tokenfile_name = args[0]
    main(
        options.token_list,
        options.holder_counts,
        options.attributes,
        options.snapshot,
        options.candymachine_id,
        options.cm_v2,
        options.outfile_name,
        tokenfile_name,
        options.bust_cache,
    )

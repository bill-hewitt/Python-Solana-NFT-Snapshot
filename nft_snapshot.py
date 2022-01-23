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

from util import cache
from util import http_helpers as hh
from util import output
from util import solana_helpers as sh

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
    # filename="app.log",  # Uncomment this to have debug logs go to an output file
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
    """Central piece of the script: run the specified pieces of functionality specified from the options passed in.
    Will fetch needed data, if required (although fetched data is cached to disk so analysis can be run multiple
    times from those snapshots).

    :param get_token_list: Whether to fetch the token list for the given CM ID (requires candymachine_id)
    :param get_holder_counts: Whether to print the number of NFTs held per wallet
    :param get_attribute_distribution: Whether to print the rarity of all attributes found in the metadata
    :param get_holder_snapshot: Whether to output a CSV snapshot of information for each token
    :param candymachine_id: The Candy Machine ID to fetch tokens for
    :param cmv2: Whether the specified candymachine_id uses v2 or not
    :param outfile_name: Name to output the CSV snapshot to
    :param token_file_name: Name to output the token list to
    :param bust_cache: Whether to clear out the cache prior to running so you get fresh data
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
        cache.save_request_cache(cache_file_key, {})
    else:
        all_token_data = cache.load_request_cache(cache_file_key)

    for token in token_list:
        if token not in all_token_data:
            all_token_data[token] = {"token": token}

    if get_holder_counts:
        if not holders_populated:
            populate_holders_details_async(all_token_data, cache_file_key)
            holders_populated = True
        print(holder_counts(all_token_data))

    if get_attribute_distribution:
        if not accounts_populated:
            populate_account_details_async(all_token_data, cache_file_key)
            accounts_populated = True
        print(attribute_distribution(all_token_data))

    if get_holder_snapshot:
        if not holders_populated:
            populate_holders_details_async(all_token_data, cache_file_key)
            holders_populated = True
        if not accounts_populated:
            populate_account_details_async(all_token_data, cache_file_key)
            accounts_populated = True
        output.holder_snapshot(all_token_data, outfile_name)


def populate_holders_details_async(all_token_data: dict, cache_file_key: str) -> dict:
    """Fetch data about which wallets own the NFTs specified by the given token IDs. Fetched data is cached at the end.

    :param all_token_data: A dict of all the token data being operated upon
    :param cache_file_key: Name of the file to write to in the cache
    :return: The all_token_data dict with the "holders" key populated for each token
    """
    start_time = time.time()

    logging.info("\nPopulating holders details...")
    result = asyncio.run(
        fetch_token_data_from_network_async(
            sh.create_solana_client,
            all_token_data,
            "holders",
            sh.get_holder_info_from_solana_async,
        )
    )
    cache.save_request_cache(cache_file_key, result)
    logging.info("--- %s seconds ---", (time.time() - start_time))
    return result


def populate_account_details_async(all_token_data: dict, cache_file_key: str) -> dict:
    """Fetch metadata about the given token IDs, including attributes. Fetched data is cached at the end.

    :param all_token_data: A dict of all the token data being operated upon
    :param cache_file_key: Name of the file to write to in the cache
    :return: The all_token_data dict with the "account" and "arweave" keys populated for each token
    """
    start_time = time.time()
    logging.info("\nPopulating account details...")
    result = asyncio.run(
        fetch_token_data_from_network_async(
            sh.create_solana_client,
            all_token_data,
            "account",
            sh.get_account_info_from_solana_async,
        )
    )
    cache.save_request_cache(cache_file_key, result)
    logging.info("--- %s seconds ---", (time.time() - start_time))

    start_time = time.time()
    logging.info("\nPopulating token metadata details...")
    result = asyncio.run(
        fetch_token_data_from_network_async(
            hh.create_http_client, all_token_data, "arweave", get_arweave_metadata
        )
    )
    cache.save_request_cache(cache_file_key, result)
    logging.info("--- %s seconds ---", (time.time() - start_time))

    return result


async def fetch_token_data_from_network_async(
    create_client_fn: Callable, all_token_data: dict, key: str, get_data_fn: Callable
) -> dict:
    """Method to abstract the async client and task management for data fetching. Creates a task for each token

    :param create_client_fn: Function that creates and returns the async network client used to fetch data
    :param all_token_data: A dict of all the token data being operated upon
    :param key: The key in token_data to save the fetched data to
    :param get_data_fn: The function to call in order to fetch the data
    :return: The all_token_data dict with the requested key populated for each token
    """
    limiter = AsyncLimiter(100, 1)
    async with create_client_fn() as client:
        tasks = []
        for token in all_token_data.keys():
            if all_token_data[token].get(key) is None:
                tasks.append(
                    asyncio.create_task(get_data_fn(client, all_token_data[token], limiter))
                )
        [await f for f in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks))]
    return all_token_data


async def get_arweave_metadata(
    http_client: aiohttp.ClientSession, data_dict: dict, limiter: AsyncLimiter
) -> dict:
    """Fetches token metadata for a particular token (primarily used for traits) from Arweave if a URL is present.

    :param http_client: The aiohttp client used to make requests
    :param data_dict: The data sub-dict for the single desired token
    :param limiter: An AsyncLimiter used to prevent hitting request limits, and generally be a good citizen.
    :return: The data dict with the "arweave" key populated with response data (if applicable)
    """
    arweave_uri = data_dict["account"]["data"].get("uri")
    if data_dict.get("arweave") is None:
        data_dict["arweave"] = {}
    if arweave_uri:
        async with limiter:
            data_dict["arweave"] = await hh.async_http_request(http_client, arweave_uri)
    return data_dict


def holder_counts(all_token_data: dict) -> str:
    """Analyze the token data to determine how many NFTs are in each wallet, and print it out.

    :param all_token_data: The preassembled data dict for all tokens
    :return: A string containing the formatted output
    """
    counts = {}
    for token, data_dict in all_token_data.items():
        token_holders = data_dict["holders"]
        # Why is this empty sometimes? Because tokens get nuked, so there is no "holder" to fetch
        if token_holders.get("info") and token_holders["info"].get("owner"):
            holder_address = token_holders["info"]["owner"]
        else:
            holder_address = ""

        if not counts.get(holder_address):
            counts[holder_address] = 0
        counts[holder_address] += 1

    return output.format_biggest_holders(len(all_token_data), counts)


def attribute_distribution(all_token_data: dict) -> str:
    """Analyze the token data to determine the statistical rarity of the possible NFT traits, and print it out.

    :param all_token_data: The preassembled data dict for all tokens
    :return: A string containing the formatted output
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

    return output.format_trait_frequency(tokens_with_attributes_total, attribute_counts)


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
        args.candymachine_id,
        args.cm_v2,
        args.outfile_name,
        args.token_file,
        args.bust_cache,
    )

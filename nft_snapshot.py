"""

"""

import aiohttp
import asyncio
import base58
import base64
import json
import logging
import requests
import pandas as pd
import threading
import time
import tqdm
from aiolimiter import AsyncLimiter
from functools import wraps
from optparse import OptionParser
from pathlib import Path
from solana.rpc.api import Client
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import DataSliceOpts, MemcmpOpts
from solana.publickey import PublicKey
from time import sleep

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    filename='app.log')
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter('%(message)s'))
logging.getLogger('').addHandler(ch)

logger = logging.getLogger('nft_snapshot')

request_cache = None
CACHE_DIR = "cache"

SOLANA_RPC_ENDPOINT = "https://ssc-dao.genesysgo.net/"

# List of marketplaces, from https://github.com/theskeletoncrew/air-support/blob/main/1_record_holders/src/main.ts
MARKETPLACE_WALLETS = {
    "GUfCR9mK6azb9vcpsxgXyj7XRPAKJd4KMHTTVvtncGgp": "MagicEden",
    "3D49QorJyNaL4rcpiynbuS3pRH4Y7EXEM6v6ZGaqfFGK": "Solanart",
    "4pUQS4Jo2dsfWzt3VgHXy3H6RYnEDd11oWPiaM2rdAPw": "AlphaArt",
    "F4ghBzHFNgJxV4wEQDchU5i7n4XWWMBSaq7CuswGiVsr": "DigitalEyes",
}


def main(candymachine_id, cmv2, sig_file_name, outfile_name, token_file_name):
    get_token_list = False
    get_holder_counts = True
    get_attribute_distribution = True
    get_holder_snapshot = True

    cache_file_key = token_file_name
    token_list = []

    if get_token_list:
        if candymachine_id:
            token_list = get_token_list_from_candymachine_id(candymachine_id, cmv2)
        elif sig_file_name:
            token_list = get_token_list_from_signatures(sig_file_name)
        else:
            print("ERROR: You asked for the token list but didn't give signature list or CM ID to look up by")
            exit(1)

        with open(token_file_name, 'w') as token_list_file:
            token_list_file.write("\n".join(token_list))

    # If we're looking up based on an existing token list...
    if not token_list:
        with open(token_file_name) as token_list_file:
            token_list = token_list_file.read().splitlines()

    holders_populated = False
    accounts_populated = False

    # Initialize the cache once
    all_token_data = load_request_cache(cache_file_key)
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
        holder_snapshot(all_token_data, outfile_name)


def get_token_list_from_candymachine_id(cm_id, use_v2):
    """
    Adapted from https://github.com/solana-dev-adv/solana-cookbook/tree/master/code/nfts/nfts-mint-addresses

    :param cm_id:
    :param use_v2:
    :return:
    """
    start_time = time.time()

    logger.info(f'Fetching tokens from CM {cm_id} (v2? {use_v2})')

    client = Client(SOLANA_RPC_ENDPOINT, timeout=120)

    # Bunch of constants to get us looking in the right place...
    MAX_NAME_LENGTH = 32
    MAX_URI_LENGTH = 200
    MAX_SYMBOL_LENGTH = 10
    MAX_CREATOR_LEN = 32 + 1 + 1
    MAX_CREATOR_LIMIT = 5
    MAX_DATA_SIZE = 4 + MAX_NAME_LENGTH + 4 + MAX_SYMBOL_LENGTH + 4 + MAX_URI_LENGTH + 2 + 1 + 4 + MAX_CREATOR_LIMIT * MAX_CREATOR_LEN
    MAX_METADATA_LEN = 1 + 32 + 32 + MAX_DATA_SIZE + 1 + 1 + 9 + 172
    CREATOR_ARRAY_START = 1 + 32 + 32 + 4 + MAX_NAME_LENGTH + 4 + MAX_URI_LENGTH + 4 + MAX_SYMBOL_LENGTH + 2 + 1 + 4

    TOKEN_METADATA_PROGRAM = PublicKey('metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s')
    CANDY_MACHINE_V2_PROGRAM = PublicKey('cndy3Z4yapfJBmL3ShUp5exZKqR3z33thTzeNMm2gRZ')

    cm_pk = PublicKey(cm_id)
    if use_v2:
        cm_pk = cm_pk.find_program_address([b'candy_machine', bytes(cm_pk)], CANDY_MACHINE_V2_PROGRAM)[0]

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

    return [str(base58.b58encode(base64.b64decode(v['account']['data'][0])), 'UTF-8')
            for v in metadata_accounts["result"]]


def holder_counts(all_token_data):
    counts = {}
    for token, data_dict in all_token_data.items():
        token_holders = data_dict['holders']
        # Why is this empty sometimes? :shrug:
        holder_address = token_holders.get('data')[0].get('owner') or "UNKNOWN_ADDRESS"

        if not counts.get(holder_address):
            counts[holder_address] = 0
        counts[holder_address] += 1

    print_biggest_holders(len(all_token_data), counts)


def attribute_distribution(all_token_data):
    tokens_with_attributes_total = 0
    attribute_counts = {}

    for token, data_dict in all_token_data.items():
        account_data = data_dict['account']
        attributes = account_data.get('metadata').get('data').get('attributes')
        if attributes:
            tokens_with_attributes_total += 1
            for attribute in attributes:
                trait_type = attribute['trait_type']
                value = attribute['value'] if attribute['value'] is not None else ""
                if not attribute_counts.get(trait_type):
                    attribute_counts[trait_type] = {}
                if not attribute_counts[trait_type].get(value):
                    attribute_counts[trait_type][value] = 0
                attribute_counts[trait_type][value] += 1
        else:
            logging.warning("Token %s has no attributes", token)

    print_trait_frequency(tokens_with_attributes_total, attribute_counts)


def holder_snapshot(all_token_data, outfile_name):
    token_csv_data = []

    for token, data_dict in all_token_data.items():
        token_holders = data_dict['holders']
        account_data = data_dict['account']

        holder_address = token_holders.get('data')[0].get('owner')
        token_name = account_data.get('tokenInfo').get('name')
        token_csv_data.append([
            token_name[token_name.find('#') + 1::],
            token_name,
            token,
            holder_address,
            token_holders.get('data')[-1].get('owner'),  # mint address
            token_holders.get('total')  # total holders of this token
        ])

    dataset = pd.DataFrame(token_csv_data, columns=['Number', 'TokenName', 'Token', 'HolderAddress', 'MintAddress', 'TotalHolders'])
    dataset.to_csv(outfile_name)


def populate_holders_details_async(all_token_data, cache_file_key):
    start_time = time.time()

    logging.info("\nPopulating holders details...")
    result = asyncio.run(populate_data_dict_async(
        all_token_data,
        "holders",
        lambda token: f'token/holders?tokenAddress={token}&offset=0&limit=20',
        cache_file_key,
    ))
    logging.info("--- %s seconds ---", (time.time() - start_time))
    return result


def get_holder_info_from_solana(token):
    # TODO: Use this! Likely significant speedup
    async with AsyncClient(SOLANA_RPC_ENDPOINT) as client:
        la = await client.get_token_largest_accounts(PublicKey(token))
        lai = await client.get_account_info(la['result']['value'][0]['address'], encoding="jsonParsed")
        result = lai["result"]["value"]['data']['parsed']['info']['owner']


def populate_account_details_async(all_token_data, cache_file_key):
    start_time = time.time()

    logging.info("\nPopulating account details...")
    result = asyncio.run(populate_data_dict_async(
        all_token_data,
        "account",
        lambda token: f'account/{token}',
        cache_file_key,
    ))
    logging.info("--- %s seconds ---", (time.time() - start_time))
    return result


async def populate_data_dict_async(all_token_data, key, endpoint_fn, cache_file_key):
    conn = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=conn) as session:
        limiter = AsyncLimiter(145, 30)

        tasks = []
        for token in all_token_data.keys():
            if all_token_data[token].get(key) is None:
                tasks.append(asyncio.create_task(
                    get_token_data(session, limiter, all_token_data[token], key, endpoint_fn(token))
                ))
        [await f for f in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks))]

    save_request_cache(cache_file_key, all_token_data)
    return all_token_data


async def get_token_data(session, limiter, data_dict, key, endpoint):
    async with limiter:
        site = 'https://public-api.solscan.io/'
        data_dict[key] = await async_solscan_request(session, f'{site}{endpoint}')
        return data_dict


async def async_solscan_request(session, url):
    async with session.get(url) as resp:
        if resp.status != 200:
            # If we failed for some reason, try again
            logging.debug(f'Got status code %s for url %s, sleeping and retrying', resp.status, url)
            sleep(3)
            return await async_solscan_request(session, url)
        logging.debug('Successful response for url %s', url)
        body = await resp.json()
        return body


# #### HERE BEGINS THE LAND OF JANK


def get_token_list_from_signatures(sig_file_name):
    signature_list = open(sig_file_name)  # load list
    signature_list = signature_list.read().splitlines()

    token_list = []
    transaction_data = None
    for signature in tqdm.tqdm(signature_list):  # check all transactions/signatures
        try:
            logger.debug('Signature: %s', signature)
            transaction_data = make_solscan_request('transaction/' + signature)
            token_address = transaction_data.get('tokenBalances')[0].get('token').get('tokenAddress')
            logger.debug('Token: %s', token_address)

            if token_address not in token_list:  # if new token
                token_list.append(token_address)  # add to list

        except Exception as e:
            if transaction_data and not transaction_data.get('tokenBalances'):
                logger.warning('No Token in Transaction: %s', transaction_data)
            else:
                logger.warning(e)
    return token_list


def make_solscan_request(endpoint):
    # sleep(0.7)  #prevent to many requests: 30 seconds/50 requests -> 0.6 -> 0.05 safety
    url = 'https://public-api.solscan.io/' + endpoint
    response = requests.get(url)
    # TODO: properly handle request errors (https://public-api.solscan.io/docs/#/Account/get_account__account_)
    if 429 == response.status_code:  # Too Many Request. Try again after 1 minute + 20 sec
        while 429 == response.status_code:
            logger.debug('Too many requests, sleeping then retrying')
            sleep(5)
            response = requests.get(url)
    return response.json()


# #### THUS ENDS THE LAND OF JANK


def load_request_cache(cache_file_key):
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


def save_request_cache(cache_file_key, cache_data):
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


def print_biggest_holders(tokens_total, counts):
    print("\n")
    print("Total tokens: {}".format(tokens_total))

    # Print holder list in descending order
    counts = sort_dict_by_values(counts, reverse=True)
    print("\nBiggest holders:\n----------")
    for holder, count in counts.items():
        marketplace_suffix = " (" + MARKETPLACE_WALLETS[holder] + ")" if holder in MARKETPLACE_WALLETS else ""
        print("{}: {}{}".format(holder, count, marketplace_suffix))


def print_trait_frequency(tokens_with_metadata_total, attribute_counts):
    # Print out trait frequency
    print(f'\n{tokens_with_metadata_total} tokens with metadata')
    print("\nAttributes:\n----------")
    for trait_type, values in attribute_counts.items():
        print("\n" + trait_type)
        for value, count in sort_dict_by_values(values).items():
            frequency_str = " ({}/{}, {})".format(count, tokens_with_metadata_total, count * 1.0/tokens_with_metadata_total)
            print(value + ": " + str(count) + frequency_str)


def sort_dict_by_values(dictionary, reverse=False):
    """Sort a dictionary by its values (default ascending)"""
    holder_list = sorted(((v, k) for (k, v) in dictionary.items()), reverse=reverse)
    return dict([(k, v) for (v, k) in holder_list])


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("--sigfile", dest="sigfile_name",
                      help="read in signatures from FILE", metavar="FILE")
    parser.add_option("-f", "--file", dest="outfile_name", default="snapshot.csv",
                      help="write report to FILE", metavar="FILE")
    parser.add_option("--cmid", dest="candymachine_id",
                      help="Use Candy Machine ID to fetch tokens")
    parser.add_option("--cmv2", dest="cm_v2", action="store_true", default=False,
                      help="Use Candy Machine v2 method to fetch tokens from CM ID")

    # TODO: implement these...
    parser.add_option("-q", "--quiet",
                  action="store_true", dest="verbose", default=False,
                  help="don't print status messages to stdout")

    (options, args) = parser.parse_args()
    # 4wTTi885HkQ6awqRGQkHAdXXzE46DyqLNXtfo1uz5ub3 = Mindfolk
    # CApZmLZAwjTm59pc6rKJ85sux4wCJsLS7RMV1pUkMeVK = My Trash
    # C3UphYJYqTab4Yrr64V8wSAxeM7Wr9NUauyYGn7aomTJ = MK

    if not args:
        print("ERROR: Please pass in a token file name")
        exit(1)

    tokenfile_name = args[0]
    main(
        options.candymachine_id,
        options.cm_v2,
        options.sigfile_name,
        options.outfile_name,
        tokenfile_name
    )
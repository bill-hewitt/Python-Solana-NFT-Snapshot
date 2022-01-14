"""

"""

import aiohttp
import asyncio
import json
import logging
import requests
import pandas as pd
import progressbar
import time
import tqdm
import tqdm.asyncio
from optparse import OptionParser
from pathlib import Path
from time import sleep


# Find the token list via https://magiceden.io/mintlist-tool by entering in CM ID or first/verified creator ID from
# solscan

request_cache = None
CACHE_DIR = "cache"

# List of marketplaces, from https://github.com/theskeletoncrew/air-support/blob/main/1_record_holders/src/main.ts
MARKETPLACES = {
    "GUfCR9mK6azb9vcpsxgXyj7XRPAKJd4KMHTTVvtncGgp": "MagicEden",
    "3D49QorJyNaL4rcpiynbuS3pRH4Y7EXEM6v6ZGaqfFGK": "Solanart",
    "4pUQS4Jo2dsfWzt3VgHXy3H6RYnEDd11oWPiaM2rdAPw": "AlphaArt",
    "F4ghBzHFNgJxV4wEQDchU5i7n4XWWMBSaq7CuswGiVsr": "DigitalEyes",
}


def main(token_file_name, sig_file_name, outfile_name):

    cache_file_key = token_file_name
    token_list = []

    # If we're looking up based on the signature list...
    if sig_file_name:
        signature_list = open(sig_file_name)  # load list
        signature_list = signature_list.read().splitlines()

        i = 1
        with progressbar.ProgressBar(max_value=len(signature_list), redirect_stdout=True) as bar:  # create bar
            for signature in signature_list:  # check all transactions/signatures
                try:
                    print('\rSignature:\t' + signature)
                    transaction_data = cached_make_solscan_request('transaction/' + signature, cache_file_key)
                    token_address = transaction_data.get('tokenBalances')[0].get('token').get('tokenAddress')
                    print('Token:\t\t' + token_address + '\n')

                    if token_address not in token_list:  # if new token
                        token_list.append(token_address)  # add to list

                except Exception as e:
                    if not transaction_data.get('tokenBalances'):  # not a transaction with token
                        print("no Token in Transaction: " + transaction_data)
                    else:
                        print(e)
                bar.update(i)
                i += 1

        token_list_file = open(token_file_name, 'w')
        file_content = "\n".join(token_list)
        token_list_file.write(file_content)
        token_list_file.close()

    # If we're looking up based on an existing token list...
    if not token_list:
        token_list_file = open(token_file_name)
        token_list = token_list_file.read().splitlines()

    holder_counts = {}

    tokens_with_metadata_total = 0
    attribute_counts = {}

    all_token_data = {}
    token_data = []
    # -----
    all_token_data = get_token_details_async(token_list, cache_file_key)
    for token, data_dict in all_token_data.items():
        token_holders = data_dict['holders']
        account_data = data_dict['account']

        # Assemble CSV row
        holder_address = token_holders.get('data')[0].get('owner')
        token_name = account_data.get('tokenInfo').get('name')
        token_data.append([
            token_name[token_name.find('#') + 1::],
            token_name,
            token,
            holder_address,
            token_holders.get('data')[-1].get('owner'),  # mint address
            token_holders.get('total')  # total holders of this token
        ])

        # Assemble holder count
        if not holder_counts.get(holder_address):
            holder_counts[holder_address] = 0
        holder_counts[holder_address] += 1

        # Assemble attribute distribution
        attributes = account_data.get('metadata').get('data').get('attributes')
        if attributes:
            tokens_with_metadata_total += 1
            for attribute in attributes:
                trait_type = attribute['trait_type']
                value = attribute['value'] if attribute['value'] is not None else ""
                if not attribute_counts.get(trait_type):
                    attribute_counts[trait_type] = {}
                if not attribute_counts[trait_type].get(value):
                    attribute_counts[trait_type][value] = 0
                attribute_counts[trait_type][value] += 1
        else:
            print("Token {} has no metadata".format(token))

    # -----
    # i = 1
    # with progressbar.ProgressBar(max_value=len(token_list), redirect_stdout=True) as bar2:  # create bar
    #     for token in token_list:
    #         try:
    #             # my python needs spaces to override the message of the bar-> bar always on bottom of terminal
    #             print('\rToken:\t' + token + '                             ')
    #
    #             # Fetch data
    #             token_holders = cached_make_solscan_request('token/holders?tokenAddress=' + token + '&offset=0&limit=10', cache_file_key)
    #             account_data = cached_make_solscan_request('account/' + token, cache_file_key)
    #
    #             # Assemble CSV row
    #             holder_address = token_holders.get('data')[0].get('owner')
    #             token_name = account_data.get('tokenInfo').get('name')
    #             token_data.append([
    #                 token_name[token_name.find('#') + 1::],
    #                 token_name,
    #                 token,
    #                 holder_address,
    #                 token_holders.get('data')[-1].get('owner'),  # mint address
    #                 token_holders.get('total')  # total holders of this token
    #             ])
    #
    #             # Assemble holder count
    #             if not holder_counts.get(holder_address):
    #                 holder_counts[holder_address] = 0
    #             holder_counts[holder_address] += 1
    #
    #             # Assemble attribute distribution
    #             attributes = account_data.get('metadata').get('data').get('attributes')
    #             if attributes:
    #                 tokens_with_metadata_total += 1
    #                 for attribute in attributes:
    #                     trait_type = attribute['trait_type']
    #                     value = attribute['value'] if attribute['value'] is not None else ""
    #                     if not attribute_counts.get(trait_type):
    #                         attribute_counts[trait_type] = {}
    #                     if not attribute_counts[trait_type].get(value):
    #                         attribute_counts[trait_type][value] = 0
    #                     attribute_counts[trait_type][value] += 1
    #             else:
    #                 print("Token {} has no metadata".format(token))
    #         except Exception as e:
    #             print(e)
    #         bar2.update(i)
    #
    #         # Dump to cache every so often so we don't lose all our work
    #         if i % 50 == 0:
    #             save_request_cache(cache_file_key)
    #         i += 1
    #
    # save_request_cache(cache_file_key)

    dataset = pd.DataFrame(token_data, columns=['Number', 'TokenName', 'Token', 'HolderAddress', 'MintAddress', 'TotalHolders'])
    dataset.to_csv(outfile_name)
    print_biggest_holders(len(all_token_data), holder_counts)
    print_trait_frequency(tokens_with_metadata_total, attribute_counts)


def get_token_details_async(token_list, cache_file_key):
    start_time = time.time()

    # Initialize the cache once
    global request_cache
    request_cache = load_request_cache(cache_file_key)

    async def solscan_request(session, url):
        async with session.get(url) as resp:
            if resp.status != 200:
                # If we failed for some reason, try again
                print(f'Got status code {resp.status} for url {url}, sleeping and retrying')
                sleep(3)
                return await solscan_request(session, url)
            print(f'Successful response for url {url}')
            body = await resp.json()
            return body

    async def get_token_data(session, token):
        # Check cache for data...if not there, make requests
        if request_cache.get(token) is None:
            # print(f'Token {token} not in cache, fetching')

            site = 'https://public-api.solscan.io/'
            holders_endpoint = f'token/holders?tokenAddress={token}&offset=0&limit=20'
            account_endpoint = f'account/{token}'
            holders = await solscan_request(session, f'{site}{holders_endpoint}')
            account = await solscan_request(session, f'{site}{account_endpoint}')
            request_cache[token] = {
                'token': token,
                'holders': holders,
                'account': account
            }
        # else:
        #     print(f'Token {token} read from cache')

        # Save data to the request cache on a regular basis
        if len(request_cache) % 100 == 0:
            save_request_cache(cache_file_key)

        return request_cache[token]

    async def inner():
        conn = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=conn) as session:

            all_token_responses = [v for v in request_cache.values()]
            tasks = []
            for token in token_list:
                if token not in request_cache:
                    tasks.append(asyncio.ensure_future(get_token_data(session, token)))
                    # Account for API limits: 150 requests/ 30 seconds, 100k requests / day
                    await asyncio.sleep(0.6)

            all_token_responses.extend([
                await f for f in tqdm.tqdm(asyncio.as_completed(tasks), total=len(tasks))
            ])
            save_request_cache(cache_file_key)

            # Now that we have all the data, reformat to something more convenient
            all_token_data = {}
            for response in all_token_responses:
                all_token_data[response['token']] = {
                    "holders": response['holders'],
                    "account": response['account']
                }
            return all_token_data

    result = asyncio.run(inner())
    print("--- %s seconds ---" % (time.time() - start_time))
    return result


# def cached_make_solscan_request(endpoint, cache_file_key):
#     global request_cache
#
#     if request_cache is None:
#         request_cache = load_request_cache(cache_file_key)
#
#     if request_cache.get(endpoint) is None:
#         request_cache[endpoint] = make_solscan_request(endpoint)
#
#     return request_cache[endpoint]
#
#
# def make_solscan_request(endpoint):
#     # sleep(0.7)  #prevent to many requests: 30 seconds/50 requests -> 0.6 -> 0.05 safety
#     url = 'https://public-api.solscan.io/' + endpoint
#     response = requests.get(url)
#     # TODO: properly handle request errors (https://public-api.solscan.io/docs/#/Account/get_account__account_)
#     if 429 == response.status_code:  # Too Many Request. Try again after 1 minute + 20 sec
#         while 429 == response.status_code:
#             print('Too many requests, waiting 80 sec')
#             sleep(80)
#             response = requests.get(url)
#     return response.json()


def load_request_cache(cache_file_key):
    try:
        filename = "{}_cache.json".format(cache_file_key)
        path = Path(CACHE_DIR) / filename
        with path.open() as file:
            cache_data = json.load(file)
            print("Loaded cache data from {}".format(filename))
            return cache_data
    except Exception as e:
        print("Unable to load cache file {}: {}".format(path, e))
        return {}


def save_request_cache(cache_file_key):
    global request_cache

    try:
        filename = "{}_cache.json".format(cache_file_key)
        path = Path(CACHE_DIR)
        path.mkdir(exist_ok=True)
        path = path / filename
        with path.open("w") as file:
            json.dump(request_cache, file)
            print("Wrote cache data to {}".format(path))
    except Exception as e:
        print("Unable to write cache file {}: {}".format(path, e))


def print_biggest_holders(tokens_total, holder_counts):
    print("\n")
    print("Total tokens: {}".format(tokens_total))

    # Print holder list in descending order
    holder_counts = sort_dict_by_values(holder_counts, reverse=True)
    print("\nBiggest holders:\n----------")
    for holder, count in holder_counts.items():
        marketplace_suffix = " (" + MARKETPLACES[holder] + ")" if holder in MARKETPLACES else ""
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

    # TODO: implement these...
    parser.add_option("-q", "--quiet",
                  action="store_true", dest="verbose", default=False,
                  help="don't print status messages to stdout")

    (options, args) = parser.parse_args()

    # Default a value for token_file
    token_file = 'tokenlist.txt'
    if args:
        token_file = args[0]
    main(token_file, options.sigfile_name, options.outfile_name)
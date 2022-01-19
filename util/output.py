import pandas as pd


# List of marketplaces, from https://github.com/theskeletoncrew/air-support/blob/main/1_record_holders/src/main.ts
MARKETPLACE_WALLETS = {
    "GUfCR9mK6azb9vcpsxgXyj7XRPAKJd4KMHTTVvtncGgp": "MagicEden",
    "3D49QorJyNaL4rcpiynbuS3pRH4Y7EXEM6v6ZGaqfFGK": "Solanart",
    "4pUQS4Jo2dsfWzt3VgHXy3H6RYnEDd11oWPiaM2rdAPw": "AlphaArt",
    "F4ghBzHFNgJxV4wEQDchU5i7n4XWWMBSaq7CuswGiVsr": "DigitalEyes",
}


def print_biggest_holders(tokens_total: int, counts: dict) -> None:
    """Print all the NFT holder wallets, sorted with the largest holders at the top

    :param tokens_total: The total number of tokens in the collection
    :param counts: A dict containing the counts of tokens held in each wallet (wallet_id: count)
    """
    print("\n")
    print("Total tokens: {}".format(tokens_total))

    # Print holder list in descending order
    counts = sort_dict_by_values(counts, reverse=True)
    print("\nBiggest holders:\n----------")
    for holder, count in counts.items():
        marketplace_suffix = (
            " (" + MARKETPLACE_WALLETS[holder] + ")" if holder in MARKETPLACE_WALLETS else ""
        )
        print("{}: {}{}".format(holder, count, marketplace_suffix))


def print_trait_frequency(tokens_with_metadata_total: int, attribute_counts: dict) -> None:
    """Print a list of all the NFT traits in the collection and their statistical frequencies.

    :param tokens_with_metadata_total: The total number of tokens in the collection with trait data
    :param attribute_counts: A dict containing all the traits present in the collection, their possible values, and the
        number of occurrences of those values
    """
    print(f"\n{tokens_with_metadata_total} tokens with metadata")
    print("\nAttributes:\n----------")
    for trait_type, values in attribute_counts.items():
        print("\n" + trait_type)
        for value, count in sort_dict_by_values(values).items():
            frequency_str = " ({}/{}, {})".format(
                count, tokens_with_metadata_total, count * 1.0 / tokens_with_metadata_total
            )
            print(f"{value}: {count}{frequency_str}")


def sort_dict_by_values(dictionary: dict, reverse: bool = False) -> dict:
    """Sort a dictionary by its values (default ascending)

    :param dictionary: dict to sort
    :param reverse: Whether to reverse sort order to descending
    :return: The sorted dictionary
    """
    flipped_sorted_dict = sorted(((v, k) for (k, v) in dictionary.items()), reverse=reverse)
    return dict([(k, v) for (v, k) in flipped_sorted_dict])


def holder_snapshot(all_token_data: dict, outfile_name: str) -> None:
    """Output a CSV file containing data about each token in the collection.

    :param all_token_data: A dict of all the token data in the collection
    :param outfile_name: The name of the file to output the CSV to
    """
    token_csv_data = []

    for token, data_dict in all_token_data.items():
        token_holders = data_dict["holders"]
        account_data = data_dict["account"]

        if token_holders.get("info"):
            holder_address = token_holders["info"].get("owner")
            amount = token_holders["info"].get("tokenAmount").get("amount")
        else:
            holder_address = "UNKNOWN_ADDRESS"
            amount = 0
        token_name = account_data.get("data").get("name")
        token_csv_data.append(
            [
                token_name[token_name.find("#") + 1 : :],
                token_name,
                token,
                holder_address,
                amount,
            ]
        )

    dataset = pd.DataFrame(
        token_csv_data, columns=["Number", "TokenName", "Token", "HolderAddress", "TotalHeld"]
    )
    dataset.to_csv(outfile_name)

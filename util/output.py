import pandas

from util.token import get_attribute_counts
from util.token import get_attribute_rarities
from util.token import set_token_rarities_and_ranks
from util.token import Token


# List of marketplaces, from https://github.com/theskeletoncrew/air-support/blob/main/1_record_holders/src/main.ts
MARKETPLACE_WALLETS = {
    "GUfCR9mK6azb9vcpsxgXyj7XRPAKJd4KMHTTVvtncGgp": "MagicEden",
    "3D49QorJyNaL4rcpiynbuS3pRH4Y7EXEM6v6ZGaqfFGK": "Solanart",
    "4pUQS4Jo2dsfWzt3VgHXy3H6RYnEDd11oWPiaM2rdAPw": "AlphaArt",
    "F4ghBzHFNgJxV4wEQDchU5i7n4XWWMBSaq7CuswGiVsr": "DigitalEyes",
}


def format_biggest_holders(tokens_total: int, counts: dict) -> str:
    """Format all the NFT holder wallets, sorted with the largest holders at the top

    :param tokens_total: The total number of tokens in the collection
    :param counts: A dict containing the counts of tokens held in each wallet (wallet_id: count)
    :return: A str containing the formatted output
    """
    result_str = "\n"
    result_str += "Total tokens: {}\n".format(tokens_total)
    result_str += "Total Holder Wallets: {}\n".format(len(counts))

    # format holder list in descending order
    counts = sort_dict_by_values(counts, reverse=True)
    result_str += "\nBiggest holders:\n----------\n"
    for holder, count in counts.items():
        marketplace_suffix = (
            " (" + MARKETPLACE_WALLETS[holder] + ")" if holder in MARKETPLACE_WALLETS else ""
        )
        result_str += "{}: {}{}\n".format(holder, count, marketplace_suffix)
    return result_str


def format_trait_frequency(tokens_with_metadata_total: int, attribute_counts: dict) -> str:
    """Format a list of all the NFT traits in the collection and their statistical frequencies.

    :param tokens_with_metadata_total: The total number of tokens in the collection with trait data
    :param attribute_counts: A dict containing all the traits present in the collection, their possible values, and the
        number of occurrences of those values
    :return: A str containing the formatted output
    """
    result_str = f"\n{tokens_with_metadata_total} tokens with metadata\n"
    result_str += "\nAttributes:\n----------\n"
    for trait_type, values in attribute_counts.items():
        result_str += f"\n{trait_type}\n"
        for value, count in sort_dict_by_values(values).items():
            frequency_str = " ({}/{}, {:.6f})".format(
                count, tokens_with_metadata_total, count * 1.0 / tokens_with_metadata_total
            )
            result_str += f"{value}: {count}{frequency_str}\n"
    return result_str


def sort_dict_by_values(dictionary: dict, reverse: bool = False) -> dict:
    """Sort a dictionary by its values (default ascending)

    :param dictionary: dict to sort
    :param reverse: Whether to reverse sort order to descending
    :return: The sorted dictionary
    """
    flipped_sorted_dict = sorted(((v, k) for (k, v) in dictionary.items()), reverse=reverse)
    return dict([(k, v) for (v, k) in flipped_sorted_dict])


def holder_snapshot(all_tokens: dict, outfile_name: str) -> None:
    """Output a CSV file containing data about each token in the collection.

    :param all_tokens: A dict of all the token data in the collection
    :param outfile_name: The name of the file to output the CSV to
    """
    token_csv_data = []

    trait_map = get_trait_map(all_tokens)
    tokens_with_attributes_total, attribute_counts = get_attribute_counts(trait_map, all_tokens)
    attribute_rarities = get_attribute_rarities(tokens_with_attributes_total, attribute_counts)

    set_token_rarities_and_ranks(trait_map, attribute_rarities, all_tokens)

    for token in all_tokens.values():
        # Create a list big enough for all the collection's traits, then fill in the ones this NFT has
        token_traits = [None] * len(trait_map)
        for trait_name, trait_value in token.traits.items():
            token_traits[trait_map[trait_name]] = trait_value
        token_csv_data.append(
            [
                token.id,
                token.name,
                token.token,
                token.holder_address if token.holder_address else "UNKNOWN_ADDRESS",
                token.amount,
                token.image,
                token.rank,
                "{:.20f}%".format(token.rarity * 100),
            ]
            + token_traits
        )

    dataset = pandas.DataFrame(
        token_csv_data,
        columns=[
            "Number",
            "TokenName",
            "Token",
            "HolderAddress",
            "TotalHeld",
            "Image",
            "Rank",
            "Rarity",
        ]
        + list(trait_map.keys()),
    )
    dataset.to_csv(outfile_name)


def get_trait_map(all_tokens: dict) -> dict:
    """Get a map of all the traits present in the collection mapped to their order of appearance.

    :param all_tokens: A dict of all the token data in the collection
    :return: dict of all the trait names mapped to ints
    """
    trait_map = {}
    traits_seen = 0
    for token in all_tokens.values():
        for trait_name in token.traits:
            if trait_name not in trait_map:
                trait_map[trait_name] = traits_seen
                traits_seen += 1
    return trait_map


def format_token_rarity(token_id: str, all_tokens: dict[str, Token]) -> str:
    """Format the statistical rarity of a token overall, and for each trait

    :param token_id: The token to analyse statistical rarity for
    :param all_tokens: A dict of all the token data in the collection
    :return: Nicely-formatted str containing the requested rarity info
    """
    token = all_tokens[token_id]

    trait_map = get_trait_map(all_tokens)
    tokens_with_attributes_total, attribute_counts = get_attribute_counts(trait_map, all_tokens)
    attribute_rarities = get_attribute_rarities(tokens_with_attributes_total, attribute_counts)

    if not token.rarity or not token.rank:
        set_token_rarities_and_ranks(trait_map, attribute_rarities, all_tokens)

    output = f"\nToken {token_id}\n----------\n"
    output += f"Rank: {token.rank}\nRarity: {token.rarity:.20f}\n\n"
    output += "Traits\n-----\n"
    for trait_name in trait_map:
        value = token.traits[trait_name] if trait_name in token.traits else ""
        output += "{name}: {value} ({count}/{total}, {pct:.6f})\n".format(
            name=trait_name,
            value=value,
            count=attribute_counts[trait_name][value],
            total=tokens_with_attributes_total,
            pct=attribute_rarities[trait_name][value],
        )
    return output

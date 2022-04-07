import logging

logger = logging.getLogger("nft_snapshot.util.token")


class Token:
    def __init__(
        self,
        token,
        name=None,
        id=None,
        token_account=None,
        holder_address=None,
        amount=None,
        image=None,
        traits=None,
        data_uri=None,
    ):
        self.token = token

        self.name = name
        self.id = id
        self.token_account = token_account
        self.holder_address = holder_address
        self.amount = amount
        self.image = image
        self.traits = traits if traits is not None else {}
        self.data_uri = data_uri

        self.rarity = None
        self.rank = None


def get_attribute_counts(trait_map: dict, all_tokens: dict[str, Token]) -> (int, dict):
    """Get a total count of tokens with traits present, and also the counts of each trait value.

    :param trait_map: dict produced by get_trait_map()
    :param all_tokens: The preassembled data dict for all tokens
    :return: int: count of tokens with attributes; dict: counts of all values for all attributes
    """
    tokens_with_attributes_total = 0
    attribute_counts = {}

    for token in all_tokens.values():
        if token.traits:
            tokens_with_attributes_total += 1
            for trait_type in trait_map:
                value = token.traits[trait_type] if trait_type in token.traits else ""
                if not attribute_counts.get(trait_type):
                    attribute_counts[trait_type] = {}
                if not attribute_counts[trait_type].get(value):
                    attribute_counts[trait_type][value] = 0
                attribute_counts[trait_type][value] += 1
        else:
            logging.info("Token %s has no attributes", token.token)

    return tokens_with_attributes_total, attribute_counts


def get_attribute_rarities(tokens_with_attributes_total: int, attribute_counts: dict) -> dict:
    """Get the relative rarities of all trait values for each in the collection

    :param tokens_with_attributes_total: Total number of tokens in the collection with traits set
    :param attribute_counts: The attribute count dict produced by get_attribute_counts()
    :return: dict mapping trait names to dicts mapping trait values to rarity
    """
    attribute_rarities = {}
    for trait_type, values in attribute_counts.items():
        attribute_rarities[trait_type] = {}
        total_count = 0
        for value, count in values.items():
            attribute_rarities[trait_type][value] = count * 1.0 / tokens_with_attributes_total
            total_count += count
        attribute_rarities[trait_type][None] = (
            (tokens_with_attributes_total - total_count) * 1.0 / tokens_with_attributes_total
        )
    return attribute_rarities


def set_token_rarities_and_ranks(
    trait_map: dict, attribute_rarities: dict, all_tokens: dict[str, Token]
):
    """Set the tokens' overall rarity and rank within the collection

    :param trait_map: dict produced by get_trait_map()
    :param attribute_rarities: dict produced by get_attribute_rarities()
    :param all_tokens: The preassembled data dict for all tokens
    """
    rarity_ranks = {}
    for t in all_tokens.values():
        if t.traits:
            token_rarity = 1
            for trait in trait_map:
                value = t.traits[trait] if trait in t.traits else ""
                token_rarity *= attribute_rarities[trait][value]
            t.rarity = token_rarity
            if rarity_ranks.get(token_rarity) is None:
                rarity_ranks[token_rarity] = []
            rarity_ranks[token_rarity].append(t)

    rarity_ranks = {k: rarity_ranks[k] for k in sorted(rarity_ranks)}
    rank = 1
    for rarity, rank_list in rarity_ranks.items():
        for t in rank_list:
            t.rank = rank
            rank += 1

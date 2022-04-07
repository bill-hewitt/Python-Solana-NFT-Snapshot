from util import token


class TestToken:
    def test_get_attribute_counts(self):
        input_dict = {
            "token_1": token.Token(token="token_1", traits={"hair": "white", "eyes": "blue"}),
            "token_2": token.Token(token="token_2", traits={"hair": "white", "eyes": ""}),
            "token_3": token.Token(token="token_3", traits={"jacket": "yes"}),
        }
        trait_map = {"hair": 0, "eyes": 1, "jacket": 2}
        expected = (
            3,
            {"hair": {"white": 2, "": 1}, "eyes": {"blue": 1, "": 2}, "jacket": {"": 2, "yes": 1}},
        )
        result = token.get_attribute_counts(trait_map, input_dict)
        assert result == expected

    def test_get_attribute_rarities(self):
        attr_counts = {
            "hair": {"white": 2, "": 1},
            "eyes": {"blue": 1, "": 2},
            "jacket": {"yes": 1, "": 2},
        }
        expected = {
            "hair": {"white": 0.6666666666666666, "": 0.3333333333333333, None: 0.0},
            "eyes": {"blue": 0.3333333333333333, "": 0.6666666666666666, None: 0.0},
            "jacket": {"": 0.6666666666666666, "yes": 0.3333333333333333, None: 0.0},
        }
        result = token.get_attribute_rarities(3, attr_counts)
        assert result == expected

    def test_set_token_rarities_and_ranks(self):
        input_dict = {
            "token_1": token.Token(token="token_1", traits={"hair": "white", "eyes": "blue"}),
            "token_2": token.Token(token="token_2", traits={"hair": "white", "eyes": ""}),
            "token_3": token.Token(token="token_3", traits={"jacket": "yes"}),
        }
        trait_map = {"hair": 0, "eyes": 1, "jacket": 2}
        rarities = {
            "hair": {"white": 0.6666666666666666, "": 0.3333333333333333, None: 0.0},
            "eyes": {"blue": 0.3333333333333333, "": 0.6666666666666666, None: 0.0},
            "jacket": {"": 0.6666666666666666, "yes": 0.3333333333333333, None: 0.0},
        }
        token.set_token_rarities_and_ranks(trait_map, rarities, input_dict)
        assert input_dict["token_1"].rarity == 0.14814814814814814
        assert input_dict["token_1"].rank == 2
        assert input_dict["token_2"].rarity == 0.2962962962962963
        assert input_dict["token_2"].rank == 3
        assert input_dict["token_3"].rarity == 0.07407407407407407
        assert input_dict["token_3"].rank == 1

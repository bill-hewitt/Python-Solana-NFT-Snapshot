import mock
import pytest
from aiolimiter import AsyncLimiter

import nft_snapshot
from util import http_helpers as hh
from util import solana_helpers as sh


class TestNftSnapshot:
    def test_main_token_list(self, mocker):
        sh_mock = mocker.patch.object(nft_snapshot, "sh")
        sh_mock.get_token_list_from_candymachine_id.return_value = ["12345"]

        with mock.patch("builtins.open", mock.mock_open()) as file_mock:
            nft_snapshot.main(
                True, False, False, False, "test_cm", False, "outfile", "tokenfile", False
            )
            file_mock.assert_called_once_with("tokenfile", "w")
        sh_mock.get_token_list_from_candymachine_id.assert_called_once_with("test_cm", False)

    def test_main_holder_list(self, mocker):
        pop_holders_mock = mocker.patch.object(nft_snapshot, "populate_holders_details_async")
        holders_mock = mocker.patch.object(nft_snapshot, "holder_counts")
        expected_tokens = {"1": {"token": "1"}, "2": {"token": "2"}, "3": {"token": "3"}}

        with mock.patch("builtins.open", mock.mock_open(read_data="1\n2\n3\n")) as file_mock:
            nft_snapshot.main(
                False, True, False, False, "test_cm", False, "outfile", "tokenfile", False
            )
            file_mock.assert_called_once_with("tokenfile")
        pop_holders_mock.assert_called_once_with(expected_tokens, "tokenfile")
        holders_mock.assert_called_once_with(expected_tokens)

    def test_main_attributes(self, mocker):
        pop_accts_mock = mocker.patch.object(nft_snapshot, "populate_account_details_async")
        attrs_mock = mocker.patch.object(nft_snapshot, "attribute_distribution")
        expected_tokens = {"1": {"token": "1"}, "2": {"token": "2"}, "3": {"token": "3"}}

        with mock.patch("builtins.open", mock.mock_open(read_data="1\n2\n3\n")) as file_mock:
            nft_snapshot.main(
                False, False, True, False, "test_cm", False, "outfile", "tokenfile", False
            )
            file_mock.assert_called_once_with("tokenfile")
        pop_accts_mock.assert_called_once_with(expected_tokens, "tokenfile")
        attrs_mock.assert_called_once_with(expected_tokens)

    def test_main_snapshot(self, mocker):
        pop_holders_mock = mocker.patch.object(nft_snapshot, "populate_holders_details_async")
        pop_accts_mock = mocker.patch.object(nft_snapshot, "populate_account_details_async")
        snap_mock = mocker.patch.object(nft_snapshot.output, "holder_snapshot")
        expected_tokens = {"1": {"token": "1"}, "2": {"token": "2"}, "3": {"token": "3"}}

        with mock.patch("builtins.open", mock.mock_open(read_data="1\n2\n3\n")) as file_mock:
            nft_snapshot.main(
                False, False, False, True, "test_cm", False, "outfile", "tokenfile", False
            )
            file_mock.assert_called_once_with("tokenfile")
        pop_holders_mock.assert_called_once_with(expected_tokens, "tokenfile")
        pop_accts_mock.assert_called_once_with(expected_tokens, "tokenfile")
        snap_mock.assert_called_once_with(expected_tokens, "outfile")

    def test_main_bust_cache(self, mocker):
        cache_mock = mocker.patch.object(nft_snapshot.cache, "save_request_cache")

        with mock.patch("builtins.open", mock.mock_open(read_data="1\n2\n3\n")) as file_mock:
            nft_snapshot.main(
                False, False, False, False, "test_cm", False, "outfile", "tokenfile", True
            )
            file_mock.assert_called_once_with("tokenfile")
        cache_mock.assert_called_once_with("tokenfile", {})

    def test_populate_holders_details_async(self, mocker):
        cache_mock = mocker.patch.object(nft_snapshot.cache, "save_request_cache")
        fetch_mock = mocker.patch.object(nft_snapshot, "fetch_token_data_from_network_async")
        input_dict = {"1": {"token": "1"}, "2": {"token": "2"}, "3": {"token": "3"}}
        expected = {
            "1": {"token": "1", "holders": {}},
            "2": {"token": "2", "holders": {}},
            "3": {"token": "3", "holders": {}},
        }
        fetch_mock.return_value = expected

        result = nft_snapshot.populate_holders_details_async(input_dict, "cachefile")
        fetch_mock.assert_called_once_with(
            sh.create_solana_client, input_dict, "holders", sh.get_holder_info_from_solana_async
        )
        cache_mock.assert_called_once_with("cachefile", expected)
        assert result == expected

    def test_populate_account_details_async(self, mocker):
        cache_mock = mocker.patch.object(nft_snapshot.cache, "save_request_cache")
        fetch_mock = mocker.patch.object(nft_snapshot, "fetch_token_data_from_network_async")
        input_dict = {"1": {"token": "1"}, "2": {"token": "2"}, "3": {"token": "3"}}
        expected = {
            "1": {"token": "1", "account": {}},
            "2": {"token": "2", "account": {}},
            "3": {"token": "3", "account": {}},
        }
        fetch_mock.return_value = expected

        result = nft_snapshot.populate_account_details_async(input_dict, "cachefile")
        fetch_mock.assert_has_calls(
            (
                mock.call(
                    sh.create_solana_client,
                    input_dict,
                    "account",
                    sh.get_account_info_from_solana_async,
                ),
                mock.call(
                    hh.create_http_client, input_dict, "arweave", nft_snapshot.get_arweave_metadata
                ),
            )
        )
        assert cache_mock.call_count == 2
        assert result == expected

    @pytest.mark.asyncio
    async def test_fetch_token_data_from_network_async(self, mocker):
        input_dict = {"1": {"token": "1"}}
        expected = {"1": {"token": "1"}}  # Hasn't changed because it's mocked out
        test_fn = mocker.AsyncMock()
        result = await nft_snapshot.fetch_token_data_from_network_async(
            hh.create_http_client, input_dict, "fill_key", test_fn
        )
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_arweave_metadata(self, mocker):
        client = mock.MagicMock()
        hh_mock = mocker.patch.object(nft_snapshot.hh, "async_http_request")
        response_dict = {"hat": "funny"}
        hh_mock.return_value = response_dict
        input_dict = {"token": "1", "account": {"data": {"uri": "https://ipfs.io/"}}}
        expected = {
            "token": "1",
            "account": {"data": {"uri": "https://ipfs.io/"}},
            "arweave": response_dict,
        }
        result = await nft_snapshot.get_arweave_metadata(client, input_dict, AsyncLimiter(1000, 1))
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_arweave_metadata_no_uri(self, mocker):
        client = mock.MagicMock()
        hh_mock = mocker.patch.object(nft_snapshot.hh, "async_http_request")
        response_dict = {"hat": "funny"}
        hh_mock.return_value = response_dict
        input_dict = {"token": "1", "account": {"data": {}}}
        expected = {"token": "1", "account": {"data": {}}, "arweave": {}}
        result = await nft_snapshot.get_arweave_metadata(client, input_dict, AsyncLimiter(1000, 1))
        assert result == expected

    def test_holder_counts(self, mocker):
        output_mock = mocker.patch.object(nft_snapshot, "output")
        output_mock.format_biggest_holders.return_value = "result_string"
        input_dict = {
            "token_1": {"holders": {"info": {"owner": "wallet_1"}}},
            "token_2": {"holders": {"info": {"owner": "wallet_2"}}},
            "token_3": {"holders": {"info": {"owner": "wallet_1"}}},
            "token_4": {"holders": {"info": {}}},
            "token_5": {"holders": {}},
        }
        result = nft_snapshot.holder_counts(input_dict)
        assert result == "result_string"
        output_mock.format_biggest_holders.assert_called_once_with(
            5, {"wallet_1": 2, "wallet_2": 1, "": 2}
        )

    def test_attribute_distribution(self, mocker):
        output_mock = mocker.patch.object(nft_snapshot, "output")
        output_mock.format_trait_frequency.return_value = "result_string"
        input_dict = {
            "token_1": {
                "arweave": {
                    "attributes": [
                        {
                            "trait_type": "hair",
                            "value": "white",
                        },
                        {
                            "trait_type": "eyes",
                            "value": "blue",
                        },
                    ]
                }
            },
            "token_2": {
                "arweave": {
                    "attributes": [
                        {
                            "trait_type": "hair",
                            "value": "white",
                        },
                        {
                            "trait_type": "eyes",
                            "value": None,
                        },
                    ]
                }
            },
            "token_3": {"arweave": {}},
        }
        result = nft_snapshot.attribute_distribution(input_dict)
        assert result == "result_string"
        output_mock.format_trait_frequency.assert_called_once_with(
            2, {"hair": {"white": 2}, "eyes": {"blue": 1, "": 1}}
        )

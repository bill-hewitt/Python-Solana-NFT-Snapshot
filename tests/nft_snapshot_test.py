import mock
import pytest
from aiolimiter import AsyncLimiter

import nft_snapshot
from util import http_helpers as hh
from util import solana_helpers as sh
from util.token import Token


class TestNftSnapshot:
    def test_main_token_list(self, mocker):
        input_dict = {"1": Token(token="1"), "2": Token(token="2"), "3": Token(token="3")}
        tc_mock = mocker.patch.object(nft_snapshot, "token_cache")
        tc_mock.load.return_value = input_dict
        wtl_mock = mocker.patch.object(nft_snapshot, "write_token_list")

        sh_mock = mocker.patch.object(nft_snapshot, "sh")
        sh_mock.get_token_list_from_candymachine_id.return_value = ["12345"]

        nft_snapshot.main(
            True, False, False, False, "test_cm", False, "outfile", "tokenfile", False
        )
        sh_mock.get_token_list_from_candymachine_id.assert_called_once_with("test_cm", False)
        wtl_mock.assert_called_once_with("tokenfile", ["12345"])

    def test_main_holder_list(self, mocker):
        input_dict = {"1": Token(token="1"), "2": Token(token="2"), "3": Token(token="3")}
        tc_mock = mocker.patch.object(nft_snapshot.token_cache, "load")
        tc_mock.return_value = input_dict
        rtl_mock = mocker.patch.object(nft_snapshot, "read_token_list")
        rtl_mock.return_value = ["1", "2", "3"]

        pop_holders_mock = mocker.patch.object(nft_snapshot, "populate_holders_details_async")
        holders_mock = mocker.patch.object(nft_snapshot, "holder_counts")

        nft_snapshot.main(
            False, True, False, False, "test_cm", False, "outfile", "tokenfile", False
        )
        rtl_mock.assert_called_once_with("tokenfile")
        pop_holders_mock.assert_called_once_with(input_dict)
        holders_mock.assert_called_once_with(input_dict)

    def test_main_attributes(self, mocker):
        input_dict = {"1": Token(token="1"), "2": Token(token="2"), "3": Token(token="3")}
        tc_mock = mocker.patch.object(nft_snapshot.token_cache, "load")
        tc_mock.return_value = input_dict
        rtl_mock = mocker.patch.object(nft_snapshot, "read_token_list")
        rtl_mock.return_value = ["1", "2", "3"]

        pop_accts_mock = mocker.patch.object(nft_snapshot, "populate_account_details_async")
        attrs_mock = mocker.patch.object(nft_snapshot, "attribute_distribution")

        nft_snapshot.main(
            False, False, True, False, "test_cm", False, "outfile", "tokenfile", False
        )
        rtl_mock.assert_called_once_with("tokenfile")
        pop_accts_mock.assert_called_once_with(input_dict)
        attrs_mock.assert_called_once_with(input_dict)

    def test_main_snapshot(self, mocker):
        input_dict = {"1": Token(token="1"), "2": Token(token="2"), "3": Token(token="3")}
        tc_mock = mocker.patch.object(nft_snapshot.token_cache, "load")
        tc_mock.return_value = input_dict
        rtl_mock = mocker.patch.object(nft_snapshot, "read_token_list")
        rtl_mock.return_value = ["1", "2", "3"]

        pop_holders_mock = mocker.patch.object(nft_snapshot, "populate_holders_details_async")
        pop_accts_mock = mocker.patch.object(nft_snapshot, "populate_account_details_async")
        snap_mock = mocker.patch.object(nft_snapshot.output, "holder_snapshot")

        nft_snapshot.main(
            False, False, False, True, "test_cm", False, "outfile", "tokenfile", False
        )
        rtl_mock.assert_called_once_with("tokenfile")
        pop_holders_mock.assert_called_once_with(input_dict)
        pop_accts_mock.assert_called_once_with(input_dict)
        snap_mock.assert_called_once_with(input_dict, "outfile")

    def test_main_bust_cache(self, mocker):
        cache_mock = mocker.patch.object(nft_snapshot.token_cache, "save")
        rtl_mock = mocker.patch.object(nft_snapshot, "read_token_list")
        rtl_mock.return_value = []

        nft_snapshot.main(
            False, False, False, False, "test_cm", False, "outfile", "tokenfile", True
        )
        cache_mock.assert_called_once_with({})

    def test_populate_holders_details_async(self, mocker):
        cache_mock = mocker.patch.object(nft_snapshot.token_cache, "save")
        fetch_mock = mocker.patch.object(nft_snapshot, "fetch_token_data_from_network_async")
        holder_mock = mocker.patch.object(nft_snapshot.sh, "get_holder_account_info_from_solana")
        input_dict = {
            "token_1": Token(token="token_1"),
            "token_2": Token(token="token_2"),
            "token_3": Token(token="token_3"),
        }
        fetch_mock.return_value = input_dict
        holder_mock.return_value = input_dict

        result = nft_snapshot.populate_holders_details_async(input_dict)
        fetch_mock.assert_called_once_with(
            sh.create_solana_client,
            input_dict,
            "token_account",
            sh.get_token_account_from_solana_async,
        )
        holder_mock.assert_called_once_with(input_dict)
        assert cache_mock.call_count == 2
        assert result == input_dict

    def test_populate_account_details_async(self, mocker):
        cache_mock = mocker.patch.object(nft_snapshot.token_cache, "save")
        fetch_mock = mocker.patch.object(nft_snapshot, "fetch_token_data_from_network_async")
        input_dict = {
            "token_1": Token(token="token_1"),
            "token_2": Token(token="token_2"),
            "token_3": Token(token="token_3"),
        }
        fetch_mock.return_value = input_dict

        result = nft_snapshot.populate_account_details_async(input_dict)
        fetch_mock.assert_has_calls(
            (
                mock.call(
                    sh.create_solana_client,
                    input_dict,
                    "name",
                    sh.get_account_info_from_solana_async,
                ),
                mock.call(
                    hh.create_http_client, input_dict, "image", nft_snapshot.get_arweave_metadata
                ),
            )
        )
        assert cache_mock.call_count == 2
        assert result == input_dict

    @pytest.mark.asyncio
    async def test_fetch_token_data_from_network_async(self, mocker):
        input_token = Token(token="test_token", token_account="")
        input_dict = {"test_token": input_token}

        test_fn = mocker.AsyncMock()
        result = await nft_snapshot.fetch_token_data_from_network_async(
            hh.create_http_client, input_dict, "token_account", test_fn
        )
        assert result == input_dict

    @pytest.mark.asyncio
    async def test_get_arweave_metadata(self, mocker):
        client = mock.MagicMock()
        hh_mock = mocker.patch.object(nft_snapshot.hh, "async_http_request")
        response_dict = {
            "image": "https://www.iana.org/_img/2022/iana-logo-header.svg",
            "attributes": [{"trait_type": "hat", "value": "funny"}],
        }
        hh_mock.return_value = response_dict
        input_token = Token(token="1", data_uri="https://ipfs.io/")

        result = await nft_snapshot.get_arweave_metadata(client, input_token, AsyncLimiter(1000, 1))
        assert result == input_token
        assert input_token.image == "https://www.iana.org/_img/2022/iana-logo-header.svg"
        assert input_token.traits == {"hat": "funny"}

    @pytest.mark.asyncio
    async def test_get_arweave_metadata_no_uri(self, mocker):
        client = mock.MagicMock()
        hh_mock = mocker.patch.object(nft_snapshot.hh, "async_http_request")
        response_dict = {"hat": "funny"}
        hh_mock.return_value = response_dict
        input_token = Token(token="1", data_uri="")

        result = await nft_snapshot.get_arweave_metadata(client, input_token, AsyncLimiter(1000, 1))
        assert result == input_token
        assert input_token.image == ""
        assert input_token.traits == {}

    def test_holder_counts(self, mocker):
        output_mock = mocker.patch.object(nft_snapshot, "output")
        output_mock.format_biggest_holders.return_value = "result_string"
        input_dict = {
            "token_1": Token(token="token_1", holder_address="wallet_1"),
            "token_2": Token(token="token_2", holder_address="wallet_2"),
            "token_3": Token(token="token_3", holder_address="wallet_1"),
            "token_4": Token(token="token_4", holder_address=""),
            "token_5": Token(token="token_5", holder_address=""),
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
            "token_1": Token(token="token_1", traits={"hair": "white", "eyes": "blue"}),
            "token_2": Token(token="token_2", traits={"hair": "white", "eyes": None}),
            "token_3": Token(token="token_3", traits={}),
        }

        result = nft_snapshot.attribute_distribution(input_dict)
        assert result == "result_string"
        output_mock.format_trait_frequency.assert_called_once_with(
            2, {"hair": {"white": 2}, "eyes": {"blue": 1, "": 1}}
        )

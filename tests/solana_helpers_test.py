import base64

import aiolimiter
import base58
import pytest
from solana.rpc.async_api import AsyncClient

from util import solana_helpers
from util.token import Token


class TestSolanaHelpers:
    def test_get_token_list_from_candymachine_id(self, mocker):
        client_mock = mocker.patch("solana.rpc.api.Client")
        client_mock.return_value.get_program_accounts.return_value = {
            "result": [{"account": {"data": [base64.b64encode(b"123456789")]}}]
        }
        test_cm_id = "4wTTi885HkQ6awqRGQkHAdXXzE46DyqLNXtfo1uz5ub3"  # Mindfolk
        expected = [base58.b58encode("123456789").decode()]

        result = solana_helpers.get_token_list_from_candymachine_id(test_cm_id)
        client_mock.assert_called_once_with("https://rpc.theindex.io", timeout=30)
        client_mock.return_value.get_program_accounts.assert_called_once()
        assert result == expected

    def test_get_token_list_from_candymachine_id_v2(self, mocker):
        client_mock = mocker.patch("solana.rpc.api.Client")
        client_mock.return_value.get_program_accounts.return_value = {
            "result": [{"account": {"data": [base64.b64encode(b"123456789")]}}]
        }
        test_cm_id = "HHGsTSzwPpYMYDGgUqssgAsMZMsYbshgrhMge8Ypgsjx"  # DTP CMv2
        expected = [base58.b58encode("123456789").decode()]

        result = solana_helpers.get_token_list_from_candymachine_id(test_cm_id, use_v2=True)
        client_mock.assert_called_once_with("https://rpc.theindex.io", timeout=30)
        client_mock.return_value.get_program_accounts.assert_called_once()
        assert result == expected

    def test_create_solana_client(self):
        result = solana_helpers.create_solana_client()
        assert isinstance(result, AsyncClient)

    @pytest.mark.asyncio
    async def test_get_token_account_from_solana_async(self, mocker):
        client_mock = mocker.MagicMock(AsyncClient)
        client_mock.get_token_largest_accounts.return_value = {
            "result": {"value": [{"address": "12345"}]}
        }

        test_token = "7z1YPxYiKK3c8ZgC4eEaA3dZDCb88LK34Nk4yGBeZnao"  # Mindfolk Founders #176
        input_token = Token(token=test_token)

        result = await solana_helpers.get_token_account_from_solana_async(
            client_mock, input_token, aiolimiter.AsyncLimiter(1000, 1)
        )
        client_mock.get_token_largest_accounts.assert_called_once_with(test_token)
        assert result == input_token
        assert input_token.token_account == "12345"

    @pytest.mark.asyncio
    async def test_get_token_account_from_solana_async_with_no_holder(self, mocker):
        client_mock = mocker.MagicMock(AsyncClient)
        client_mock.get_token_largest_accounts.return_value = {"result": {"value": None}}

        test_token = "7z1YPxYiKK3c8ZgC4eEaA3dZDCb88LK34Nk4yGBeZnao"  # Mindfolk Founders #176
        input_token = Token(token=test_token)

        result = await solana_helpers.get_token_account_from_solana_async(
            client_mock, input_token, aiolimiter.AsyncLimiter(1000, 1)
        )
        client_mock.get_token_largest_accounts.assert_called_once_with(test_token)
        assert result == input_token
        assert input_token.token_account == ""

    def test_get_holder_account_info_from_solana_async(self, mocker):
        client_mock = mocker.patch("solana.rpc.api.Client")
        client_mock.return_value.get_multiple_accounts.return_value = {
            "result": {
                "value": [
                    {"data": {"parsed": {"info": {"owner": "test1", "tokenAmount": {"amount": 1}}}}}
                ]
            }
        }
        test_token = "7z1YPxYiKK3c8ZgC4eEaA3dZDCb88LK34Nk4yGBeZnao"  # Mindfolk Founders #176
        input_token = Token(token=test_token, token_account="token_account")
        input_dict = {test_token: input_token}

        result = solana_helpers.get_holder_account_info_from_solana(input_dict)
        client_mock.return_value.get_multiple_accounts.assert_called_with(
            ["token_account"], encoding="jsonParsed"
        )
        assert result == input_dict
        assert input_token.amount == 1
        assert input_token.holder_address == "test1"

    def test_get_holder_account_info_from_solana_async_with_no_holder(self, mocker):
        test_token = "7z1YPxYiKK3c8ZgC4eEaA3dZDCb88LK34Nk4yGBeZnao"  # Mindfolk Founders #176
        input_token = Token(token=test_token, token_account="")
        input_dict = {test_token: input_token}

        result = solana_helpers.get_holder_account_info_from_solana(input_dict)
        assert result == input_dict
        assert input_token.amount == 0
        assert input_token.holder_address == ""

    def test_get_holder_account_info_from_solana_async_with_token_account_but_no_holder(
        self, mocker
    ):
        client_mock = mocker.patch("solana.rpc.api.Client")
        client_mock.return_value.get_multiple_accounts.return_value = {"result": {"value": [{}]}}

        test_token = "7z1YPxYiKK3c8ZgC4eEaA3dZDCb88LK34Nk4yGBeZnao"  # Mindfolk Founders #176
        input_token = Token(token=test_token, token_account="token_account")
        input_dict = {test_token: input_token}

        result = solana_helpers.get_holder_account_info_from_solana(input_dict)
        client_mock.return_value.get_multiple_accounts.assert_called_with(
            ["token_account"], encoding="jsonParsed"
        )
        assert result == input_dict
        assert input_token.amount == 0
        assert input_token.holder_address == ""

    @pytest.mark.asyncio
    async def test_get_account_info_from_solana_async(self, mocker):
        client_mock = mocker.MagicMock(AsyncClient)
        client_mock.get_account_info.return_value = {
            "result": {"value": {"data": [base64.b64encode(b"123456789")]}}
        }
        metadata_mock = mocker.patch.object(solana_helpers, "metadata")
        metadata_mock.get_metadata_account.return_value = "string1"
        metadata_mock.unpack_metadata_account.return_value = {
            "data": {"name": "String #2", "uri": "https://www.google.com"}
        }

        test_token = "7z1YPxYiKK3c8ZgC4eEaA3dZDCb88LK34Nk4yGBeZnao"  # Mindfolk Founders #176
        input_token = Token(token=test_token)

        result = await solana_helpers.get_account_info_from_solana_async(
            client_mock, input_token, aiolimiter.AsyncLimiter(1000, 1)
        )
        metadata_mock.get_metadata_account.assert_called_once_with(test_token)
        client_mock.get_account_info.assert_called_once_with("string1")
        metadata_mock.unpack_metadata_account.assert_called_once_with(b"123456789")
        assert result == input_token
        assert input_token.name == "String #2"
        assert input_token.id == "2"
        assert input_token.data_uri == "https://www.google.com"

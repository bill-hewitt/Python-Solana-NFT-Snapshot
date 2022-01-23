import base64

import aiolimiter
import base58
import mock
import pytest
from solana.rpc.async_api import AsyncClient

from util import solana_helpers


class TestSolanaHelpers:
    def test_get_token_list_from_candymachine_id(self, mocker):
        client_mock = mocker.patch("solana.rpc.api.Client")
        client_mock.return_value.get_program_accounts.return_value = {
            "result": [{"account": {"data": [base64.b64encode(b"123456789")]}}]
        }
        test_cm_id = "4wTTi885HkQ6awqRGQkHAdXXzE46DyqLNXtfo1uz5ub3"  # Mindfolk
        expected = [base58.b58encode("123456789").decode()]
        result = solana_helpers.get_token_list_from_candymachine_id(test_cm_id)
        client_mock.assert_called_once_with("https://ssc-dao.genesysgo.net/", timeout=120)
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
        client_mock.assert_called_once_with("https://ssc-dao.genesysgo.net/", timeout=120)
        client_mock.return_value.get_program_accounts.assert_called_once()
        assert result == expected

    def test_create_solana_client(self):
        result = solana_helpers.create_solana_client()
        assert isinstance(result, AsyncClient)

    @pytest.mark.asyncio
    async def test_get_holder_info_from_solana_async(self, mocker):
        client_mock = mocker.MagicMock(AsyncClient)
        client_mock.get_token_largest_accounts.return_value = {
            "result": {"value": [{"address": "12345"}]}
        }
        client_mock.get_account_info.return_value = {
            "result": {"value": {"data": {"parsed": {"holder_1": 1, "holder_2": 2}}}}
        }
        test_token = "7z1YPxYiKK3c8ZgC4eEaA3dZDCb88LK34Nk4yGBeZnao"  # Mindfolk Founders #176
        input_dict = {
            "token": test_token,
        }
        expected = {"token": test_token, "holders": {"holder_1": 1, "holder_2": 2}}
        result = await solana_helpers.get_holder_info_from_solana_async(
            client_mock, input_dict, aiolimiter.AsyncLimiter(1000, 1)
        )
        client_mock.get_token_largest_accounts.assert_called_once_with(test_token)
        client_mock.get_account_info.assert_called_with("12345", encoding="jsonParsed")
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_holder_info_from_solana_async_with_no_holder(self, mocker):
        test_token = "7z1YPxYiKK3c8ZgC4eEaA3dZDCb88LK34Nk4yGBeZnao"  # Mindfolk Founders #176
        client_mock = mocker.MagicMock(AsyncClient)
        client_mock.get_token_largest_accounts.return_value = {"result": {"value": None}}
        input_dict = {
            "token": test_token,
        }
        expected = {"token": test_token, "holders": {}}
        result = await solana_helpers.get_holder_info_from_solana_async(
            client_mock, input_dict, aiolimiter.AsyncLimiter(1000, 1)
        )
        client_mock.get_token_largest_accounts.assert_called_once_with(test_token)
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_account_info_from_solana_async(self, mocker):
        test_token = "7z1YPxYiKK3c8ZgC4eEaA3dZDCb88LK34Nk4yGBeZnao"  # Mindfolk Founders #176
        metadata_mock = mocker.patch.object(solana_helpers, "metadata")
        metadata_mock.get_metadata_account.return_value = "string1"
        metadata_mock.unpack_metadata_account.return_value = {"key": b"string2"}
        client_mock = mocker.MagicMock(AsyncClient)
        client_mock.get_account_info.return_value = {
            "result": {"value": {"data": [base64.b64encode(b"123456789")]}}
        }
        input_dict = {
            "token": test_token,
        }
        expected = {"token": test_token, "account": {"key": "string2"}}
        result = await solana_helpers.get_account_info_from_solana_async(
            client_mock, input_dict, aiolimiter.AsyncLimiter(1000, 1)
        )
        metadata_mock.get_metadata_account.assert_called_once_with(test_token)
        client_mock.get_account_info.assert_called_once_with("string1")
        metadata_mock.unpack_metadata_account.assert_called_once_with(b"123456789")
        assert result == expected

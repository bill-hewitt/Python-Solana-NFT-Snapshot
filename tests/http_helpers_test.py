import aiohttp
import mock
import pytest

from util import http_helpers


class TestHttpHelpers:
    @pytest.mark.asyncio
    async def test_create_http_client(self):
        result = http_helpers.create_http_client()
        assert isinstance(result, aiohttp.ClientSession)

    @pytest.mark.asyncio
    async def test_async_http_request(self, mocker):
        test_url = "http://www.example.com"
        session_mock = mocker.MagicMock(aiohttp.ClientSession)
        response_mock = mocker.Mock(aiohttp.ClientResponse)
        response_mock.status = 200
        response_mock.json = mock.AsyncMock()
        result_json = "This is just a test response"
        response_mock.json.return_value = result_json
        session_mock.get.return_value.__aenter__.return_value = response_mock

        result = await http_helpers.async_http_request(session_mock, test_url)
        session_mock.get.assert_called_once_with(test_url)
        response_mock.json.assert_called_once()
        assert result == result_json

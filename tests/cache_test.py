import json

import mock

from util import cache


class TestCache:
    def test_load_request_cache(self, mocker):
        test_cache_data = {"test": "result"}
        json_mock = mocker.patch("json.load")
        json_mock.return_value = test_cache_data

        file_mock = mock.mock_open(read_data=json.dumps(test_cache_data))
        with mock.patch("pathlib.Path.open", file_mock) as path_mock:
            config = cache.load_request_cache("test")
            path_mock.assert_called_once()
            json_mock.assert_called_once_with(file_mock())
        assert config == test_cache_data

    def test_save_request_cache(self, mocker):
        test_cache_data = {"test": "result"}
        json_mock = mocker.patch("json.dump")

        file_mock = mock.mock_open(read_data=json.dumps(test_cache_data))
        with mock.patch("pathlib.Path.open", file_mock) as path_mock:
            cache.save_request_cache("test", test_cache_data)
            path_mock.assert_called_once()
        json_mock.assert_called_once_with(test_cache_data, file_mock())

import pickle

import mock

from util import cache


class TestCache:
    def test_write_token_list(self):
        token_list = ["1", "2", "3"]
        with mock.patch("builtins.open") as file_mock:
            cache.write_token_list("tokenfile", token_list)
            file_mock.assert_called_once_with("tokenfile", "w")
            file_mock.return_value.write.called_once_with("1\n2\n3\n")

    def test_read_token_list(self):
        expected = ["1", "2", "3"]
        with mock.patch("builtins.open", mock.mock_open(read_data="1\n2\n3\n")) as file_mock:
            result = cache.read_token_list("tokenfile")
            file_mock.assert_called_once_with("tokenfile")
        assert result == expected

    def test_load_request_cache(self, mocker):
        test_cache_data = {"test": "result"}
        pickle_mock = mocker.patch("pickle.load")
        pickle_mock.return_value = test_cache_data

        file_mock = mock.mock_open(read_data=pickle.dumps(test_cache_data))
        with mock.patch("pathlib.Path.open", file_mock) as path_mock:
            cache.token_cache.initialize("test")
            config = cache.token_cache.load()
            path_mock.assert_called_once()
            pickle_mock.assert_called_once_with(file_mock())
        assert config == test_cache_data

    def test_save_request_cache(self, mocker):
        test_cache_data = {"test": "result"}
        pickle_mock = mocker.patch("pickle.dump")

        file_mock = mock.mock_open(read_data=pickle.dumps(test_cache_data))
        with mock.patch("pathlib.Path.open", file_mock) as path_mock:
            cache.token_cache.initialize("test")
            cache.token_cache.save(test_cache_data)
            path_mock.assert_called_once()
        pickle_mock.assert_called_once_with(test_cache_data, file_mock())

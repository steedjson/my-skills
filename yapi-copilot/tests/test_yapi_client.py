import json
import unittest
from unittest.mock import MagicMock, patch

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
from yapi_client import YApiClient, build_json_schema


class YApiClientTestCase(unittest.TestCase):
    def setUp(self):
        self.client = YApiClient("https://yapi.example.com", cookies={"_yapi_token": "mock_tok", "_yapi_uid": "123"})

    def test_build_json_schema(self):
        props = {
            "name": {"type": "string", "description": "Name"},
            "age": {"type": "integer", "description": "Age"}
        }
        schema = build_json_schema(props, required=["name"])
        self.assertEqual(schema["$schema"], "http://json-schema.org/draft-04/schema#")
        self.assertEqual(schema["type"], "object")
        self.assertIn("name", schema["properties"])
        self.assertEqual(schema["required"], ["name"])

    @patch("urllib.request.urlopen")
    def test_list_menu(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "errcode": 0,
            "errmsg": "ok",
            "data": [{"_id": 100, "name": "Category A", "list": []}]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = self.client.list_menu(1472)
        self.assertEqual(res["errcode"], 0)
        self.assertEqual(len(res["data"]), 1)
        self.assertEqual(res["data"][0]["name"], "Category A")

    @patch("urllib.request.urlopen")
    def test_find_category_by_name(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "errcode": 0,
            "errmsg": "ok",
            "data": [
                {"_id": 100, "name": "User Management", "list": []},
                {"_id": 200, "name": "Contract Management", "list": []}
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        cat = self.client.find_category_by_name(1472, "Contract Management")
        self.assertIsNotNone(cat)
        self.assertEqual(cat["_id"], 200)

        none_cat = self.client.find_category_by_name(1472, "Non-existent")
        self.assertIsNone(none_cat)


if __name__ == "__main__":
    unittest.main()

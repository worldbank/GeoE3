# -*- coding: utf-8 -*-
"""Unit tests for Space2Stats API client."""

import json
import unittest
from unittest.mock import MagicMock, patch

from qgis.PyQt.QtNetwork import QNetworkRequest

from geest.core.s2s_client import S2SClient


class _FakeReply:
    """Simple fake reply object for QgsNetworkAccessManager mocks."""

    def __init__(self, status_code, content):
        self._status_code = status_code
        self._content = content

    def attribute(self, key):
        if key == QNetworkRequest.HttpStatusCodeAttribute:
            return self._status_code
        return None

    def content(self):
        return self._content


class TestS2SClient(unittest.TestCase):
    """Test S2S client request handling and validation."""

    def setUp(self):
        self.aoi = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[30.0, -1.0], [30.5, -1.0], [30.5, -1.5], [30.0, -1.5], [30.0, -1.0]]],
            },
            "properties": {},
        }

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_health_returns_dict(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingGet.return_value = _FakeReply(200, b'{"status": "ok"}')
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient()
        result = client.health()

        self.assertEqual(result["status"], "ok")
        manager.blockingGet.assert_called_once()

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_fields_returns_list(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingGet.return_value = _FakeReply(200, b'["field_a", "field_b"]')
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient()
        result = client.fields()

        self.assertEqual(result, ["field_a", "field_b"])

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_fields_accepts_wrapped_fields_key(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingGet.return_value = _FakeReply(200, b'{"fields": ["field_a", "field_b"]}')
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient()
        result = client.fields()

        self.assertEqual(result, ["field_a", "field_b"])

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_fields_raises_on_unexpected_wrapped_object(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingGet.return_value = _FakeReply(200, b'{"detail": "upstream issue"}')
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient(max_attempts=1, backoff_base_seconds=0.0, backoff_jitter_seconds=0.0)
        with self.assertRaises(RuntimeError) as context:
            client.fields()

        self.assertIn("unexpected /fields response format", str(context.exception).lower())

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_summary_returns_records(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingPost.return_value = _FakeReply(200, b'[{"hex_id": "86754e64fffffff", "example": 1.2}]')
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient()
        result = client.summary(self.aoi, ["example"], spatial_join_method="centroid", geometry="point")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["hex_id"], "86754e64fffffff")

        _, payload = manager.blockingPost.call_args[0]
        decoded = json.loads(payload.decode("utf-8"))
        self.assertEqual(decoded["spatial_join_method"], "centroid")
        self.assertEqual(decoded["geometry"], "point")

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_summary_by_hexids_returns_records(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingPost.return_value = _FakeReply(200, b'[{"hex_id": "86754e64fffffff", "example": 7.7}]')
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient()
        result = client.summary_by_hexids(["86754e64fffffff"], ["example"], geometry="point")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["hex_id"], "86754e64fffffff")

        _, payload = manager.blockingPost.call_args[0]
        decoded = json.loads(payload.decode("utf-8"))
        self.assertEqual(decoded["hex_ids"], ["86754e64fffffff"])
        self.assertEqual(decoded["fields"], ["example"])

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_summary_by_hexids_rejects_empty_hex_ids(self, mock_network_access_manager):
        mock_network_access_manager.instance.return_value = MagicMock()
        client = S2SClient()

        with self.assertRaises(ValueError):
            client.summary_by_hexids([], ["example"])

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_summary_rejects_invalid_join_method(self, mock_network_access_manager):
        mock_network_access_manager.instance.return_value = MagicMock()
        client = S2SClient()

        with self.assertRaises(ValueError):
            client.summary(self.aoi, ["example"], spatial_join_method="invalid")

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_summary_rejects_invalid_geometry(self, mock_network_access_manager):
        mock_network_access_manager.instance.return_value = MagicMock()
        client = S2SClient()

        with self.assertRaises(ValueError):
            client.summary(self.aoi, ["example"], geometry="line")

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_summary_rejects_empty_fields(self, mock_network_access_manager):
        mock_network_access_manager.instance.return_value = MagicMock()
        client = S2SClient()

        with self.assertRaises(ValueError):
            client.summary(self.aoi, [])

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_request_raises_on_422(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingPost.return_value = _FakeReply(422, b'{"detail":"bad input"}')
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient()
        with self.assertRaises(ValueError):
            client.summary(self.aoi, ["example"])

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_request_raises_on_429(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingGet.return_value = _FakeReply(429, b"{}")
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient()
        with self.assertRaises(RuntimeError):
            client.fields()

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_request_raises_on_500(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingGet.return_value = _FakeReply(500, b"{}")
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient()
        with self.assertRaises(RuntimeError):
            client.health()

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_request_retries_on_503_then_succeeds(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingGet.side_effect = [_FakeReply(503, b"{}"), _FakeReply(200, b'{"status": "ok"}')]
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient(max_attempts=3, backoff_base_seconds=0.0, backoff_jitter_seconds=0.0)
        result = client.health()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(manager.blockingGet.call_count, 2)

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_request_parses_json_with_trailing_extra_data(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingGet.return_value = _FakeReply(200, b'["field_a", "field_b"]garbage-trailer')
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient(max_attempts=1, backoff_base_seconds=0.0, backoff_jitter_seconds=0.0)
        result = client.fields()

        self.assertEqual(result, ["field_a", "field_b"])

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_request_rejects_multiple_json_documents(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingGet.return_value = _FakeReply(200, b'{"detail":"oops"}["field_a"]')
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient(max_attempts=1, backoff_base_seconds=0.0, backoff_jitter_seconds=0.0)
        with self.assertRaises(RuntimeError):
            client.fields()

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_request_parses_json_with_bom_and_null_prefix(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingGet.return_value = _FakeReply(200, b'\xef\xbb\xbf\x00\x00{"status": "ok"}')
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient(max_attempts=1, backoff_base_seconds=0.0, backoff_jitter_seconds=0.0)
        result = client.health()

        self.assertEqual(result.get("status"), "ok")

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_request_raises_after_retry_exhausted_on_503(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingGet.return_value = _FakeReply(503, b"{}")
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient(max_attempts=3, backoff_base_seconds=0.0, backoff_jitter_seconds=0.0)
        with self.assertRaises(RuntimeError) as context:
            client.health()

        self.assertIn("temporarily unavailable", str(context.exception).lower())
        self.assertEqual(manager.blockingGet.call_count, 3)

    @patch("geest.core.s2s_client.QgsNetworkAccessManager")
    def test_request_does_not_retry_on_422(self, mock_network_access_manager):
        manager = MagicMock()
        manager.blockingPost.return_value = _FakeReply(422, b'{"detail":"bad input"}')
        mock_network_access_manager.instance.return_value = manager

        client = S2SClient(max_attempts=4, backoff_base_seconds=0.0, backoff_jitter_seconds=0.0)
        with self.assertRaises(ValueError):
            client.summary(self.aoi, ["example"])

        self.assertEqual(manager.blockingPost.call_count, 1)


if __name__ == "__main__":
    unittest.main()

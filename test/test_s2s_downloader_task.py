# -*- coding: utf-8 -*-
"""Unit tests for S2S downloader task."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from osgeo import ogr

from geest.core.tasks.s2s_downloader_task import S2SDownloaderTask


class TestS2SDownloaderTask(unittest.TestCase):
    """Tests for Phase 2 S2SDownloaderTask behavior."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_s2s_task_")
        self.aoi = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[30.0, -1.0], [30.5, -1.0], [30.5, -1.5], [30.0, -1.5], [30.0, -1.0]]],
            },
            "properties": {},
        }
        self.fields = ["example_field"]

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch("geest.core.tasks.s2s_downloader_task.S2SClient")
    def test_run_success_writes_valid_gpkg(self, mock_client_class):
        client = mock_client_class.return_value
        client.health.return_value = {"status": "ok"}
        client.fields.return_value = ["example_field"]
        client.summary.return_value = [
            {
                "hex_id": "86754e64fffffff",
                "example_field": 12.34,
                "geometry": {"type": "Point", "coordinates": [30.25, -1.25]},
            }
        ]

        task = S2SDownloaderTask(
            aoi=self.aoi,
            fields=self.fields,
            working_dir=self.temp_dir,
            filename="s2s_test",
            geometry="point",
        )

        success = task.run()
        self.assertTrue(success)
        self.assertTrue(os.path.exists(task.output_path))

        dataset = ogr.Open(task.output_path, 0)
        self.assertIsNotNone(dataset)
        layer = dataset.GetLayerByName("s2s_test")
        self.assertIsNotNone(layer)
        self.assertEqual(layer.GetFeatureCount(), 1)

    @patch("geest.core.tasks.s2s_downloader_task.S2SClient")
    def test_run_fails_when_field_missing(self, mock_client_class):
        client = mock_client_class.return_value
        client.health.return_value = {"status": "ok"}
        client.fields.return_value = ["other_field"]

        task = S2SDownloaderTask(
            aoi=self.aoi,
            fields=self.fields,
            working_dir=self.temp_dir,
            filename="s2s_test_missing",
        )

        errors = []
        task.error_occurred.connect(errors.append)

        success = task.run()
        self.assertFalse(success)
        self.assertEqual(len(errors), 1)
        self.assertIn("Requested S2S fields are unavailable", errors[0])
        self.assertFalse(os.path.exists(task.output_path))

    @patch("geest.core.tasks.s2s_downloader_task.S2SClient")
    def test_run_continues_when_fields_endpoint_unexpected_format(self, mock_client_class):
        client = mock_client_class.return_value
        client.health.return_value = {"status": "ok"}
        client.fields.side_effect = RuntimeError("Unexpected /fields response format: object keys [detail]")
        client.summary.return_value = [
            {
                "hex_id": "86754e64fffffff",
                "example_field": 42.0,
                "geometry": {"type": "Point", "coordinates": [30.25, -1.25]},
            }
        ]

        task = S2SDownloaderTask(
            aoi=self.aoi,
            fields=self.fields,
            working_dir=self.temp_dir,
            filename="s2s_fields_fallback",
            geometry="point",
        )

        success = task.run()
        self.assertTrue(success)
        self.assertTrue(os.path.exists(task.output_path))

    @patch("geest.core.tasks.s2s_downloader_task.S2SClient")
    def test_run_fails_on_empty_summary_rows(self, mock_client_class):
        client = mock_client_class.return_value
        client.health.return_value = {"status": "ok"}
        client.fields.return_value = ["example_field"]
        client.summary.return_value = []

        task = S2SDownloaderTask(
            aoi=self.aoi,
            fields=self.fields,
            working_dir=self.temp_dir,
            filename="s2s_empty",
        )

        success = task.run()
        self.assertFalse(success)
        self.assertFalse(os.path.exists(task.output_path))

    @patch("geest.core.tasks.s2s_downloader_task.S2SClient")
    def test_run_surfaces_temporary_service_unavailable_errors(self, mock_client_class):
        client = mock_client_class.return_value
        client.health.return_value = {"status": "ok"}
        client.fields.return_value = ["example_field"]
        client.summary.side_effect = RuntimeError("S2S service temporarily unavailable (503) after 4 attempts.")

        task = S2SDownloaderTask(
            aoi=self.aoi,
            fields=self.fields,
            working_dir=self.temp_dir,
            filename="s2s_retry_exhausted",
            geometry="point",
        )

        errors = []
        task.error_occurred.connect(errors.append)

        success = task.run()
        self.assertFalse(success)
        self.assertEqual(len(errors), 1)
        self.assertIn("temporarily unavailable", errors[0].lower())
        self.assertFalse(os.path.exists(task.output_path))

    @patch("geest.core.tasks.s2s_downloader_task.S2SClient")
    def test_run_hex_ids_mode_writes_chunked_output(self, mock_client_class):
        client = mock_client_class.return_value
        client.health.return_value = {"status": "ok"}
        client.fields.return_value = ["example_field"]
        client.summary_by_hexids.side_effect = [
            [
                {
                    "hex_id": "86754e64fffffff",
                    "example_field": 1.0,
                    "geometry": {"type": "Point", "coordinates": [30.0, -1.0]},
                }
            ],
            [
                {
                    "hex_id": "86754e65fffffff",
                    "example_field": 2.0,
                    "geometry": {"type": "Point", "coordinates": [30.2, -1.2]},
                }
            ],
        ]

        task = S2SDownloaderTask(
            aoi={},
            fields=self.fields,
            working_dir=self.temp_dir,
            filename="s2s_hex_chunked",
            geometry="point",
            mode="hex_ids",
            hex_ids=["86754e64fffffff", "86754e65fffffff"],
            chunk_size=1,
        )

        chunks = []
        task.chunk_completed.connect(lambda current, total: chunks.append((current, total)))

        success = task.run()
        self.assertTrue(success)
        self.assertTrue(os.path.exists(task.output_path))
        self.assertEqual(chunks, [(1, 2), (2, 2)])

        dataset = ogr.Open(task.output_path, 0)
        self.assertIsNotNone(dataset)
        layer = dataset.GetLayerByName("s2s_hex_chunked")
        self.assertIsNotNone(layer)
        self.assertEqual(layer.GetFeatureCount(), 2)

    def test_normalize_geometry_from_json_string(self):
        geometry_string = '{"type":"Point","coordinates":[30.2,-1.3]}'
        normalized = S2SDownloaderTask._normalize_geometry(geometry_string)
        self.assertIsInstance(normalized, dict)
        self.assertEqual(normalized.get("type"), "Point")

    def test_normalize_geometry_invalid_string_returns_none(self):
        normalized = S2SDownloaderTask._normalize_geometry("not json")
        self.assertIsNone(normalized)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Tests for key-based grid column write utilities."""

import os
import shutil
import tempfile
import unittest

from osgeo import ogr

from geest.core.grid_column_utils import write_joined_values_to_grid


class TestWriteJoinedValuesToGrid(unittest.TestCase):
    """Validate direct key join writes from external GPKG into study_area_grid."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_grid_join_")
        self.main_gpkg = os.path.join(self.temp_dir, "study_area.gpkg")
        self.source_gpkg = os.path.join(self.temp_dir, "s2s.gpkg")

        self._create_study_area_grid()
        self._create_source_layer()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_study_area_grid(self):
        driver = ogr.GetDriverByName("GPKG")
        dataset = driver.CreateDataSource(self.main_gpkg)
        layer = dataset.CreateLayer("study_area_grid", geom_type=ogr.wkbPolygon)
        layer.CreateField(ogr.FieldDefn("h3_index", ogr.OFTString))
        layer.CreateField(ogr.FieldDefn("area_name", ogr.OFTString))

        layer_defn = layer.GetLayerDefn()
        for hex_id, area_name in [
            ("h3_a", "Area 1"),
            ("h3_b", "Area 1"),
            ("h3_c", "Area 2"),
        ]:
            feature = ogr.Feature(layer_defn)
            feature.SetField("h3_index", hex_id)
            feature.SetField("area_name", area_name)
            layer.CreateFeature(feature)

        dataset = None

    def _create_source_layer(self):
        driver = ogr.GetDriverByName("GPKG")
        dataset = driver.CreateDataSource(self.source_gpkg)
        layer = dataset.CreateLayer("s2s_nighttime_lights", geom_type=ogr.wkbPoint)
        layer.CreateField(ogr.FieldDefn("hex_id", ogr.OFTString))
        layer.CreateField(ogr.FieldDefn("sum_viirs_ntl_2024", ogr.OFTReal))

        layer_defn = layer.GetLayerDefn()
        for hex_id, value in [
            ("h3_a", 10.5),
            ("h3_b", 20.5),
            ("h3_extra", 999.0),
        ]:
            feature = ogr.Feature(layer_defn)
            feature.SetField("hex_id", hex_id)
            feature.SetField("sum_viirs_ntl_2024", value)
            layer.CreateFeature(feature)

        dataset = None

    def _read_grid_values(self, column_name):
        dataset = ogr.Open(self.main_gpkg, 0)
        layer = dataset.GetLayerByName("study_area_grid")
        values = {}
        for feature in layer:
            values[feature.GetField("h3_index")] = feature.GetField(column_name)
        dataset = None
        return values

    def test_write_joined_values_to_grid_updates_matching_rows(self):
        updated_count = write_joined_values_to_grid(
            gpkg_path=self.main_gpkg,
            column_name="nighttime_lights",
            source_gpkg=self.source_gpkg,
            source_layer="s2s_nighttime_lights",
            source_key_field="hex_id",
            target_key_field="h3_index",
            source_value_field="sum_viirs_ntl_2024",
        )

        self.assertEqual(updated_count, 2)
        values = self._read_grid_values("nighttime_lights")
        self.assertAlmostEqual(values["h3_a"], 10.5)
        self.assertAlmostEqual(values["h3_b"], 20.5)
        self.assertIsNone(values["h3_c"])

    def test_write_joined_values_to_grid_respects_area_filter(self):
        updated_count = write_joined_values_to_grid(
            gpkg_path=self.main_gpkg,
            column_name="nighttime_lights",
            source_gpkg=self.source_gpkg,
            source_layer="s2s_nighttime_lights",
            source_key_field="hex_id",
            target_key_field="h3_index",
            source_value_field="sum_viirs_ntl_2024",
            area_name="Area 1",
        )

        self.assertEqual(updated_count, 2)
        values = self._read_grid_values("nighttime_lights")
        self.assertAlmostEqual(values["h3_a"], 10.5)
        self.assertAlmostEqual(values["h3_b"], 20.5)
        self.assertIsNone(values["h3_c"])


if __name__ == "__main__":
    unittest.main()

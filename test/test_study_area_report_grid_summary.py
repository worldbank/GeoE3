# -*- coding: utf-8 -*-
"""Unit tests for StudyAreaReport's closing "Grid Summary" page - key facts
about the study area and the analysis grid (area names, cell count, grid
type, cell size/H3 resolution, CRS), read straight from the GeoPackage.
Mirrors AnalysisReport's own study area summary page, which this module
doesn't otherwise share any code with (StudyAreaReport never touches
model.json).
"""
import os
import shutil
import tempfile
import unittest

from osgeo import ogr, osr

from geest.core.reports.study_area_report import StudyAreaReport

_EPSG_32632 = 32632  # a projected (metre-based) CRS


def _square_ring(x0, y0, size):
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint(x0, y0)
    ring.AddPoint(x0 + size, y0)
    ring.AddPoint(x0 + size, y0 + size)
    ring.AddPoint(x0, y0 + size)
    ring.AddPoint(x0, y0)
    polygon = ogr.Geometry(ogr.wkbPolygon)
    polygon.AddGeometry(ring)
    return polygon


def _build_test_gpkg(path, with_grid=True, h3=False):
    """A minimal GeoPackage shaped like a real study_area.gpkg.

    Args:
        path: Where to create the GeoPackage.
        with_grid: Whether to create study_area_grid/study_area_polygons
            at all - StudyAreaReport itself only requires
            study_area_creation_status to exist.
        h3: Whether the grid cells carry h3_resolution/h3_index (H3
            hexagonal grid) instead of being plain squares.
    """
    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(path)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(_EPSG_32632)

    status_layer = ds.CreateLayer("study_area_creation_status", srs, geom_type=ogr.wkbNone)
    status_layer.CreateField(ogr.FieldDefn("area_name", ogr.OFTString))

    if with_grid:
        polygons_layer = ds.CreateLayer("study_area_polygons", srs, geom_type=ogr.wkbPolygon)
        polygons_layer.CreateField(ogr.FieldDefn("area_name", ogr.OFTString))
        for name, origin in (("AreaOne", 0), ("AreaTwo", 2000)):
            feature = ogr.Feature(polygons_layer.GetLayerDefn())
            feature.SetField("area_name", name)
            feature.SetGeometry(_square_ring(origin, 0, 1000))
            polygons_layer.CreateFeature(feature)

        grid_layer = ds.CreateLayer("study_area_grid", srs, geom_type=ogr.wkbPolygon)
        grid_layer.CreateField(ogr.FieldDefn("area_name", ogr.OFTString))
        if h3:
            grid_layer.CreateField(ogr.FieldDefn("h3_resolution", ogr.OFTInteger))
            grid_layer.CreateField(ogr.FieldDefn("h3_index", ogr.OFTString))
        cell_size = 100
        for i in range(3):
            feature = ogr.Feature(grid_layer.GetLayerDefn())
            feature.SetField("area_name", "AreaOne")
            if h3:
                feature.SetField("h3_resolution", 6)
                feature.SetField("h3_index", f"abc{i}")
            feature.SetGeometry(_square_ring(i * cell_size, 0, cell_size))
            grid_layer.CreateFeature(feature)

    ds = None  # noqa: F841 - closes/flushes the GeoPackage


class TestGridFacts(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="geoe3_study_area_report_test_")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.gpkg_path = os.path.join(self.tmp_dir, "study_area.gpkg")

    def test_square_grid_reports_cell_size_area_names_and_total_area(self):
        _build_test_gpkg(self.gpkg_path, h3=False)
        report = StudyAreaReport(self.gpkg_path, report_name="Test")

        facts = dict(report._grid_facts())

        self.assertEqual(facts["Number of grid cells"], "3")
        self.assertEqual(facts["Grid type"], "Square")
        self.assertIn("100", facts["Grid cell size"])
        self.assertIn("AreaOne, AreaTwo", facts["Study areas (2)"])
        self.assertIn("km", facts["Total analysis area"])

    def test_h3_grid_reports_resolution_and_hex_area_instead_of_cell_size(self):
        _build_test_gpkg(self.gpkg_path, h3=True)
        report = StudyAreaReport(self.gpkg_path, report_name="Test")

        facts = dict(report._grid_facts())

        self.assertEqual(facts["Grid type"], "H3 hexagonal")
        self.assertEqual(facts["H3 resolution"], "6")
        self.assertIn("Average cell area", facts)
        self.assertNotIn("Grid cell size", facts)

    def test_a_single_study_area_uses_the_singular_label(self):
        driver = ogr.GetDriverByName("GPKG")
        ds = driver.CreateDataSource(self.gpkg_path)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(_EPSG_32632)
        ds.CreateLayer("study_area_creation_status", srs, geom_type=ogr.wkbNone)
        polygons_layer = ds.CreateLayer("study_area_polygons", srs, geom_type=ogr.wkbPolygon)
        polygons_layer.CreateField(ogr.FieldDefn("area_name", ogr.OFTString))
        feature = ogr.Feature(polygons_layer.GetLayerDefn())
        feature.SetField("area_name", "OnlyArea")
        feature.SetGeometry(_square_ring(0, 0, 1000))
        polygons_layer.CreateFeature(feature)
        grid_layer = ds.CreateLayer("study_area_grid", srs, geom_type=ogr.wkbPolygon)
        grid_layer.CreateField(ogr.FieldDefn("area_name", ogr.OFTString))
        feature = ogr.Feature(grid_layer.GetLayerDefn())
        feature.SetField("area_name", "OnlyArea")
        feature.SetGeometry(_square_ring(0, 0, 100))
        grid_layer.CreateFeature(feature)
        ds = None  # noqa: F841

        report = StudyAreaReport(self.gpkg_path, report_name="Test")
        facts = dict(report._grid_facts())

        self.assertEqual(facts["Study area"], "OnlyArea")

    def test_no_grid_layer_returns_no_facts(self):
        _build_test_gpkg(self.gpkg_path, with_grid=False)
        report = StudyAreaReport(self.gpkg_path, report_name="Test")

        self.assertEqual(report._grid_facts(), [])


if __name__ == "__main__":
    unittest.main()

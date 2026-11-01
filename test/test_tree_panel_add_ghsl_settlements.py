# -*- coding: utf-8 -*-
"""Regression test for TreePanel.add_ghsl_settlements_to_map() visibility.

TreePanel is a heavy QWidget that needs a loaded .ui file to construct,
so this calls the unbound method against a lightweight MagicMock
stand-in, matching the pattern in test_tree_panel_clear_item.py.

Guards against a real production bug: unlike add_to_map()/
add_grid_layer_to_map(), this function never re-enabled visibility on
the layer or its parent groups after adding it - if "GeoE3 Study Area"
(or an ancestor) was ever unchecked for any reason, "Layer added to
map" fired while nothing actually rendered, with no self-healing
re-check (worldbank/GeoE3 field report, 2026-10-24).
"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from osgeo import ogr
from qgis.core import QgsProject

from geest.gui.panels.tree_panel import TreePanel


class TestAddGhslSettlementsToMapRestoresVisibility(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_add_ghsl_settlements_")
        study_area_dir = os.path.join(self.temp_dir, "study_area")
        os.makedirs(study_area_dir)
        self.gpkg_path = os.path.join(study_area_dir, "study_area.gpkg")

        driver = ogr.GetDriverByName("GPKG")
        dataset = driver.CreateDataSource(self.gpkg_path)
        from osgeo import osr

        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        layer = dataset.CreateLayer("ghsl_settlements", srs, geom_type=ogr.wkbPolygon)
        layer_defn = layer.GetLayerDefn()
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for px, py in [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]:
            ring.AddPoint(px, py)
        polygon = ogr.Geometry(ogr.wkbPolygon)
        polygon.AddGeometry(ring)
        feature = ogr.Feature(layer_defn)
        feature.SetGeometry(polygon)
        layer.CreateFeature(feature)
        dataset = None

        self.panel = MagicMock()
        self.panel.working_directory = self.temp_dir
        # add_ghsl_settlements_to_map() now checks _find_layer_tree_node()
        # first to reveal an already-loaded layer instead of reloading it.
        # Left unconfigured, self.panel's auto-generated Mock attribute
        # returns a truthy Mock rather than None, which the method reads
        # as "already loaded" and walks up via .parent() forever - every
        # Mock.parent() call also auto-generates another truthy Mock, so
        # that walk never reaches a real None and spins until the test
        # process is killed. None is also the accurate answer here: this
        # test's whole premise is the "nothing loaded yet" precondition.
        self.panel._find_layer_tree_node = MagicMock(return_value=None)

    def tearDown(self):
        QgsProject.instance().clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("geest.gui.panels.tree_panel.iface")
    def test_a_pre_existing_unchecked_study_area_group_is_made_visible_again(self, mock_iface):
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        study_area_group = root.insertGroup(0, "GeoE3 Study Area")
        study_area_group.setItemVisibilityChecked(False)  # simulate the bug precondition

        TreePanel.add_ghsl_settlements_to_map(self.panel)

        self.assertTrue(study_area_group.isVisible())
        layer_nodes = [child for child in study_area_group.children() if hasattr(child, "layer")]
        self.assertEqual(len(layer_nodes), 1)
        self.assertTrue(layer_nodes[0].isVisible())


if __name__ == "__main__":
    unittest.main()

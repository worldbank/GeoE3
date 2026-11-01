# -*- coding: utf-8 -*-
"""Regression test for GeoE3Dock.open_associated_qgis_project().

Reproduces the "dreaded network layer error": after a country pack
import, re-opening the generated QGIS project silently overwrote the
correctly-saved road_network_layer_path with a different layer.

Root cause - QgsProject.read() adds the project's layers one at a time.
The road network combo's filtered layer list (every line layer
qualifies) resettles mid-load, auto-selecting whichever layer is current
once all layers are in. That auto-select fires
road_network_layer_path_changed unblocked, so it silently overwrites the
correct saved path with the wrong layer (e.g. an OSM-derived line layer
sharing the real road network's schema).
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from utilities_for_testing import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()

from qgis.core import QgsProject, QgsVectorLayer  # noqa: E402

from geest.gui.geoe3_dock import GeoE3Dock  # noqa: E402
from geest.utilities import resources_path  # noqa: E402


class TestOpenAssociatedQgisProjectRoadNetworkRace(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.tmpdir = tempfile.mkdtemp()

        self.dock = GeoE3Dock(parent=PARENT, json_file=resources_path("resources", "model.json"))

        self.correct_layer = QgsVectorLayer("LineString?crs=EPSG:32620", "road_network", "memory")
        self.wrong_layer = QgsVectorLayer("LineString?crs=EPSG:4326", "Active_Transport_Network", "memory")
        self.assertTrue(self.correct_layer.isValid())
        self.assertTrue(self.wrong_layer.isValid())
        QgsProject.instance().addMapLayer(self.correct_layer)

        self.analysis_item = self.dock.tree_widget.model.get_analysis_item()
        self.analysis_item.setAttribute("road_network_layer_path", self.correct_layer.source())

        self.fake_qgis_project_path = os.path.join(self.tmpdir, "fake_project.qgz")
        with open(self.fake_qgis_project_path, "w") as f:
            f.write("")
        self.analysis_item.setAttribute("qgis_project_path", self.fake_qgis_project_path)

    def tearDown(self):
        self.dock.deleteLater()
        QgsProject.instance().clear()

    def test_road_network_path_survives_a_mid_read_auto_select(self):
        def fake_read(path, *args, **kwargs):
            # Simulate QGIS adding a second, schema-identical line layer
            # mid-read, and the combo auto-selecting it as the project's
            # layer list settles - the exact race that corrupted the model.
            QgsProject.instance().addMapLayer(self.wrong_layer)
            self.dock.road_network_widget.road_layer_combo.setLayer(self.wrong_layer)
            return True

        with patch.object(QgsProject.instance(), "read", side_effect=fake_read):
            self.dock.open_associated_qgis_project()

        self.assertEqual(
            self.analysis_item.attribute("road_network_layer_path"),
            self.correct_layer.source(),
        )
        self.assertEqual(
            self.dock.road_network_widget.road_layer_combo.currentLayer(),
            self.correct_layer,
        )


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Unit tests for RoadNetworkPanel.restore_layer_from_path().

RoadNetworkPanel now shows a read-only label fed from model.json, with a
"Load / Change Network Layer" button that opens a short-lived picker
dialog - there is no live combo listening to QgsProject's layer registry
any more, so restore_layer_from_path() only ever needs to update that
label. It must never emit road_network_layer_path_changed itself: doing
so is what previously let restoring the UI turn into an unwanted write-back
to model.json (worldbank/GeoE3, cross-project road network leak).
"""
import os
import tempfile
import unittest

from qgis.core import QgsProject

from geest.gui.panels.road_network_panel import RoadNetworkPanel


class TestRestoreLayerFromPathNeverWritesBack(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.panel = RoadNetworkPanel()
        self.emitted = []
        self.panel.road_network_layer_path_changed.connect(self.emitted.append)

    def tearDown(self):
        self.panel.deleteLater()
        QgsProject.instance().clear()

    def test_restoring_an_existing_file_updates_the_label_and_does_not_emit(self):
        with tempfile.NamedTemporaryFile(suffix=".gpkg") as tmp:
            self.panel.restore_layer_from_path(tmp.name)

            self.assertEqual(self.emitted, [])
            self.assertEqual(self.panel.current_layer_label.text(), os.path.basename(tmp.name))
            self.assertEqual(self.panel.road_network_layer_path(), tmp.name)

    def test_restoring_a_missing_file_shows_not_set_and_does_not_emit(self):
        self.panel.restore_layer_from_path("/no/such/file.gpkg")

        self.assertEqual(self.emitted, [])
        self.assertEqual(self.panel.current_layer_label.text(), "Not set")
        self.assertIsNone(self.panel.road_network_layer_path())

    def test_restoring_an_empty_path_shows_not_set_and_does_not_emit(self):
        self.panel.restore_layer_from_path("")

        self.assertEqual(self.emitted, [])
        self.assertEqual(self.panel.current_layer_label.text(), "Not set")


if __name__ == "__main__":
    unittest.main()

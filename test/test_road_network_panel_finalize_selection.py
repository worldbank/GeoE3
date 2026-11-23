# -*- coding: utf-8 -*-
"""Unit tests for RoadNetworkPanel._finalize_road_layer_selection() and
on_change_network_layer_clicked().

_finalize_road_layer_selection() is now the ONLY place that emits
road_network_layer_path_changed - always from one explicit, synchronous
action (a file pick, an OSM download finishing, or the inline picker
row's Ok), never from a live combo reacting to ambient QGIS/project
signals. network_layer_combo itself has no signal connected to it at
all - its currentLayer() is only ever read once, when Ok is clicked.
"""
import tempfile
import unittest
from unittest.mock import patch

from qgis.core import QgsCoordinateReferenceSystem, QgsProject, QgsVectorLayer

from geest.gui.panels.road_network_panel import RoadNetworkPanel


class TestFinalizeRoadLayerSelection(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.panel = RoadNetworkPanel()
        # isVisible() reflects the whole ancestor chain, not just this
        # widget's own setVisible() state - without show(), every child
        # reports isVisible() == False regardless of its own state.
        self.panel.show()
        self.panel.working_directory = tempfile.mkdtemp()
        self.panel._crs = QgsCoordinateReferenceSystem("EPSG:32620")
        self.emitted = []
        self.panel.road_network_layer_path_changed.connect(self.emitted.append)

    def tearDown(self):
        self.panel.deleteLater()
        QgsProject.instance().clear()

    def test_matching_crs_layer_is_committed_without_reprojecting(self):
        layer = QgsVectorLayer("LineString?crs=EPSG:32620", "road", "memory")
        self.assertTrue(layer.isValid())

        self.panel._finalize_road_layer_selection(layer)

        self.assertEqual(self.emitted, [layer.source()])
        self.assertEqual(self.panel.road_network_layer_path(), layer.source())
        self.assertNotEqual(self.panel.current_layer_label.text(), "Not set")

    def test_mismatched_crs_layer_is_reprojected_and_committed_once(self):
        layer = QgsVectorLayer("LineString?crs=EPSG:4326", "road_wgs84", "memory")
        self.assertTrue(layer.isValid())

        self.panel._finalize_road_layer_selection(layer)

        self.assertEqual(len(self.emitted), 1)
        final_path = self.emitted[0]
        self.assertIn("study_area", final_path)
        self.assertTrue(final_path.endswith(".gpkg"))

    def test_non_line_layer_is_rejected_and_nothing_is_emitted(self):
        polygon_layer = QgsVectorLayer("Polygon?crs=EPSG:32620", "not_a_road", "memory")
        self.assertTrue(polygon_layer.isValid())

        with patch("geest.gui.panels.road_network_panel.QMessageBox"):
            self.panel._finalize_road_layer_selection(polygon_layer)

        self.assertEqual(self.emitted, [])

    def test_change_button_does_nothing_when_no_working_directory(self):
        self.panel.working_directory = ""

        with patch("geest.gui.panels.road_network_panel.QMessageBox") as mock_box:
            self.panel.on_change_network_layer_clicked()

        mock_box.critical.assert_called_once()
        self.assertEqual(self.emitted, [])
        self.assertFalse(self.panel.network_layer_combo.isVisible())

    def test_change_button_swaps_label_for_the_inline_picker_row(self):
        self.panel.on_change_network_layer_clicked()

        self.assertFalse(self.panel.current_layer_label.isVisible())
        self.assertFalse(self.panel.change_network_layer_button.isVisible())
        self.assertTrue(self.panel.network_layer_combo.isVisible())
        self.assertTrue(self.panel.ok_network_layer_button.isVisible())
        self.assertTrue(self.panel.cancel_network_layer_button.isVisible())

    def test_ok_commits_the_combos_chosen_layer_and_exits_edit_mode(self):
        layer = QgsVectorLayer("LineString?crs=EPSG:32620", "road", "memory")
        self.assertTrue(layer.isValid())
        QgsProject.instance().addMapLayer(layer)
        self.panel.network_layer_combo.setLayer(layer)

        self.panel.on_change_network_layer_clicked()
        self.panel.on_network_layer_ok_clicked()

        self.assertEqual(self.emitted, [layer.source()])
        self.assertTrue(self.panel.current_layer_label.isVisible())
        self.assertFalse(self.panel.network_layer_combo.isVisible())

    def test_cancel_discards_the_pick_and_exits_edit_mode(self):
        layer = QgsVectorLayer("LineString?crs=EPSG:32620", "road", "memory")
        self.assertTrue(layer.isValid())
        QgsProject.instance().addMapLayer(layer)
        self.panel.network_layer_combo.setLayer(layer)

        self.panel.on_change_network_layer_clicked()
        self.panel.on_network_layer_cancel_clicked()

        self.assertEqual(self.emitted, [])
        self.assertTrue(self.panel.current_layer_label.isVisible())
        self.assertFalse(self.panel.network_layer_combo.isVisible())


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Unit tests for clearing a layer selection in the vector/raster datasource widgets.

Selecting "no layer" in the layer combo and clicking OK used to leave
"{widget_key}_layer_id"/"_layer_source"/etc. at their previous value -
only the (unused) "{widget_key}_layer" key was ever cleared. That meant
clearing the selection didn't actually un-configure the indicator
(getStatus() still saw a real source) and silently re-selected the old
layer the next time the dialog opened (worldbank/GeoE3 field report,
2026-11-25).

These call the unbound update_attributes() against a lightweight stand-in
(layer_combo/shapefile_line_edit as plain mocks) rather than constructing
the real QWidget - VectorDataSourceWidget's QgsMapLayerComboBox only
lists layers already in QgsProject.instance() through live Qt model
signals that don't reliably settle in a headless unittest run, which has
nothing to do with the update_attributes() logic under test here.
"""
import unittest
from unittest.mock import MagicMock

from qgis.core import QgsWkbTypes

from geest.gui.widgets.datasource_widgets.raster_datasource_widget import (
    RasterDataSourceWidget,
)
from geest.gui.widgets.datasource_widgets.vector_and_field_datasource_widget import (
    VectorAndFieldDataSourceWidget,
)
from geest.gui.widgets.datasource_widgets.vector_datasource_widget import (
    VectorDataSourceWidget,
)


def _fake_layer(source="fake.gpkg|layername=fake", name="fake", layer_id="fake_id_123"):
    layer = MagicMock()
    layer.name.return_value = name
    layer.source.return_value = source
    layer.providerType.return_value = "ogr"
    layer.crs.return_value.authid.return_value = "EPSG:32620"
    layer.wkbType.return_value = QgsWkbTypes.Point
    layer.id.return_value = layer_id
    return layer


class TestVectorDataSourceWidgetClearsSelection(unittest.TestCase):
    def test_clearing_the_layer_combo_clears_every_layer_key(self):
        widget = MagicMock()
        widget.widget_key = "use_point_per_cell"
        widget.attributes = {}
        widget.shapefile_line_edit.text.return_value = ""
        widget.layer_combo.currentLayer.return_value = _fake_layer()

        VectorDataSourceWidget.update_attributes(widget)
        self.assertTrue(widget.attributes["use_point_per_cell_layer_source"])
        self.assertTrue(widget.attributes["use_point_per_cell_layer_id"])

        widget.layer_combo.currentLayer.return_value = None
        VectorDataSourceWidget.update_attributes(widget)

        self.assertFalse(widget.attributes["use_point_per_cell_layer_source"])
        self.assertFalse(widget.attributes["use_point_per_cell_layer_id"])
        self.assertFalse(widget.attributes["use_point_per_cell_layer_name"])
        self.assertFalse(widget.attributes["use_point_per_cell_layer_provider_type"])
        self.assertFalse(widget.attributes["use_point_per_cell_layer_crs"])


class TestVectorAndFieldDataSourceWidgetClearsSelection(unittest.TestCase):
    def test_clearing_the_layer_combo_clears_every_layer_key(self):
        widget = MagicMock()
        widget.widget_key = "use_classify_polygon_into_classes"
        widget.attributes = {}
        widget.shapefile_line_edit.text.return_value = ""
        widget.layer_combo.currentLayer.return_value = _fake_layer()

        VectorAndFieldDataSourceWidget.update_attributes(widget)
        self.assertTrue(widget.attributes["use_classify_polygon_into_classes_layer_source"])

        widget.layer_combo.currentLayer.return_value = None
        VectorAndFieldDataSourceWidget.update_attributes(widget)

        self.assertFalse(widget.attributes["use_classify_polygon_into_classes_layer_source"])
        self.assertFalse(widget.attributes["use_classify_polygon_into_classes_layer_id"])
        self.assertFalse(widget.attributes["use_classify_polygon_into_classes_layer_name"])
        self.assertFalse(widget.attributes["use_classify_polygon_into_classes_layer_provider_type"])
        self.assertFalse(widget.attributes["use_classify_polygon_into_classes_layer_crs"])


class TestRasterDataSourceWidgetClearsSelection(unittest.TestCase):
    def test_clearing_the_layer_combo_clears_every_layer_key(self):
        widget = MagicMock()
        widget.widget_key = "use_nighttime_lights"
        widget.attributes = {}
        widget.raster_line_edit.text.return_value = ""
        widget.raster_layer_combo.currentLayer.return_value = _fake_layer(source="fake.tif")

        RasterDataSourceWidget.update_attributes(widget)
        self.assertTrue(widget.attributes["use_nighttime_lights_layer_source"])

        widget.raster_layer_combo.currentLayer.return_value = None
        RasterDataSourceWidget.update_attributes(widget)

        self.assertFalse(widget.attributes["use_nighttime_lights_layer_source"])
        self.assertFalse(widget.attributes["use_nighttime_lights_layer_id"])
        self.assertFalse(widget.attributes["use_nighttime_lights_layer_name"])
        self.assertFalse(widget.attributes["use_nighttime_lights_layer_provider_type"])
        self.assertFalse(widget.attributes["use_nighttime_lights_layer_crs"])


if __name__ == "__main__":
    unittest.main()

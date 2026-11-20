# -*- coding: utf-8 -*-
"""ImportCountryPackTask.finished(): the reconstructed project's layers
actually land in the QGIS project, not just on disk.
"""

import json
import os
import shutil
import tempfile
import unittest

from osgeo import ogr, osr
from qgis.core import QgsProject
from utilities_for_testing import get_qgis_app

from geest.core.country_pack import build_country_pack
from geest.core.tasks import ImportCountryPackTask

QGIS_APP = get_qgis_app()

TEST_DATA = os.path.join(os.path.dirname(__file__), "test_data")


class TestImportCountryPackTaskLoadsLayers(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.pack_path = os.path.join(TEST_DATA, "_import_task_layers_test.gpkg")
        if os.path.exists(self.pack_path):
            os.remove(self.pack_path)
        self.import_dir = tempfile.mkdtemp(prefix="geoe3_import_task_test_")

    def tearDown(self):
        QgsProject.instance().clear()
        if os.path.exists(self.pack_path):
            os.remove(self.pack_path)
        shutil.rmtree(self.import_dir, ignore_errors=True)

    def _model(self):
        return {
            "dimensions": [
                {
                    "factors": [
                        {
                            "indicators": [
                                {
                                    "id": "Childcare_Location",
                                    "indicator": "Childcare Access",
                                    "analysis_mode": "use_point_per_cell",
                                    "point_per_cell_layer_source": os.path.join(
                                        TEST_DATA, "points", "fake_childcare.gpkg|layername=fake_childcare"
                                    ),
                                },
                                {
                                    "id": "Generic_Raster",
                                    "indicator": "Generic Raster Indicator",
                                    "analysis_mode": "use_nighttime_lights",
                                    "nighttime_lights_raster": os.path.join(TEST_DATA, "rasters", "raster.tif"),
                                },
                            ]
                        }
                    ]
                }
            ],
        }

    def test_every_reconstructed_layer_lands_in_the_qgis_project(self):
        build_country_pack(working_directory=TEST_DATA, model=self._model(), output_path=self.pack_path)

        task = ImportCountryPackTask(self.pack_path, self.import_dir)
        self.assertTrue(task.run())
        task.finished(True)

        layers = QgsProject.instance().mapLayers()
        names = {layer.name() for layer in layers.values()}
        self.assertIn("Childcare Access", names)
        self.assertIn("Generic Raster Indicator", names)
        self.assertIn("study_area_grid", names)
        self.assertTrue(all(layer.isValid() for layer in layers.values()))

        # Every loaded layer's source lives inside the new working
        # directory - nothing leaked in from the original fixture
        # directory or anywhere else outside the reconstructed project.
        import_dir_abs = os.path.abspath(self.import_dir)
        for layer in layers.values():
            source_path = layer.source().split("|")[0].split("?")[0]
            self.assertTrue(
                os.path.abspath(source_path).startswith(import_dir_abs),
                f"'{layer.name()}' points outside the new working directory: {source_path}",
            )

    def test_saves_a_qgis_project_named_after_the_working_directory(self):
        build_country_pack(working_directory=TEST_DATA, model=self._model(), output_path=self.pack_path)

        task = ImportCountryPackTask(self.pack_path, self.import_dir)
        self.assertTrue(task.run())
        task.finished(True)

        expected_project_path = os.path.join(self.import_dir, f"{os.path.basename(self.import_dir)}.qgz")
        self.assertTrue(os.path.exists(expected_project_path))
        self.assertEqual(QgsProject.instance().fileName(), expected_project_path)

        with open(os.path.join(self.import_dir, "model.json"), encoding="utf-8") as f:
            model = json.load(f)
        self.assertEqual(model["qgis_project_path"], expected_project_path)

    def test_layers_land_in_three_mutually_exclusive_groups(self):
        build_country_pack(working_directory=TEST_DATA, model=self._model(), output_path=self.pack_path)

        task = ImportCountryPackTask(self.pack_path, self.import_dir)
        self.assertTrue(task.run())
        task.finished(True)

        root = QgsProject.instance().layerTreeRoot()
        study_area_group = root.findGroup("Study Area")
        results_group = root.findGroup("GeoE3 Results")
        inputs_group = root.findGroup(os.path.basename(self.import_dir))
        self.assertIsNotNone(study_area_group)
        self.assertIsNotNone(results_group)
        self.assertIsNotNone(inputs_group)
        for group in (study_area_group, results_group, inputs_group):
            self.assertTrue(group.isMutuallyExclusive())

        childcare_node = root.findLayer(
            next(
                layer.id() for layer in QgsProject.instance().mapLayers().values() if layer.name() == "Childcare Access"
            )
        )
        study_area_grid_node = root.findLayer(
            next(
                layer.id() for layer in QgsProject.instance().mapLayers().values() if layer.name() == "study_area_grid"
            )
        )
        self.assertEqual(childcare_node.parent(), inputs_group)
        self.assertEqual(study_area_grid_node.parent(), study_area_group)

    def test_csv_backed_indicator_loads_via_the_delimitedtext_provider(self):
        model = self._model()
        model["dimensions"][0]["factors"][0]["indicators"].append(
            {
                "id": "FCV",
                "analysis_mode": "use_csv_to_point_layer",
                "use_csv_to_point_layer_csv_file": os.path.join(TEST_DATA, "points", "fake_acled.csv"),
            }
        )
        # Derive the CSV's lon/lat from the existing (UTM) childcare
        # fixture's own points, reprojected to WGS84 - guaranteed to
        # fall inside the clip boundary once correctly reprojected
        # back, rather than guessed coordinates that might not.
        source_ds = ogr.Open(os.path.join(TEST_DATA, "points", "fake_childcare.gpkg"))
        source_layer = source_ds.GetLayerByName("fake_childcare")
        source_srs = source_layer.GetSpatialRef()
        wgs84_srs = osr.SpatialReference()
        wgs84_srs.ImportFromEPSG(4326)
        source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        wgs84_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(source_srs, wgs84_srs)

        csv_path = os.path.join(TEST_DATA, "points", "fake_acled.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("longitude,latitude,event\n")
            for i, feature in enumerate(source_layer):
                if i >= 2:
                    break
                geometry = feature.GetGeometryRef().Clone()
                geometry.Transform(transform)
                f.write(f"{geometry.GetX()},{geometry.GetY()},event_{i}\n")
        source_ds = None
        self.addCleanup(lambda: os.path.exists(csv_path) and os.remove(csv_path))

        build_country_pack(working_directory=TEST_DATA, model=model, output_path=self.pack_path)

        task = ImportCountryPackTask(self.pack_path, self.import_dir)
        self.assertTrue(task.run())
        task.finished(True)

        layers = {layer.name(): layer for layer in QgsProject.instance().mapLayers().values()}
        self.assertIn("FCV", layers)
        self.assertTrue(layers["FCV"].isValid())
        self.assertEqual(layers["FCV"].featureCount(), 2)

    def test_already_computed_results_get_their_qml_style_applied(self):
        """Regression test for a real bug: loadNamedStyle() returns
        (errorMessage, resultFlag), not (success, message) - reading it
        the other way round silently swallowed every failure (an empty
        error string is falsy) and reported every real failure as a
        success, so a reconstructed result layer kept QGIS's arbitrary
        auto-styling instead of the pack's actual style.
        """
        model = self._model()
        model["dimensions"][0]["factors"][0]["indicators"][1]["result_file"] = os.path.join(
            TEST_DATA, "rasters", "raster.tif"
        )

        build_country_pack(working_directory=TEST_DATA, model=model, output_path=self.pack_path)

        task = ImportCountryPackTask(self.pack_path, self.import_dir)
        self.assertTrue(task.run())
        task.finished(True)

        # The result layer's display name is the indicator's pretty title,
        # not its "{id}_result" internal key (see
        # test_result_layers_use_the_pretty_title_not_the_result_suffix) -
        # same lookup a live run's own add_to_map() would use.
        result_layer = next(
            layer for layer in QgsProject.instance().mapLayers().values() if layer.name() == "Generic Raster Indicator"
        )
        # indicator.qml sets a singlebandpseudocolor renderer - a freshly
        # loaded raster never gets that renderer on its own, so this only
        # passes if the style file was actually applied.
        self.assertEqual(result_layer.renderer().type(), "singlebandpseudocolor")

    def test_layer_names_preserve_the_original_project_titles_not_internal_keys(self):
        """Regression test: a country-pack round trip must show the same
        legend names the original project did, not the internal keys
        (indicator "id" slugs, fixed project-level keys, "{id}_result"
        technical names) the pack uses as its own GeoPackage table names.
        """
        model = self._model()
        model["dimensions"][0]["factors"][0]["indicators"][1]["result_file"] = os.path.join(
            TEST_DATA, "rasters", "raster.tif"
        )
        # A project-level input whose original display name was tracked
        # via sync_layer_metadata_fields() during a live run (see
        # "point_mask_layer_name" in country_pack_import.py's
        # PROJECT_LEVEL_DISPLAY_NAME_FIELD) - the pack's own output key is
        # always the fixed "point_mask", regardless of this.
        model["point_mask_shapefile"] = os.path.join(
            TEST_DATA, "points", "fake_childcare.gpkg|layername=fake_childcare"
        )
        model["point_mask_layer_name"] = "My Point Mask"

        build_country_pack(working_directory=TEST_DATA, model=model, output_path=self.pack_path)

        task = ImportCountryPackTask(self.pack_path, self.import_dir)
        self.assertTrue(task.run())
        task.finished(True)

        names = {layer.name() for layer in QgsProject.instance().mapLayers().values()}
        # Indicator input: pretty title, not the "id" slug.
        self.assertIn("Childcare Access", names)
        self.assertNotIn("Childcare_Location", names)
        # Indicator result: the same pretty title, not "{id}_result".
        self.assertIn("Generic Raster Indicator", names)
        self.assertNotIn("Generic_Raster_result", names)
        # Project-level input: its tracked original name, not the fixed
        # "point_mask" pack key.
        self.assertIn("My Point Mask", names)
        self.assertNotIn("point_mask", names)


if __name__ == "__main__":
    unittest.main()

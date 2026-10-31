# -*- coding: utf-8 -*-
import json
import os
import shutil
import tempfile
import unittest

from osgeo import gdal, ogr

from geest.core.country_pack import INDEX_SCORE_TABLE_NAME, PROJECT_MODEL_TABLE_NAME, build_country_pack
from geest.core.country_pack_import import (
    _indicator_import_targets,
    _project_level_import_targets,
    _result_import_targets,
    _sync_s2s_output_path,
    import_country_pack,
    result_layer_roles,
    result_qml_path,
)

TEST_DATA = os.path.join(os.path.dirname(__file__), "test_data")

STUDY_AREA_LAYER_NAMES = {
    "study_area_bbox",
    "study_area_bboxes",
    "study_area_polygons",
    "study_area_clip_polygons",
    "study_area_grid",
}


class TestIndicatorImportTargets(unittest.TestCase):
    def test_resolves_the_same_field_indicator_source_would_read(self):
        model = {
            "dimensions": [
                {
                    "factors": [
                        {
                            "indicators": [
                                {
                                    "id": "Fire",
                                    "analysis_mode": "use_environmental_hazards",
                                    "environmental_hazards_raster": "/old/fire.tif",
                                },
                                {
                                    "id": "Workplace_Index",
                                    "analysis_mode": "use_contextual_index_score",
                                    "index_score": 95,
                                },
                            ]
                        }
                    ]
                }
            ]
        }
        targets = _indicator_import_targets(model)
        self.assertEqual(set(targets), {"Fire"})
        indicator, field_name, kind = targets["Fire"]
        self.assertIs(indicator, model["dimensions"][0]["factors"][0]["indicators"][0])
        self.assertEqual(field_name, "environmental_hazards_raster")
        self.assertEqual(kind, "raster")

    def test_s2s_vector_fallback_is_resolved_too(self):
        model = {
            "dimensions": [
                {
                    "factors": [
                        {
                            "indicators": [
                                {
                                    "id": "Fire",
                                    "analysis_mode": "use_environmental_hazards",
                                    "environmental_hazards_raster": "",
                                    "environmental_hazards_layer_source": "/old/s2s_fire.gpkg|layername=x",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        _, field_name, kind = _indicator_import_targets(model)["Fire"]
        self.assertEqual(field_name, "environmental_hazards_layer_source")
        self.assertEqual(kind, "vector")


class TestProjectLevelImportTargets(unittest.TestCase):
    def test_resolves_road_network_and_population(self):
        model = {
            "road_network_layer_path": "/old/roads.shp",
            "population_layer_source": "/old/pop.tif",
            "population_source": "raster",
        }
        targets = _project_level_import_targets(model)
        self.assertEqual(targets["road_network"], ("road_network_layer_path", "vector"))
        self.assertEqual(targets["population"], ("population_layer_source", "raster"))

    def test_unconfigured_model_has_no_targets(self):
        self.assertEqual(_project_level_import_targets({}), {})


class TestResultImportTargets(unittest.TestCase):
    def test_resolves_prefixed_dimension_and_factor_names(self):
        model = {
            "dimensions": [
                {
                    "id": "contextual",
                    "result_file": "/old/contextual.vrt",
                    "factors": [{"id": "eplex", "result_file": ""}],
                }
            ]
        }
        targets = _result_import_targets(model)
        self.assertEqual(set(targets), {"dim_contextual_result"})
        node, field_name, kind = targets["dim_contextual_result"]
        self.assertIs(node, model["dimensions"][0])
        self.assertEqual(field_name, "result_file")
        self.assertEqual(kind, "raster")

    def test_resolves_extra_top_level_composite_products(self):
        model = {
            "geoe3_by_population": "/old/by_pop.vrt",
            "geoe3_score_subnational_aggregation": "/old/sub.gpkg|layername=sub",
        }
        targets = _result_import_targets(model)
        self.assertEqual(set(targets), {"geoe3_by_population", "geoe3_score_subnational_aggregation"})
        node, field_name, kind = targets["geoe3_by_population"]
        self.assertIs(node, model)
        self.assertEqual(field_name, "geoe3_by_population")
        self.assertEqual(kind, "raster")
        self.assertEqual(targets["geoe3_score_subnational_aggregation"][2], "vector")


class TestSyncS2sOutputPath(unittest.TestCase):
    def test_points_s2s_output_path_at_the_rewritten_layer_source(self):
        indicator = {
            "s2s_output_path": "/old/s2s_fire.gpkg",
            "environmental_hazards_layer_source": "/new/s2s_fire.gpkg|layername=s2s_fire",
        }
        _sync_s2s_output_path(indicator)
        self.assertEqual(indicator["s2s_output_path"], "/new/s2s_fire.gpkg")

    def test_leaves_untouched_when_not_present(self):
        indicator = {"environmental_hazards_raster": "/new/fire.tif"}
        _sync_s2s_output_path(indicator)
        self.assertNotIn("s2s_output_path", indicator)


class TestResultQmlPath(unittest.TestCase):
    def test_roles_resolve_for_dimension_factor_indicator_and_analysis(self):
        model = {
            "result_file": "/old/analysis.vrt",
            "dimensions": [
                {
                    "id": "contextual",
                    "result_file": "/old/dim.vrt",
                    "factors": [
                        {
                            "id": "eplex",
                            "result_file": "/old/fac.vrt",
                            "indicators": [{"id": "Workplace_Index", "result_file": "/old/ind.vrt"}],
                        }
                    ],
                }
            ],
        }
        roles = result_layer_roles(model)
        self.assertEqual(
            roles,
            {
                "analysis_result": "analysis",
                "dim_contextual_result": "dimension",
                "fac_eplex_result": "factor",
                "Workplace_Index_result": "indicator",
            },
        )

    def test_role_based_layers_resolve_to_their_qml_file(self):
        roles = {
            "dim_contextual_result": "dimension",
            "fac_eplex_result": "factor",
            "Workplace_Index_result": "indicator",
            "analysis_result": "analysis",
        }
        self.assertTrue(result_qml_path("dim_contextual_result", roles).endswith("dimension.qml"))
        self.assertTrue(result_qml_path("fac_eplex_result", roles).endswith("factor.qml"))
        self.assertTrue(result_qml_path("Workplace_Index_result", roles).endswith("indicator.qml"))
        self.assertTrue(result_qml_path("analysis_result", roles).endswith("analysis.qml"))

    def test_extra_top_level_fields_resolve_regardless_of_role(self):
        self.assertTrue(result_qml_path("geoe3_by_population", {}).endswith("geoe3_by_population_score.qml"))
        self.assertTrue(result_qml_path("opportunities_mask_result_file", {}).endswith("mask.qml"))
        self.assertTrue(result_qml_path("geoe3_score_subnational_aggregation", {}).endswith("geoe3_score_vector.qml"))

    def test_unrecognised_layer_name_has_no_style(self):
        self.assertIsNone(result_qml_path("Childcare_Location", {}))


class TestImportCountryPack(unittest.TestCase):
    """End-to-end: build a real pack from the same fixture data
    test_country_pack.py uses, then import it into a fresh empty
    directory and confirm the reconstructed project is self-contained
    and openable - the round trip the user actually asked for."""

    def setUp(self):
        self.pack_path = os.path.join(TEST_DATA, "_country_pack_import_test.gpkg")
        if os.path.exists(self.pack_path):
            os.remove(self.pack_path)
        self.import_dir = tempfile.mkdtemp(prefix="geoe3_import_test_")

    def tearDown(self):
        if os.path.exists(self.pack_path):
            os.remove(self.pack_path)
        shutil.rmtree(self.import_dir, ignore_errors=True)

    def _model(self):
        return {
            "working_folder": TEST_DATA,
            "qgis_project_path": "/some/other/project/elsewhere.qgz",
            "dimensions": [
                {
                    "id": "place_characterization",
                    "factors": [
                        {
                            "id": "fcv",
                            "indicators": [
                                {
                                    "id": "Childcare_Location",
                                    "analysis_mode": "use_point_per_cell",
                                    "point_per_cell_layer_source": os.path.join(
                                        TEST_DATA, "points", "fake_childcare.gpkg|layername=fake_childcare"
                                    ),
                                },
                                {
                                    "id": "Generic_Raster",
                                    "analysis_mode": "use_nighttime_lights",
                                    "nighttime_lights_raster": os.path.join(TEST_DATA, "rasters", "raster.tif"),
                                },
                                {
                                    "id": "Workplace_Index",
                                    "analysis_mode": "use_contextual_index_score",
                                    "index_score": 95,
                                },
                            ],
                        }
                    ],
                }
            ],
        }

    def _build_pack(self):
        model = self._model()
        build_country_pack(working_directory=TEST_DATA, model=model, output_path=self.pack_path)
        return model

    def test_round_trip_reconstructs_an_openable_self_contained_project(self):
        self._build_pack()

        summary = import_country_pack(self.pack_path, self.import_dir)
        self.assertEqual(summary["skipped"], [])

        model_json_path = os.path.join(self.import_dir, "model.json")
        self.assertTrue(os.path.exists(model_json_path))
        with open(model_json_path, encoding="utf-8") as f:
            reloaded = json.load(f)

        indicators = reloaded["dimensions"][0]["factors"][0]["indicators"]
        by_id = {i["id"]: i for i in indicators}

        # The manually-typed score survives untouched, straight from the
        # model.json blob - no index_score_values round trip needed.
        self.assertEqual(by_id["Workplace_Index"]["index_score"], 95)

        # The model's own record of where it lives is updated to the
        # new working directory, not left pointing at the exporting
        # machine's.
        self.assertEqual(reloaded["working_folder"], self.import_dir)

        # qgis_project_path is cleared, not left pointing at a .qgz
        # whose own layers reference the exporting machine's paths -
        # loading it would pull foreign layers into the freshly
        # started QGIS project the import flow requires.
        self.assertEqual(reloaded["qgis_project_path"], "")

        # Spatial inputs got rewritten to point inside the new working
        # directory, not the original fixture directory.
        childcare_path = by_id["Childcare_Location"]["point_per_cell_layer_source"]
        self.assertTrue(childcare_path.startswith(self.import_dir))
        self.assertNotIn(TEST_DATA, childcare_path)

        raster_path = by_id["Generic_Raster"]["nighttime_lights_raster"]
        self.assertTrue(raster_path.startswith(self.import_dir))

        # And every rewritten path actually resolves to real, openable data.
        # gdal.OpenEx() doesn't understand QGIS's "path|layername=X"
        # convention (see country_pack.py's _split_source_uri()
        # docstring) - split it the same way to open the right layer.
        base_path, layer_name = childcare_path.split("|layername=")
        vector_ds = gdal.OpenEx(base_path, gdal.OF_VECTOR)
        self.assertIsNotNone(vector_ds)
        self.assertIsNotNone(vector_ds.GetLayerByName(layer_name))
        vector_ds = None

        raster_ds = gdal.Open(raster_path)
        self.assertIsNotNone(raster_ds)
        raster_ds = None

        # study_area.gpkg was reconstructed wholesale under study_area/.
        study_area_gpkg = os.path.join(self.import_dir, "study_area", "study_area.gpkg")
        dataset = gdal.OpenEx(study_area_gpkg, gdal.OF_VECTOR)
        self.assertIsNotNone(dataset)
        layer_names = {dataset.GetLayerByIndex(i).GetName() for i in range(dataset.GetLayerCount())}
        self.assertEqual(layer_names, STUDY_AREA_LAYER_NAMES)
        dataset = None

        # Neither metadata table leaks into "imported" as a real layer.
        self.assertNotIn(PROJECT_MODEL_TABLE_NAME, summary["imported"])
        self.assertNotIn(INDEX_SCORE_TABLE_NAME, summary["imported"])

    def test_extra_top_level_composite_products_survive_the_round_trip(self):
        """Regression test: a project whose analysis_aggregation step
        has run carries up to 8 extra top-level composite products
        (GHSL-masked/by-population rasters, per-zone subnational
        aggregation vectors) - confirmed live on a real regional-scale
        project (StLuciaH3), none of which build_country_pack()/
        import_country_pack() touched before this was added, leaving
        them pointing at the exporting machine's path forever."""
        model = self._model()
        model["geoe3_by_population"] = os.path.join(TEST_DATA, "rasters", "raster.tif")
        model["geoe3_score_subnational_aggregation"] = os.path.join(
            TEST_DATA, "points", "fake_childcare.gpkg|layername=fake_childcare"
        )
        build_country_pack(working_directory=TEST_DATA, model=model, output_path=self.pack_path)

        import_country_pack(self.pack_path, self.import_dir)
        with open(os.path.join(self.import_dir, "model.json"), encoding="utf-8") as f:
            reloaded = json.load(f)

        new_raster = reloaded["geoe3_by_population"]
        self.assertTrue(new_raster.startswith(self.import_dir))
        raster_ds = gdal.Open(new_raster)
        self.assertIsNotNone(raster_ds)
        raster_ds = None

        new_vector = reloaded["geoe3_score_subnational_aggregation"]
        self.assertTrue(new_vector.startswith(self.import_dir))
        base_path, layer_name = new_vector.split("|layername=")
        vector_ds = gdal.OpenEx(base_path, gdal.OF_VECTOR)
        self.assertIsNotNone(vector_ds.GetLayerByName(layer_name))
        vector_ds = None

    def test_feature_counts_survive_the_round_trip(self):
        self._build_pack()
        import_country_pack(self.pack_path, self.import_dir)

        with open(os.path.join(self.import_dir, "model.json"), encoding="utf-8") as f:
            reloaded = json.load(f)
        childcare_path = reloaded["dimensions"][0]["factors"][0]["indicators"][0]["point_per_cell_layer_source"]

        original_ds = ogr.Open(os.path.join(TEST_DATA, "points", "fake_childcare.gpkg"))
        original_count = original_ds.GetLayerByName("fake_childcare").GetFeatureCount()
        original_ds = None

        base_path, layer_name = childcare_path.split("|layername=")
        imported_ds = ogr.Open(base_path)
        imported_count = imported_ds.GetLayerByName(layer_name).GetFeatureCount()
        imported_ds = None

        self.assertEqual(original_count, imported_count)

    def test_refuses_to_import_into_a_directory_that_already_has_a_project(self):
        self._build_pack()
        with open(os.path.join(self.import_dir, "model.json"), "w", encoding="utf-8") as f:
            f.write("{}")
        with self.assertRaises(RuntimeError):
            import_country_pack(self.pack_path, self.import_dir)

    def test_refuses_to_import_a_file_that_is_not_a_country_pack(self):
        not_a_pack = os.path.join(TEST_DATA, "_not_a_country_pack.gpkg")
        driver = ogr.GetDriverByName("GPKG")
        dataset = driver.CreateDataSource(not_a_pack)
        dataset.CreateLayer("some_layer", geom_type=ogr.wkbPoint)
        dataset = None
        try:
            with self.assertRaises(RuntimeError):
                import_country_pack(not_a_pack, self.import_dir)
        finally:
            os.remove(not_a_pack)


if __name__ == "__main__":
    unittest.main()

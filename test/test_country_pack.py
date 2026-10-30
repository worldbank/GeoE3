# -*- coding: utf-8 -*-
import os
import unittest

from osgeo import ogr, osr

from geest.core.country_pack import (
    INDEX_SCORE_TABLE_NAME,
    PROJECT_MODEL_TABLE_NAME,
    _actual_table_names,
    all_sources,
    build_country_pack,
    index_score_values,
    indicator_source,
    project_level_sources,
    result_sources,
    study_area_sources,
)

TEST_DATA = os.path.join(os.path.dirname(__file__), "test_data")

#: build_country_pack() always writes this table (the full model.json),
#: regardless of what sources the project has configured.
ALWAYS_WRITTEN_TABLE_NAMES = {PROJECT_MODEL_TABLE_NAME}

#: Layers in test/test_data/study_area/study_area.gpkg - bundled
#: automatically by build_country_pack() whenever working_directory has
#: a study_area/study_area.gpkg, on top of whatever indicator sources a
#: test configures.
STUDY_AREA_LAYER_NAMES = {
    "study_area_bbox",
    "study_area_bboxes",
    "study_area_polygons",
    "study_area_clip_polygons",
    "study_area_grid",
}


class TestIndicatorSource(unittest.TestCase):
    def test_vector_widget_mode_prefers_layer_source_over_shapefile(self):
        indicator = {
            "id": "Kindergartens_Location",
            "analysis_mode": "use_multi_buffer_point",
            "multi_buffer_point_layer_source": "/path/live.gpkg|layername=points",
            "multi_buffer_point_shapefile": "/path/browsed.shp",
        }
        source = indicator_source(indicator)
        self.assertEqual(source.path, "/path/live.gpkg|layername=points")
        self.assertEqual(source.kind, "vector")
        self.assertEqual(source.layer_name, "Kindergartens_Location")

    def test_vector_widget_mode_falls_back_to_shapefile(self):
        indicator = {
            "id": "Water_Sanitation",
            "analysis_mode": "use_single_buffer_point",
            "single_buffer_point_layer_source": "",
            "single_buffer_point_shapefile": "/path/water.shp",
        }
        source = indicator_source(indicator)
        self.assertEqual(source.path, "/path/water.shp")
        self.assertEqual(source.kind, "vector")

    def test_environmental_hazards_raster_field(self):
        indicator = {
            "id": "Fire",
            "analysis_mode": "use_environmental_hazards",
            "environmental_hazards_raster": "/path/fire.tif",
        }
        source = indicator_source(indicator)
        self.assertEqual(source.path, "/path/fire.tif")
        self.assertEqual(source.kind, "raster")

    def test_environmental_hazards_falls_back_to_s2s_vector_field(self):
        """Regression test: a regional-scale, Space2Stats-backed project
        leaves environmental_hazards_raster empty and stores its actual
        configured source (an OGR vector layer, not a raster) under
        environmental_hazards_layer_source instead - confirmed live
        against a real project where every hazard indicator was silently
        dropped from the pack until this fallback was added."""
        indicator = {
            "id": "Fire",
            "analysis_mode": "use_environmental_hazards",
            "environmental_hazards_raster": "",
            "environmental_hazards_source": "s2s",
            "environmental_hazards_layer_source": "/path/s2s_fire.gpkg|layername=s2s_fire",
        }
        source = indicator_source(indicator)
        self.assertEqual(source.path, "/path/s2s_fire.gpkg|layername=s2s_fire")
        self.assertEqual(source.kind, "vector")

    def test_nighttime_lights_falls_back_to_s2s_vector_field(self):
        indicator = {
            "id": "Street_Lights",
            "analysis_mode": "use_nighttime_lights",
            "nighttime_lights_raster": "",
            "nighttime_lights_layer_source": "/path/s2s_ntl.gpkg|layername=s2s_ntl",
        }
        source = indicator_source(indicator)
        self.assertEqual(source.path, "/path/s2s_ntl.gpkg|layername=s2s_ntl")
        self.assertEqual(source.kind, "vector")

    def test_csv_mode_captures_xy_fields(self):
        indicator = {
            "id": "FCV",
            "analysis_mode": "use_csv_to_point_layer",
            "use_csv_to_point_layer_csv_file": "/path/acled.csv",
        }
        source = indicator_source(indicator)
        self.assertEqual(source.kind, "csv")
        self.assertEqual(source.x_field, "longitude")
        self.assertEqual(source.y_field, "latitude")

    def test_manual_number_mode_has_no_source(self):
        indicator = {"id": "Workplace_Index", "analysis_mode": "use_contextual_index_score", "index_score": 95}
        self.assertIsNone(indicator_source(indicator))

    def test_unconfigured_indicator_has_no_source(self):
        indicator = {
            "id": "Active_Transport_Network",
            "analysis_mode": "use_polyline_per_cell",
            "polyline_per_cell_layer_source": "",
            "polyline_per_cell_shapefile": "",
        }
        self.assertIsNone(indicator_source(indicator))

    def test_missing_mode_or_id_has_no_source(self):
        self.assertIsNone(indicator_source({"id": "X"}))
        self.assertIsNone(indicator_source({"analysis_mode": "use_point_per_cell"}))


class TestProjectLevelSources(unittest.TestCase):
    def test_reads_road_network_population_and_masks(self):
        model = {
            "road_network_layer_path": "/path/roads.shp|layername=roads",
            "population_layer_source": "/path/pop.tif",
            "population_source": "raster",
            "point_mask_shapefile": "/path/point_mask.shp",
        }
        sources = project_level_sources(model)
        by_name = {s.layer_name: s for s in sources}
        self.assertEqual(by_name["road_network"].kind, "vector")
        self.assertEqual(by_name["population"].kind, "raster")
        self.assertEqual(by_name["point_mask"].kind, "vector")
        self.assertNotIn("polygon_mask", by_name)
        self.assertNotIn("raster_mask", by_name)
        self.assertNotIn("aggregation_boundary", by_name)

    def test_population_kind_follows_population_source_vector_case(self):
        model = {"population_shapefile": "/path/pop.shp", "population_source": "vector"}
        sources = project_level_sources(model)
        self.assertEqual(sources[0].kind, "vector")

    def test_empty_model_has_no_project_level_sources(self):
        self.assertEqual(project_level_sources({}), [])


class TestIndexScoreValues(unittest.TestCase):
    def _model_with_one_indicator(self, indicator):
        return {"dimensions": [{"factors": [{"indicators": [indicator]}]}]}

    def test_contextual_index_score_is_captured(self):
        model = self._model_with_one_indicator(
            {
                "id": "Workplace_Index",
                "indicator": "Workplace Discrimination",
                "analysis_mode": "use_contextual_index_score",
                "index_score": 95,
            }
        )
        rows = index_score_values(model)
        self.assertEqual(
            rows,
            [
                {
                    "id": "Workplace_Index",
                    "name": "Workplace Discrimination",
                    "analysis_mode": "use_contextual_index_score",
                    "value": 95.0,
                }
            ],
        )

    def test_eplex_uses_its_own_value_field(self):
        model = self._model_with_one_indicator(
            {
                "id": "eplex_score_indicator",
                "indicator": "EPLEX Score",
                "analysis_mode": "use_eplex_score",
                "eplex_score": 0.7,
            }
        )
        rows = index_score_values(model)
        self.assertEqual(rows[0]["value"], 0.7)

    def test_spatial_indicator_is_not_captured(self):
        model = self._model_with_one_indicator(
            {
                "id": "Kindergartens_Location",
                "analysis_mode": "use_multi_buffer_point",
                "multi_buffer_point_layer_source": "/path/points.gpkg",
            }
        )
        self.assertEqual(index_score_values(model), [])

    def test_unconfigured_index_score_indicator_is_omitted(self):
        model = self._model_with_one_indicator(
            {"id": "Digital_Inclusion", "analysis_mode": "use_index_score_with_ookla", "index_score": ""}
        )
        self.assertEqual(index_score_values(model), [])


class TestStudyAreaSources(unittest.TestCase):
    def test_returns_every_layer_unclipped(self):
        sources = study_area_sources(TEST_DATA)
        self.assertEqual({s.layer_name for s in sources}, STUDY_AREA_LAYER_NAMES)
        self.assertTrue(all(s.kind == "vector" for s in sources))
        self.assertTrue(all(s.clip is False for s in sources))
        self.assertTrue(all(s.path.startswith(TEST_DATA) for s in sources))

    def test_missing_study_area_gpkg_returns_empty_list(self):
        self.assertEqual(study_area_sources("/no/such/working/directory"), [])


class TestResultSources(unittest.TestCase):
    def test_captures_every_level_that_has_run(self):
        model = {
            "output_filename": "GeoE3_Score",
            "result_file": "/path/GeoE3_Score_combined.vrt",
            "dimensions": [
                {
                    "id": "contextual",
                    "result_file": "/path/Contextual_score_combined.vrt",
                    "factors": [
                        {"id": "eplex", "result_file": ""},
                        {
                            "id": "workplace_discrimination",
                            "result_file": "/path/WD_output_combined.vrt",
                            "indicators": [
                                {"id": "Workplace_Index", "result_file": "/path/Workplace_Index_combined.vrt"},
                                {"id": "Unrun_Indicator", "result_file": ""},
                            ],
                        },
                    ],
                }
            ],
        }
        sources = result_sources(model)
        by_name = {s.layer_name: s for s in sources}
        self.assertEqual(
            set(by_name),
            {
                "GeoE3_Score_result",
                "dim_contextual_result",
                "fac_workplace_discrimination_result",
                "Workplace_Index_result",
            },
        )
        self.assertTrue(all(s.kind == "raster" and s.clip is False for s in by_name.values()))

    def test_falls_back_to_a_fixed_name_with_no_output_filename(self):
        model = {"result_file": "/path/result.vrt", "dimensions": []}
        sources = result_sources(model)
        self.assertEqual(sources[0].layer_name, "analysis_result")

    def test_empty_model_has_no_results(self):
        self.assertEqual(result_sources({}), [])

    def test_factor_and_same_named_indicator_do_not_collide(self):
        """Regression test: GeoPackage table names are case-insensitive at
        the SQLite level even though gpkg_contents preserves the display
        casing, so a factor ("fcv") and its one child indicator ("FCV")
        sharing the same name in different case would silently collide
        and drop one of the two without this prefixing - confirmed live
        against a real project (Cabo Verde) before this was added:
        "fcv_result" (factor) wrote fine, "FCV_result" (indicator) landed
        in "skipped" with no further explanation."""
        model = {
            "dimensions": [
                {
                    "id": "place_characterization",
                    "factors": [
                        {
                            "id": "fcv",
                            "result_file": "/path/fac_fcv.vrt",
                            "indicators": [{"id": "FCV", "result_file": "/path/ind_fcv.vrt"}],
                        }
                    ],
                }
            ]
        }
        names = {s.layer_name for s in result_sources(model)}
        self.assertEqual(names, {"fac_fcv_result", "FCV_result"})

    def test_captures_extra_top_level_composite_products(self):
        """Regression test: model.json can carry up to 8 extra top-level
        composite products once the analysis_aggregation workflow has
        run (GHSL-masked/by-population rasters, per-zone subnational
        aggregation vectors) - confirmed live on a real regional-scale
        project (StLuciaH3), none of which result_sources() bundled
        before this was added."""
        model = {
            "geoe3_score_ghsl_masked_result_file": "/path/masked.vrt",
            "geoe3_by_population": "/path/by_pop.vrt",
            "geoe3_score_by_population_ghsl_masked_result_file": "/path/by_pop_masked.vrt",
            "opportunities_mask_result_file": "/path/opportunities.vrt",
            "geoe3_score_subnational_aggregation": "/path/sub1.gpkg|layername=sub1",
            "geoe3_score_ghsl_masked_subnational_aggregation": "/path/sub2.gpkg|layername=sub2",
            "geoe3_by_population_subnational_aggregation": "/path/sub3.gpkg|layername=sub3",
            "geoe3_score_by_population_ghsl_masked_subnational_aggregation": "/path/sub4.gpkg|layername=sub4",
        }
        sources = result_sources(model)
        by_name = {s.layer_name: s for s in sources}
        self.assertEqual(len(sources), 8)
        self.assertEqual(by_name["geoe3_score_ghsl_masked_result_file"].kind, "raster")
        self.assertEqual(by_name["geoe3_score_subnational_aggregation"].kind, "vector")
        self.assertTrue(all(s.clip is False for s in sources))


class TestAllSources(unittest.TestCase):
    def test_combines_project_level_and_every_indicator(self):
        model = {
            "road_network_layer_path": "/path/roads.shp|layername=roads",
            "dimensions": [
                {
                    "factors": [
                        {
                            "indicators": [
                                {
                                    "id": "Fire",
                                    "analysis_mode": "use_environmental_hazards",
                                    "environmental_hazards_raster": "/path/fire.tif",
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
            ],
        }
        sources = all_sources(model)
        names = {s.layer_name for s in sources}
        # road_network (project-level) + Fire (indicator), Workplace_Index skipped (no file).
        self.assertEqual(names, {"road_network", "Fire"})

    def test_two_indicators_sharing_one_source_each_get_their_own_layer(self):
        shared_path = "/path/osm_points.gpkg|layername=points"
        model = {
            "dimensions": [
                {
                    "factors": [
                        {
                            "indicators": [
                                {
                                    "id": "Kindergartens_Location",
                                    "analysis_mode": "use_multi_buffer_point",
                                    "multi_buffer_point_layer_source": shared_path,
                                },
                                {
                                    "id": "Primary_School_Location",
                                    "analysis_mode": "use_multi_buffer_point",
                                    "multi_buffer_point_layer_source": shared_path,
                                },
                            ]
                        }
                    ]
                }
            ]
        }
        sources = all_sources(model)
        self.assertEqual(len(sources), 2)
        self.assertEqual({s.layer_name for s in sources}, {"Kindergartens_Location", "Primary_School_Location"})
        self.assertTrue(all(s.path == shared_path for s in sources))


class TestClipAcrossMismatchedCrs(unittest.TestCase):
    """Regression test: a vector source whose CRS differs from the study
    area clip boundary's CRS used to silently clip away every feature,
    with no error - confirmed live against StLuciaH3 and CaboVerde,
    where every OSM-sourced (WGS84) indicator was reduced to 0 features
    against each project's UTM-projected study area. ogr2ogr's own
    "-clipsrc <file> -clipsrclayer <name>" form does not reproject the
    clip geometry on the GDAL version QGIS 3.34 bundles (3.4.1)."""

    def setUp(self):
        self.out_path = os.path.join(TEST_DATA, "_country_pack_crs_test_output.gpkg")
        self.wgs84_points_path = os.path.join(TEST_DATA, "_wgs84_points.gpkg")
        for path in (self.out_path, self.wgs84_points_path):
            if os.path.exists(path):
                os.remove(path)

        # Reproject the existing (UTM 32620) childcare fixture's own
        # points into WGS84 lon/lat, so they're guaranteed to fall
        # inside the study area's clip boundary once correctly
        # reprojected back - not guessed coordinates.
        source_ds = ogr.Open(os.path.join(TEST_DATA, "points", "fake_childcare.gpkg"))
        source_layer = source_ds.GetLayerByName("fake_childcare")
        source_srs = source_layer.GetSpatialRef()
        wgs84_srs = osr.SpatialReference()
        wgs84_srs.ImportFromEPSG(4326)
        source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        wgs84_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(source_srs, wgs84_srs)

        self.expected_feature_count = source_layer.GetFeatureCount()

        driver = ogr.GetDriverByName("GPKG")
        out_ds = driver.CreateDataSource(self.wgs84_points_path)
        out_layer = out_ds.CreateLayer("wgs84_points", srs=wgs84_srs, geom_type=ogr.wkbPoint)
        for feature in source_layer:
            geometry = feature.GetGeometryRef().Clone()
            geometry.Transform(transform)
            out_feature = ogr.Feature(out_layer.GetLayerDefn())
            out_feature.SetGeometry(geometry)
            out_layer.CreateFeature(out_feature)
            out_feature = None
        out_ds = None
        source_ds = None

    def tearDown(self):
        for path in (self.out_path, self.wgs84_points_path):
            if os.path.exists(path):
                os.remove(path)

    def test_clipping_reprojects_the_boundary_to_match_the_source_crs(self):
        model = {
            "dimensions": [
                {
                    "factors": [
                        {
                            "indicators": [
                                {
                                    "id": "Wgs84_Points",
                                    "analysis_mode": "use_point_per_cell",
                                    "point_per_cell_layer_source": (f"{self.wgs84_points_path}|layername=wgs84_points"),
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        build_country_pack(working_directory=TEST_DATA, model=model, output_path=self.out_path)

        ds = ogr.Open(self.out_path)
        layer = ds.GetLayerByName("Wgs84_Points")
        feature_count = layer.GetFeatureCount()
        ds = None

        self.assertGreater(self.expected_feature_count, 0)
        self.assertEqual(feature_count, self.expected_feature_count)


class TestBuildCountryPack(unittest.TestCase):
    """End-to-end against real committed fixture data (not the user's own
    working directory data, which isn't available in CI)."""

    def setUp(self):
        self.out_path = os.path.join(TEST_DATA, "_country_pack_test_output.gpkg")
        if os.path.exists(self.out_path):
            os.remove(self.out_path)

    def tearDown(self):
        if os.path.exists(self.out_path):
            os.remove(self.out_path)

    def _model(self):
        return {
            "dimensions": [
                {
                    "factors": [
                        {
                            "indicators": [
                                {
                                    "id": "Childcare_Location",
                                    "analysis_mode": "use_point_per_cell",
                                    "point_per_cell_layer_source": os.path.join(
                                        TEST_DATA, "points", "fake_childcare.gpkg|layername=fake_childcare"
                                    ),
                                },
                                # A Float32 raster (no downcast needed).
                                {
                                    "id": "Generic_Raster",
                                    "analysis_mode": "use_nighttime_lights",
                                    "nighttime_lights_raster": os.path.join(TEST_DATA, "rasters", "raster.tif"),
                                },
                                # A Float64 raster (needs downcast to Float32 for GPKG).
                                {
                                    "id": "Fire",
                                    "analysis_mode": "use_environmental_hazards",
                                    "environmental_hazards_raster": os.path.join(
                                        TEST_DATA, "rasters", "env_fire_hazard.tif"
                                    ),
                                },
                                # No file configured - should be skipped silently, not fail the pack.
                                {
                                    "id": "Workplace_Index",
                                    "analysis_mode": "use_contextual_index_score",
                                    "index_score": 95,
                                },
                            ]
                        }
                    ]
                }
            ],
        }

    def test_writes_vector_and_raster_sources_into_one_gpkg(self):
        summary = build_country_pack(
            working_directory=TEST_DATA,
            model=self._model(),
            output_path=self.out_path,
        )
        self.assertEqual(
            set(summary["written"]),
            {"Childcare_Location", "Generic_Raster", "Fire", "index_score_values"}
            | STUDY_AREA_LAYER_NAMES
            | ALWAYS_WRITTEN_TABLE_NAMES,
        )
        self.assertEqual(summary["skipped"], [])
        self.assertTrue(os.path.exists(self.out_path))

    def test_a_missing_source_file_is_skipped_not_fatal(self):
        model = self._model()
        model["dimensions"][0]["factors"][0]["indicators"][0]["point_per_cell_layer_source"] = os.path.join(
            TEST_DATA, "points", "does_not_exist.gpkg|layername=x"
        )
        summary = build_country_pack(
            working_directory=TEST_DATA,
            model=model,
            output_path=self.out_path,
        )
        self.assertIn("Childcare_Location", summary["skipped"])
        self.assertIn("Generic_Raster", summary["written"])
        self.assertIn("Fire", summary["written"])

    def test_verification_works_with_no_indicator_level_vector_sources(self):
        """Regression test: ogr.Open() returns None for a GeoPackage that
        has no vector layers at all (confirmed live via the test above,
        before this was fixed) - verification has to open with
        gdal.OF_ALL instead, or a pack with every vector source skipped
        would look like it verified nothing, even though the rasters
        wrote and survived correctly. study_area_sources() means a real
        pack is never truly vector-free once study_area.gpkg exists, but
        this still exercises the same OF_ALL code path with no
        indicator-level vector content to rely on."""
        model = self._model()
        # Drop the one indicator-level vector source, leaving only the
        # two rasters (plus whatever study_area_sources() always adds).
        del model["dimensions"][0]["factors"][0]["indicators"][0]

        summary = build_country_pack(
            working_directory=TEST_DATA,
            model=model,
            output_path=self.out_path,
        )
        expected = (
            {"Generic_Raster", "Fire", "index_score_values"} | STUDY_AREA_LAYER_NAMES | ALWAYS_WRITTEN_TABLE_NAMES
        )
        self.assertEqual(set(summary["written"]), expected)
        self.assertEqual(_actual_table_names(self.out_path), expected)

    def test_vector_then_raster_order_does_not_lose_the_vector_layer(self):
        """Regression test: GDAL's GPKG driver recreates the whole file
        unless told to append, which once silently wiped out an
        already-written vector layer the moment the next write was a
        raster (caught via a real end-to-end run against a real project)."""
        from osgeo import ogr

        summary = build_country_pack(
            working_directory=TEST_DATA,
            model=self._model(),
            output_path=self.out_path,
        )
        self.assertIn("Childcare_Location", summary["written"])

        ds = ogr.Open(self.out_path)
        layer_names = [ds.GetLayerByIndex(i).GetName() for i in range(ds.GetLayerCount())]
        ds = None
        self.assertIn("Childcare_Location", layer_names)

    def test_index_score_table_content_is_readable_back(self):
        from osgeo import ogr

        model = self._model()
        model["dimensions"][0]["factors"][0]["indicators"].append(
            {
                "id": "eplex_score_indicator",
                "indicator": "EPLEX Score",
                "analysis_mode": "use_eplex_score",
                "eplex_score": 0.65,
            }
        )
        build_country_pack(working_directory=TEST_DATA, model=model, output_path=self.out_path)

        ds = ogr.Open(self.out_path)
        layer = ds.GetLayerByName(INDEX_SCORE_TABLE_NAME)
        rows = {f["id"]: f["value"] for f in layer}
        ds = None

        self.assertEqual(rows["Workplace_Index"], 95.0)
        self.assertEqual(rows["eplex_score_indicator"], 0.65)

    def test_project_model_table_round_trips_the_exact_model(self):
        import json

        from osgeo import ogr

        model = self._model()
        build_country_pack(working_directory=TEST_DATA, model=model, output_path=self.out_path)

        ds = ogr.Open(self.out_path)
        layer = ds.GetLayerByName(PROJECT_MODEL_TABLE_NAME)
        feature = next(iter(layer))
        reloaded = json.loads(feature["model_json"])
        ds = None

        self.assertEqual(reloaded, model)


if __name__ == "__main__":
    unittest.main()

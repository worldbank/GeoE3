# -*- coding: utf-8 -*-
"""Unit tests for geest.core.integrity_checks - the ontology of
preconditions a project must satisfy before loading, Run All, Run
Incomplete, or a single-indicator run can go ahead.
"""
import json
import os
import shutil
import sqlite3
import tempfile
import unittest

from geest.core.integrity_checks import (
    check_grid_completeness,
    check_network_layer,
    check_working_directory,
    indicator_needs_road_network,
    is_well_formed_model,
    load_model_json_with_repair,
    save_model_json_atomically,
    study_area_setup_complete,
)


class TestIndicatorNeedsRoadNetwork(unittest.TestCase):
    def test_multi_buffer_point_always_needs_it(self):
        self.assertTrue(indicator_needs_road_network({"analysis_mode": "use_multi_buffer_point"}))

    def test_polyline_per_cell_needs_it_when_no_other_source_is_set(self):
        self.assertTrue(indicator_needs_road_network({"analysis_mode": "use_polyline_per_cell"}))

    def test_polyline_per_cell_does_not_need_it_once_its_own_source_is_set(self):
        self.assertFalse(
            indicator_needs_road_network(
                {
                    "analysis_mode": "use_polyline_per_cell",
                    "polyline_per_cell_shapefile": "/some/roads.shp",
                }
            )
        )

    def test_osm_transport_polyline_per_cell_needs_it_when_no_other_source_is_set(self):
        self.assertTrue(indicator_needs_road_network({"analysis_mode": "use_osm_transport_polyline_per_cell"}))

    def test_unrelated_mode_never_needs_it(self):
        self.assertFalse(indicator_needs_road_network({"analysis_mode": "use_nighttime_lights"}))


class TestCheckWorkingDirectory(unittest.TestCase):
    def test_no_working_directory_is_not_a_problem(self):
        self.assertEqual(check_working_directory(None), [])
        self.assertEqual(check_working_directory(""), [])

    def test_missing_directory_is_a_global_problem(self):
        problems = check_working_directory("/does/not/exist/geoe3-test-dir")

        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].scope, "global")
        self.assertIn("no longer exists", problems[0].message)

    def test_existing_writable_directory_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.assertEqual(check_working_directory(tmp_dir), [])

    def test_unwritable_directory_is_a_global_problem(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chmod(tmp_dir, 0o500)
            try:
                if os.access(tmp_dir, os.W_OK):
                    self.skipTest("running as a user that can write regardless of permissions (e.g. root)")
                problems = check_working_directory(tmp_dir)
            finally:
                os.chmod(tmp_dir, 0o700)

        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].scope, "global")
        self.assertIn("not writable", problems[0].message)


def _make_study_area_gpkg(path, area_polygons, grid_area_names):
    """A minimal sqlite db shaped like study_area.gpkg for grid-completeness tests.

    Args:
        path: Where to create the sqlite file.
        area_polygons: [(area_name, intersects_ghsl)] rows for study_area_polygons.
        grid_area_names: area_name value for each study_area_grid row (None
            for an un-partitioned grid).
    """
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE study_area_polygons (area_name TEXT, intersects_ghsl INTEGER)")
        connection.executemany("INSERT INTO study_area_polygons VALUES (?, ?)", area_polygons)
        connection.execute("CREATE TABLE study_area_grid (area_name TEXT)")
        connection.executemany("INSERT INTO study_area_grid VALUES (?)", [(name,) for name in grid_area_names])
        connection.commit()
    finally:
        connection.close()


class TestStudyAreaSetupComplete(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="geoe3_integrity_setup_complete_test_")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.study_area_dir = os.path.join(self.tmp_dir, "study_area")
        os.makedirs(self.study_area_dir)
        self.gpkg_path = os.path.join(self.study_area_dir, "study_area.gpkg")

    def test_no_working_directory_is_incomplete(self):
        self.assertFalse(study_area_setup_complete(None))
        self.assertFalse(study_area_setup_complete(""))

    def test_no_study_area_gpkg_yet_is_incomplete(self):
        """A model.json copied by the wizard before study area creation ran at all."""
        self.assertFalse(study_area_setup_complete(self.tmp_dir))

    def test_gpkg_with_no_polygons_is_incomplete(self):
        """Study area creation failed partway through - the gpkg exists but is empty."""
        _make_study_area_gpkg(self.gpkg_path, [], grid_area_names=[])

        self.assertFalse(study_area_setup_complete(self.tmp_dir))

    def test_gpkg_with_polygons_is_complete(self):
        _make_study_area_gpkg(self.gpkg_path, [("AreaOne", 1)], grid_area_names=["AreaOne"])

        self.assertTrue(study_area_setup_complete(self.tmp_dir))


class TestCheckGridCompleteness(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="geoe3_integrity_grid_test_")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.study_area_dir = os.path.join(self.tmp_dir, "study_area")
        os.makedirs(self.study_area_dir)
        self.gpkg_path = os.path.join(self.study_area_dir, "study_area.gpkg")

    def test_no_study_area_gpkg_yet_is_not_a_problem(self):
        self.assertEqual(check_grid_completeness(self.tmp_dir), [])

    def test_empty_grid_is_incomplete(self):
        _make_study_area_gpkg(self.gpkg_path, [("AreaOne", 1)], grid_area_names=[])

        problems = check_grid_completeness(self.tmp_dir)

        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].scope, "global")

    def test_every_expected_area_populated_is_complete(self):
        _make_study_area_gpkg(
            self.gpkg_path,
            [("AreaOne", 1), ("AreaTwo", 1)],
            grid_area_names=["AreaOne", "AreaOne", "AreaTwo"],
        )

        self.assertEqual(check_grid_completeness(self.tmp_dir), [])

    def test_a_missing_area_is_incomplete(self):
        _make_study_area_gpkg(
            self.gpkg_path,
            [("AreaOne", 1), ("AreaTwo", 1)],
            grid_area_names=["AreaOne", "AreaOne"],
        )

        problems = check_grid_completeness(self.tmp_dir)

        self.assertEqual(len(problems), 1)
        self.assertIn("1 of 2", problems[0].message)

    def test_ghsl_filtered_out_area_is_not_expected_to_have_cells(self):
        _make_study_area_gpkg(
            self.gpkg_path,
            [("AreaOne", 1), ("GhslExcluded", 0)],
            grid_area_names=["AreaOne"],
        )

        self.assertEqual(check_grid_completeness(self.tmp_dir), [])

    def test_unpartitioned_grid_only_checks_total_cell_count(self):
        _make_study_area_gpkg(
            self.gpkg_path,
            [("AreaOne", 1)],
            grid_area_names=[None, None, None],
        )

        self.assertEqual(check_grid_completeness(self.tmp_dir), [])


class TestCheckNetworkLayer(unittest.TestCase):
    def test_nothing_in_scope_needs_it(self):
        problems = check_network_layer(None, [{"analysis_mode": "use_nighttime_lights"}])

        self.assertEqual(problems, [])

    def test_something_needs_it_and_it_is_unset(self):
        problems = check_network_layer("", [{"analysis_mode": "use_multi_buffer_point"}])

        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].scope, "network")

    def test_something_needs_it_and_the_path_does_not_exist(self):
        problems = check_network_layer("/does/not/exist/roads.gpkg", [{"analysis_mode": "use_multi_buffer_point"}])

        self.assertEqual(len(problems), 1)

    def test_something_needs_it_and_it_is_set_to_an_existing_path(self):
        with tempfile.NamedTemporaryFile(suffix=".gpkg") as tmp_file:
            problems = check_network_layer(
                f"{tmp_file.name}|layername=roads", [{"analysis_mode": "use_multi_buffer_point"}]
            )

        self.assertEqual(problems, [])


class TestIsWellFormedModel(unittest.TestCase):
    def test_a_dict_with_a_dimensions_list_is_well_formed(self):
        self.assertTrue(is_well_formed_model({"dimensions": []}))

    def test_missing_dimensions_key_is_not_well_formed(self):
        self.assertFalse(is_well_formed_model({}))

    def test_dimensions_not_a_list_is_not_well_formed(self):
        self.assertFalse(is_well_formed_model({"dimensions": "oops"}))

    def test_a_non_dict_is_not_well_formed(self):
        self.assertFalse(is_well_formed_model(["oops"]))
        self.assertFalse(is_well_formed_model(None))


class TestModelJsonAtomicSaveAndRepair(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="geoe3_integrity_model_json_test_")
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.model_path = os.path.join(self.tmp_dir, "model.json")
        self.backup_path = self.model_path + ".bak"

    def test_a_fresh_save_can_be_loaded_back(self):
        save_model_json_atomically(self.model_path, {"dimensions": [{"id": "dim1"}]})

        data, problems = load_model_json_with_repair(self.model_path)

        self.assertEqual(data, {"dimensions": [{"id": "dim1"}]})
        self.assertEqual(problems, [])
        self.assertFalse(os.path.exists(self.backup_path), "first save has nothing valid yet to back up")

    def test_a_second_save_backs_up_the_first(self):
        save_model_json_atomically(self.model_path, {"dimensions": [{"id": "v1"}]})
        save_model_json_atomically(self.model_path, {"dimensions": [{"id": "v2"}]})

        with open(self.backup_path, encoding="utf-8") as f:
            backup_data = json.load(f)
        self.assertEqual(backup_data, {"dimensions": [{"id": "v1"}]})

    def test_corrupted_primary_file_is_repaired_from_backup(self):
        save_model_json_atomically(self.model_path, {"dimensions": [{"id": "good"}]})
        save_model_json_atomically(self.model_path, {"dimensions": [{"id": "good2"}]})
        with open(self.model_path, "w", encoding="utf-8") as f:
            f.write("{not valid json")

        data, problems = load_model_json_with_repair(self.model_path)

        self.assertEqual(data, {"dimensions": [{"id": "good"}]})
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].scope, "info")

    def test_corrupted_primary_file_with_no_usable_backup_is_unrecoverable(self):
        with open(self.model_path, "w", encoding="utf-8") as f:
            f.write("{not valid json")

        data, problems = load_model_json_with_repair(self.model_path)

        self.assertIsNone(data)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].scope, "global")

    def test_save_survives_a_pre_existing_corrupt_file(self):
        with open(self.model_path, "w", encoding="utf-8") as f:
            f.write("{not valid json")

        save_model_json_atomically(self.model_path, {"dimensions": [{"id": "new"}]})

        with open(self.model_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data, {"dimensions": [{"id": "new"}]})
        self.assertFalse(os.path.exists(self.backup_path), "a corrupt file must never be copied in as the backup")


if __name__ == "__main__":
    unittest.main()

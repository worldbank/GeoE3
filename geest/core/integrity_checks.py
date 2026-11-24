# -*- coding: utf-8 -*-
"""📦 Integrity check module.

Preconditions a GeoE3 project must satisfy before it can be loaded with
confidence, or before Run All / Run Incomplete / a single indicator can
actually execute. Each check returns zero or more `Problem`s - plain,
human-readable facts about what's wrong, each carrying its own icon and a
`scope` saying which run modes it blocks:

- "global": nothing can run until this is fixed (a broken grid, a
  corrupted model.json, an unwritable working directory) - blocks
  project load confidence, Run All, Run Incomplete, and every
  single-indicator run.
- "network": blocks Run All, Run Incomplete, and any single-indicator
  run whose indicator actually needs the road network layer - never an
  indicator that doesn't.
- "info": never blocks anything - purely informational (e.g. "model.json
  was auto-repaired from a backup, check your indicators").

Callers (TreePanel) decide *when* to run which checks and how to combine
their output with other blocking reasons (e.g. per-indicator
configuredness, which has nothing to do with this module); this module
only knows how to detect each problem and describe it.
"""
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from typing import Optional

from geest.utilities import resources_path


@dataclass(frozen=True)
class Problem:
    """One failed precondition.

    Attributes:
        key: Stable identifier for this kind of problem.
        scope: "global", "network", or "info" - which run modes it blocks.
        message: Human-readable explanation, ready to show as-is.
        icon: Absolute path to an svg under geest/resources/icons/.
    """

    key: str
    scope: str
    message: str
    icon: str


def _icon(name: str) -> str:
    return resources_path("resources", "icons", name)


#: Other attribute keys each network-layer-dependent analysis_mode tries
#: first - road_network_layer_path is only actually read as a fallback
#: once every one of these is empty (see polyline_per_cell_workflow.py /
#: osm_transport_polyline_per_cell_workflow.py /
#: osm_transport_polyline_weighted_per_cell_workflow.py). A mode absent
#: from this dict either doesn't use the road network at all, or (
#: "use_multi_buffer_point") has no fallback keys - it always needs it.
_NETWORK_FALLBACK_KEYS = {
    "use_polyline_per_cell": (
        "polyline_per_cell_shapefile",
        "polyline_per_cell_layer_source",
        "osm_transport_polyline_per_cell_shapefile",
        "osm_transport_polyline_per_cell_layer_source",
    ),
    "use_osm_transport_polyline_per_cell": (
        "osm_transport_polyline_per_cell_shapefile",
        "osm_transport_polyline_per_cell_layer_source",
    ),
}


def indicator_needs_road_network(attributes: dict) -> bool:
    """Whether this indicator's configured analysis_mode actually depends on road_network_layer_path.

    Args:
        attributes: An indicator's attributes() dict.

    Returns:
        True if the workflow this indicator would run actually reads
        road_network_layer_path (as a hard requirement or as the last
        fallback once its own mode-specific keys are empty).
    """
    mode = attributes.get("analysis_mode", "")
    if mode == "use_multi_buffer_point":
        return True
    fallback_keys = _NETWORK_FALLBACK_KEYS.get(mode)
    if fallback_keys is None:
        return False
    return not any(attributes.get(key) for key in fallback_keys)


def check_working_directory(working_directory: Optional[str]) -> list:
    """The analysis folder itself must exist and be writable.

    Args:
        working_directory: The project's working directory, or None/""
            if no project is open yet.

    Returns:
        A single "global" Problem, or [] if the directory is fine (or
        no project is open yet - nothing to check).
    """
    if not working_directory:
        return []
    if not os.path.isdir(working_directory):
        return [
            Problem(
                "working_dir_missing",
                "global",
                f"The analysis folder at {working_directory} no longer exists.",
                _icon("integrity-working-dir.svg"),
            )
        ]
    if not os.access(working_directory, os.W_OK):
        return [
            Problem(
                "working_dir_not_writable",
                "global",
                f"The analysis folder at {working_directory} is not writable.",
                _icon("integrity-working-dir.svg"),
            )
        ]
    return []


def check_grid_completeness(working_directory: Optional[str]) -> list:
    """The analysis grid must cover every study area polygon.

    Only applies once a study area has actually been created - a brand
    new project with no study_area.gpkg yet isn't "incomplete", it just
    hasn't reached that step.

    Args:
        working_directory: The project's working directory.

    Returns:
        A single "global" Problem if the grid is missing/empty, or
        missing cells for one or more study area polygons; [] otherwise.
    """
    if not working_directory:
        return []
    gpkg_path = os.path.join(working_directory, "study_area", "study_area.gpkg")
    if not os.path.exists(gpkg_path):
        return []

    from geest.core.grid_column_utils import grid_cell_count, populated_area_names
    from geest.core.settings import setting

    if grid_cell_count(gpkg_path) <= 0:
        return [
            Problem(
                "grid_incomplete",
                "global",
                "Your study area grid is not complete. Re-run study area creation before analysing.",
                _icon("integrity-grid-incomplete.svg"),
            )
        ]

    try:
        connection = sqlite3.connect(gpkg_path)
        try:
            table_exists = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='study_area_polygons'"
            ).fetchone()
            if table_exists is None:
                return []
            filter_enabled = bool(setting(key="filter_study_areas_by_ghsl", default=True))
            if filter_enabled:
                rows = connection.execute(
                    "SELECT DISTINCT area_name FROM study_area_polygons WHERE intersects_ghsl = 1"
                ).fetchall()
            else:
                rows = connection.execute("SELECT DISTINCT area_name FROM study_area_polygons").fetchall()
            expected_areas = {row[0] for row in rows if row[0] is not None}
        finally:
            connection.close()
    except sqlite3.Error:
        return []

    if not expected_areas:
        return []

    populated = populated_area_names(gpkg_path)
    if populated is None:
        # Not partitioned by area - grid_cell_count() > 0 already proved it exists.
        return []

    missing = expected_areas - populated
    if missing:
        return [
            Problem(
                "grid_incomplete",
                "global",
                "Your study area grid is not complete - "
                f"{len(missing)} of {len(expected_areas)} area(s) have no grid cells.",
                _icon("integrity-grid-incomplete.svg"),
            )
        ]
    return []


def study_area_setup_complete(working_directory: Optional[str]) -> bool:
    """True once study area creation actually produced usable outputs.

    model.json is written early in the Create Project wizard, well before
    the study area GeoPackage/grid is built - so its mere presence can't
    tell a finished project from one where step 1 failed partway through.
    Used to decide whether reopening a project should land on the
    indicator tree (ready to analyse) or back on the Create Project
    wizard (worldbank/GeoE3 #535: a failed study area creation left the
    user on the indicator tree "as if ready to run", with none of the
    previous steps actually set up).

    This is a point-in-time check for a previous session's finished (or
    abandoned) project, not a replacement for CreateProjectPanel's own
    polling readiness check during an in-progress run (which additionally
    guards against reading a GeoPackage mid-write, a race that can't
    happen here).

    Args:
        working_directory: The project's working directory, or None/"".

    Returns:
        True if study_area.gpkg exists and its study_area_polygons table
        has at least one feature.
    """
    if not working_directory:
        return False
    gpkg_path = os.path.join(working_directory, "study_area", "study_area.gpkg")
    if not os.path.exists(gpkg_path):
        return False
    try:
        connection = sqlite3.connect(gpkg_path, timeout=0.2)
        try:
            row = connection.execute("SELECT COUNT(*) FROM study_area_polygons").fetchone()
            return bool(row and row[0] > 0)
        finally:
            connection.close()
    except sqlite3.Error:
        return False


def check_network_layer(road_network_layer_path: Optional[str], indicator_attributes_in_scope) -> list:
    """The road network layer must be set and reachable, if anything in scope actually needs it.

    Args:
        road_network_layer_path: The model's current road_network_layer_path value.
        indicator_attributes_in_scope: Iterable of indicator attributes()
            dicts for every indicator this run would actually touch.

    Returns:
        A single "network" Problem if something in scope needs the road
        network and it isn't usable; [] if nothing in scope needs it, or
        it's already set to an existing path.
    """
    if not any(indicator_needs_road_network(attrs) for attrs in indicator_attributes_in_scope):
        return []
    layer_path = (road_network_layer_path or "").split("|")[0]
    if layer_path and os.path.exists(layer_path):
        return []
    return [
        Problem(
            "network_layer_unset",
            "network",
            "Your network layer is not set. Click here to configure.",
            _icon("integrity-network-layer.svg"),
        )
    ]


def is_well_formed_model(data) -> bool:
    """Minimal, dependency-free structural check for a parsed model.json.

    jsonschema (used by scripts/validate_model_schema.py) is a dev-only
    dependency, deliberately not bundled with the plugin - this is the
    plugin's own, much shallower runtime substitute: just enough to tell
    "this is usable" from "this is not", without needing jsonschema
    installed in the user's QGIS Python environment.

    Args:
        data: Parsed JSON content.

    Returns:
        True if `data` has the one structural property every other
        model.json reader in this codebase already assumes.
    """
    return isinstance(data, dict) and isinstance(data.get("dimensions"), list)


def _read_json_or_none(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load_model_json_with_repair(model_path: str):
    """Load a model.json file, falling back to its backup if the primary file is corrupt.

    A plain write can leave a truncated, unparseable model.json if the
    process dies mid-write (crash, disk full, force-quit) - the one
    realistic cause of "corrupted data model" this project can actually
    hit, now that save_model_json_atomically() makes every *successful*
    save keep a backup of the previous good copy.

    Args:
        model_path: Path to the model.json file to load.

    Returns:
        (data, problems) - data is the loaded dict, or None if neither
        the primary file nor its backup could be used; problems is a
        list of 0 or 1 Problem describing what happened.
    """
    backup_path = model_path + ".bak"

    data = _read_json_or_none(model_path)
    if data is not None and is_well_formed_model(data):
        return data, []

    backup_data = _read_json_or_none(backup_path)
    if backup_data is not None and is_well_formed_model(backup_data):
        return backup_data, [
            Problem(
                "model_json_repaired",
                "info",
                "The data model for this project was corrupted. We restored your last "
                "automatically-saved backup - some indicators may need their configuration checked.",
                _icon("integrity-model-repaired.svg"),
            )
        ]

    return None, [
        Problem(
            "model_json_corrupt",
            "global",
            "The data model for this study area is corrupted and no backup could be used to repair it.",
            _icon("integrity-model-corrupt.svg"),
        )
    ]


def save_model_json_atomically(model_path: str, data: dict) -> None:
    """Write a model.json file via temp-file + rename, keeping a backup of the previous good copy.

    The rename is what actually prevents corruption going forward: a
    crash mid-write now leaves the half-written temp file, never
    model.json itself. The backup is what makes
    load_model_json_with_repair() able to recover from corruption that
    happened before this existed, or from any other cause (a disk
    error, an external tool touching the file, ...).

    Args:
        model_path: Path to the model.json file to save.
        data: The model dict to save (TreeModel.to_json()'s output).
    """
    backup_path = model_path + ".bak"
    if os.path.exists(model_path):
        existing = _read_json_or_none(model_path)
        if existing is not None and is_well_formed_model(existing):
            shutil.copyfile(model_path, backup_path)
    tmp_path = model_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp_path, model_path)

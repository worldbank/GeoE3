# -*- coding: utf-8 -*-
"""Country Pack Import Task.

This module contains the QgsTask for reconstructing a full GeoE3
project from a country pack GeoPackage in the background.
"""

import json
import os
from typing import Dict, List
from urllib.parse import quote

from qgis.core import Qgis, QgsProject, QgsRasterLayer, QgsTask, QgsVectorLayer

from geest.core.country_pack import all_sources, result_sources, study_area_sources
from geest.core.country_pack_import import (
    _indicator_import_targets,
    _project_level_import_targets,
    import_country_pack,
    result_layer_roles,
    result_qml_path,
    sync_layer_metadata_fields,
)
from geest.utilities import log_message


class ImportCountryPackTask(QgsTask):
    """Background task for reconstructing a project from a country pack."""

    def __init__(self, pack_path: str, working_directory: str):
        """Initialize the task.

        Args:
            pack_path: Path to the country pack GeoPackage to import.
            working_directory: An empty directory to reconstruct the
                project into.
        """
        super().__init__("Importing Country Pack", QgsTask.CanCancel)
        self.pack_path = pack_path
        self.working_directory = working_directory
        self.exception = None
        self.summary: Dict[str, List[str]] = {"imported": [], "skipped": []}

    def run(self) -> bool:
        """Reconstruct the project in the background thread.

        Returns:
            True if the project was reconstructed (even if some tables
            were skipped - see self.summary["skipped"]), False on a
            hard failure (e.g. the working directory already has a
            project, or the pack isn't a country pack).
        """
        try:
            log_message(f"Starting country pack import from '{self.pack_path}'...", tag="GeoE3", level=Qgis.Info)

            def _report_progress(done: int, total: int, table_name: str) -> None:
                if total:
                    self.setProgress(int(100 * done / total))
                if table_name:
                    log_message(f"Country pack import: extracting '{table_name}'...", tag="GeoE3")

            self.summary = import_country_pack(
                pack_path=self.pack_path,
                working_directory=self.working_directory,
                progress_callback=_report_progress,
            )

            log_message(
                f"Country pack imported: {len(self.summary['imported'])} tables reconstructed, "
                f"{len(self.summary['skipped'])} skipped -> {self.working_directory}",
                tag="GeoE3",
                level=Qgis.Info,
            )
            return True

        except Exception as e:
            self.exception = e
            log_message(f"Error importing country pack: {e}", tag="GeoE3", level=Qgis.Critical)
            return False

    def finished(self, result: bool) -> None:
        """Called when the task finishes (main thread).

        Args:
            result: True if the task succeeded, False otherwise.
        """
        if result:
            log_message(
                f"Country pack import ready: {self.working_directory} "
                f"({len(self.summary['imported'])} tables, {len(self.summary['skipped'])} skipped)",
                tag="GeoE3",
                level=Qgis.Info,
            )
            self._load_layers_into_project()
        else:
            log_message("Country pack import failed.", tag="GeoE3", level=Qgis.Critical)

    def _load_layers_into_project(self) -> None:
        """Add every layer the import reconstructed into the current QGIS project.

        Runs from finished(), always on the main thread - constructing
        QgsVectorLayer/QgsRasterLayer and touching QgsProject.instance()
        here is safe for exactly that reason (see country_pack.py's
        module docstring on why run()'s worker thread never may).

        Re-derived from the just-written (already path-rewritten)
        model.json via the same all_sources()/result_sources()/
        study_area_sources() functions the export side uses, rather
        than tracked separately during the import loop - every path
        in it already points inside self.working_directory, so this
        can't pull in anything from outside it.

        Layers land in three top-level, mutually exclusive groups (one
        visible layer at a time within each - the same convention
        geest/core/utilities.py's add_to_map() uses for a live run's own
        "GeoE3" group) rather than flat in the legend: "Study Area"
        (study_area_sources()), "GeoE3 Results" (result_sources()), and
        one named after the destination folder for every configured
        input (all_sources()) - a bundle can carry 50+ layers, and
        without grouping the legend would be an unreadable flat list.

        Once every layer is added, also saves the live QgsProject (still
        otherwise blank at this point - see blank_project_guard.py) as a
        new .qgz inside self.working_directory, and records it as
        model.json's qgis_project_path - import_country_pack() cleared
        that field earlier since the exporting machine's own .qgz is
        meaningless here (see its docstring), so without this the user
        would land on a project with everything loaded but nothing to
        reopen it from later.

        For every indicator/project-level source, also points its
        "already-loaded-layer" companion fields (_layer_id etc - see
        sync_layer_metadata_fields()) at the layer just added, and
        re-saves model.json with those updates before the Tree panel
        re-reads it - otherwise every data source widget would show no
        selection despite the file being correctly referenced.
        """
        model_path = os.path.join(self.working_directory, "model.json")
        try:
            with open(model_path, "r", encoding="utf-8") as f:
                model = json.load(f)
        except Exception as e:
            log_message(f"Could not reload model.json to populate the map: {e}", tag="GeoE3", level=Qgis.Warning)
            return

        indicator_targets = _indicator_import_targets(model)
        project_targets = _project_level_import_targets(model)
        result_roles = result_layer_roles(model)

        # Names it after the destination folder rather than the country
        # (unlike build_country_pack()'s *_geoe3.gpkg) - the admin0 name
        # lives in study_area/boundaries_dissolved.gpkg, a file the
        # export/import round trip doesn't preserve (study area layers
        # all land in one study_area.gpkg here - see
        # _extract_vector_into()'s callers above), so the folder name is
        # the only stable label available post-import. Reused below for
        # the input layers' own group name.
        project_name = os.path.basename(os.path.normpath(self.working_directory)) or "project"

        project = QgsProject.instance()
        root = project.layerTreeRoot()

        def _group(name: str, index: int):
            group = root.findGroup(name)
            if group is None:
                group = root.insertGroup(index, name)
                group.setIsMutuallyExclusive(True)
            return group

        grouped_sources = [
            (_group("Study Area", 0), study_area_sources(self.working_directory)),
            (_group("GeoE3 Results", 1), result_sources(model)),
            (_group(project_name, 2), all_sources(model)),
        ]

        added = 0
        total = sum(len(sources) for _, sources in grouped_sources)
        metadata_changed = False
        for group, sources in grouped_sources:
            for source in sources:
                try:
                    if source.kind == "raster":
                        layer = QgsRasterLayer(source.path, source.layer_name)
                    elif source.kind == "csv":
                        # file:// URIs need an absolute path - source.path is
                        # normally already absolute (working_directory comes
                        # from a file picker), but abspath() here is cheap
                        # insurance against a malformed URI if it isn't.
                        uri = (
                            f"file:///{quote(os.path.abspath(source.path))}?type=csv&delimiter=,"
                            f"&xField={source.x_field}&yField={source.y_field}&crs=EPSG:4326"
                        )
                        layer = QgsVectorLayer(uri, source.layer_name, "delimitedtext")
                    else:
                        layer = QgsVectorLayer(source.path, source.layer_name, "ogr")
                    if not layer.isValid():
                        log_message(f"Skipping invalid layer '{source.layer_name}' ({source.path})", tag="GeoE3")
                        continue

                    # Already-computed results have no companion .qml next
                    # to the extracted copy (unlike a normal run, which
                    # writes one alongside the .vrt at computation time) -
                    # apply the same style the rest of the app would have,
                    # rather than leaving QGIS's arbitrary auto-styling.
                    qml_path = result_qml_path(source.layer_name, result_roles)
                    if qml_path and os.path.exists(qml_path):
                        success, message = layer.loadNamedStyle(qml_path)
                        if not success:
                            log_message(f"Could not style '{source.layer_name}': {message}", tag="GeoE3")

                    project.addMapLayer(layer, False)
                    group.addLayer(layer)
                    added += 1

                    if source.layer_name in indicator_targets:
                        node, field_name, _kind = indicator_targets[source.layer_name]
                        sync_layer_metadata_fields(node, field_name, layer)
                        metadata_changed = True
                    elif source.layer_name in project_targets:
                        field_name, _kind = project_targets[source.layer_name]
                        sync_layer_metadata_fields(model, field_name, layer)
                        metadata_changed = True
                except Exception as e:
                    log_message(f"Could not add layer '{source.layer_name}': {e}", tag="GeoE3", level=Qgis.Warning)

        log_message(f"Added {added}/{total} layers to the QGIS project.", tag="GeoE3", level=Qgis.Info)

        if added:
            project_path = os.path.join(self.working_directory, f"{project_name}.qgz")
            if project.write(project_path):
                log_message(f"Saved QGIS project to '{project_path}'.", tag="GeoE3", level=Qgis.Info)
                model["qgis_project_path"] = project_path
                metadata_changed = True
            else:
                log_message(f"Could not save QGIS project to '{project_path}'.", tag="GeoE3", level=Qgis.Warning)

        if metadata_changed:
            try:
                with open(model_path, "w", encoding="utf-8") as f:
                    json.dump(model, f, indent=2)
            except Exception as e:
                log_message(f"Could not save layer metadata to model.json: {e}", tag="GeoE3", level=Qgis.Warning)

    def cancel(self) -> None:
        """Called when the task is cancelled."""
        log_message("Country pack import cancelled.", tag="GeoE3", level=Qgis.Warning)
        super().cancel()

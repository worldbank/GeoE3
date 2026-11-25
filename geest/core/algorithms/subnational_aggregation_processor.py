# -*- coding: utf-8 -*-
"""📦 Subnational Aggregation Processor module.

This module contains functionality for subnational aggregation processor.
"""

import os
import shutil
import sqlite3
import traceback
from typing import Optional

from osgeo import ogr
from qgis import processing
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProject,
    QgsSpatialIndex,
    QgsTask,
    QgsVectorLayer,
)

from geest.core import JsonTreeItem
from geest.core.constants import is_unconfigured_analysis_mode
from geest.core.grid_column_utils import _quote_sql_identifier
from geest.core.settings import setting
from geest.utilities import log_message, resources_path


class SubnationalAggregationProcessingTask(QgsTask):
    """
    A QgsTask subclass for calculating GeoE3 x Population Score and or GeoE3 Score per aggregation area.

    It iterates over subnational boundaries, calculates the majoriy GeoE3 Score or GeoE3 x Population Score
    into a geopackage with the same polygons as original subnational boundaries but new attributes for
    the majority scores and applies a QML style.

    The subnational boundaries will NOT be split bu the study area polygons, so
    containment is not guaranteed between study area polygons and the subnational boundary polygons.
    Because of this, we will use the VRT combined outputs for the GeoE3 Score and GeoE3 x Population Score
    inputs.

    It will write 4 columns to the output gpkg:

    fid - generic incrementing id for each subnational area
    name - subnational area name
    geoe3_score - majority GeoE3 Score for that subnational area
    geoe3_pop_score - majority geoe3 x population score for that subnational area

    The GeoE3 Score can be one of 5 classes:

    | Range  | Description               | Color      |
    |--------|---------------------------|------------|
    | 0 - 1  | Very Low Enablement       | ![#FF0000](#) `#FF0000` |
    | 1 - 2  | Low Enablement            | ![#FFA500](#) `#FFA500` |
    | 2 - 3  | Moderately Enabling       | ![#FFFF00](#) `#FFFF00` |
    | 3 - 4  | Enabling                  | ![#90EE90](#) `#90EE90` |
    | 4 - 5  | Highly Enabling           | ![#0000FF](#) `#0000FF` |

    The GeoE3 x Population Score can be one of 15 classes:

    | Color      | Description                                 |
    |------------|---------------------------------------------|
    | ![#FF0000](#) `#FF0000` | Very low enablement, low population       |
    | ![#FF0000](#) `#FF0000` | Very low enablement, medium population    |
    | ![#FF0000](#) `#FF0000` | Very low enablement, high population      |
    | ![#FFA500](#) `#FFA500` | Low enablement, low population            |
    | ![#FFA500](#) `#FFA500` | Low enablement, medium population         |
    | ![#FFA500](#) `#FFA500` | Low enablement, high population           |
    | ![#FFFF00](#) `#FFFF00` | Moderately enabling, low population       |
    | ![#FFFF00](#) `#FFFF00` | Moderately enabling, medium population    |
    | ![#FFFF00](#) `#FFFF00` | Moderately enabling, high population      |
    | ![#90EE90](#) `#90EE90` | Enabling, low population                  |
    | ![#90EE90](#) `#90EE90` | Enabling, medium population               |
    | ![#90EE90](#) `#90EE90` | Enabling, high population                 |
    | ![#0000FF](#) `#0000FF` | Highly enabling, low population           |
    | ![#0000FF](#) `#0000FF` | Highly enabling, medium population        |
    | ![#0000FF](#) `#0000FF` | Highly enabling, high population          |

    See the geoe3_by_population_score_processor.py module for more details on how this is computed.

    📒 The majority score for each subnational area is calculated by counting the
       number of pixels in each GeoE3 Score and GeoE3 x Population Score class as per the
       above tables. Then majority pixel count is then allocated to the aggregate area.
       In the unlikely event of there being two or more classes with an equal pixel count,
       the highest enablement and population class is assigned.

    See zonalstatisticsfb algorithm for more details on how the majority score is calculated.
    https://qgis.org/pyqgis/3.34/analysis/QgsZonalStatistics.html#qgis.analysis.QgsZonalStatistics.Majority


    Args:
        study_area_gpkg_path (str): Path to the study area geopackage. Used to determine the CRS.
        working_directory (str): Parent directory to save the output agregated data. Outputs will
            be saved in a subdirectory called "subnational_aggregates".
        target_crs (Optional[QgsCoordinateReferenceSystem]): CRS for the output rasters.
        force_clear (bool): Flag to force clearing of all outputs before processing.

    Note: item.attribute("aggregation_layer_source") must be set for the analysis item.
    """

    def __init__(
        self,
        item: JsonTreeItem,
        study_area_gpkg_path: str,
        working_directory: str,
        target_crs: Optional[QgsCoordinateReferenceSystem] = None,
        force_clear: bool = False,
    ):
        super().__init__("Subnational Aggregation Processor", QgsTask.CanCancel)
        self.item = item  # should be an item with role=analysis

        self.study_area_gpkg_path = study_area_gpkg_path

        self.aggregation_areas_path = item.attribute("aggregation_layer_source")

        self.aggregation_layer: QgsVectorLayer = QgsVectorLayer(
            self.aggregation_areas_path,
            "aggregation_areas",
            "ogr",
        )
        if not self.aggregation_layer.isValid():
            raise Exception(f"Invalid aggregation areas layer:\n{self.aggregation_areas_path}")  # noqa E231

        self.output_dir = os.path.join(working_directory, "subnational_aggregation")
        os.makedirs(self.output_dir, exist_ok=True)

        # This folder should already exist from the aggregation analysis and population raster processing
        self.geoe3_score_folder = os.path.join(working_directory, "geoe3_score")

        if not os.path.exists(self.geoe3_score_folder):
            raise Exception(
                f"GeoE3 folder not found.\n{self.geoe3_score_folder}\nPlease run GeoE3 raster processing first."
            )
        # This folder is optional  - user needs to have configured population layer in analysis properties dialog
        self.geoe3_by_population_folder = os.path.join(working_directory, "geoe3_by_population_score")

        if not os.path.exists(self.geoe3_by_population_folder):
            log_message(
                f"GeoE3 folder not found.\n{self.geoe3_by_population_folder}\nPlease run GeoE3 raster processing first."
            )
            self.geoe3_by_population_folder = None
        # These two folders are optional - will only be set if user configured mask for
        # job opportunities in analysis properties dialog
        self.geoe3_score_ghsl_masked_folder = os.path.join(working_directory, "geoe3_score_ghsl_masked")

        if not os.path.exists(self.geoe3_score_ghsl_masked_folder):
            log_message(
                f"GeoE3 GHSL masked folder not found.\n{self.geoe3_score_ghsl_masked_folder}\nPlease run GeoE3 raster processing first."
            )
            self.geoe3_score_ghsl_masked_folder = None

        self.geoe3_score_by_population_ghsl_masked_folder = os.path.join(
            working_directory, "geoe3_score_by_population_ghsl_masked"
        )

        if not os.path.exists(self.geoe3_score_by_population_ghsl_masked_folder):
            log_message(
                f"GeoE3 by population GHSL masked folder not found.\n{self.geoe3_score_by_population_ghsl_masked_folder}\nPlease run GeoE3 raster processing first."
            )
            self.geoe3_score_by_population_ghsl_masked_folder = None

        # Set by fix_geometries() - the best-guess zone name field
        # detected on the aggregation boundary, if any.
        self.zone_name_field: Optional[str] = None

        self.force_clear = force_clear
        if self.force_clear and os.path.exists(self.output_dir):
            for file in os.listdir(self.output_dir):
                os.remove(os.path.join(self.output_dir, file))

        self.target_crs = target_crs
        if not self.target_crs:
            layer: QgsVectorLayer = QgsVectorLayer(
                f"{self.study_area_gpkg_path}|layername=study_area_clip_polygons",
                "study_area_clip_polygons",
                "ogr",
            )
            self.target_crs = layer.crs()
            log_message(f"Target CRS not set. Using CRS from study area clip polygon: {self.target_crs.authid()}")
            log_message(f"{self.study_area_gpkg_path}|ayername=study_area_clip_polygon")
            del layer

        log_message("Initialized GeoE3 Subnational Area Aggregation Processing Task")

    def run(self) -> bool:
        """
        Executes the GeoE3 Subnational Area Aggregation Processing Task calculation task.

        Returns:
            bool: True if the task completed successfully, False otherwise.
        """
        try:
            cleaned_aggregation_layer = self.fix_geometries()
            if self.geoe3_score_folder:
                log_message("Calculating GeoE3 Score Aggregation")
                layer_name = "geoe3_score_subnational_aggregation"
                raster_layer_path = os.path.join(self.geoe3_score_folder, "GeoE3_Score_combined.vrt")
                output = self.aggregate(
                    cleaned_aggregation_layer,
                    raster_layer_path,
                    layer_name,
                )
                self.apply_qml_style(
                    source_qml=resources_path("resources", "qml", "geoe3_score_vector.qml"),
                    qml_path=os.path.join(self.output_dir, f"{layer_name}.qml"),
                )
                self.item.setAttribute(f"{layer_name}", f"{output}|layername={layer_name}")
                if bool(setting(key="include_subnational_score_matrix", default=False)):
                    try:
                        self.aggregate_factor_dimension_totals(cleaned_aggregation_layer)
                    except Exception as e:
                        # A failure here must not take down the 4 well-established
                        # products above, which have already been written out
                        # successfully by this point.
                        log_message(f"Subnational factor/dimension averages failed: {e}", tag="GeoE3")
                        log_message(traceback.format_exc(), tag="GeoE3")
            if self.geoe3_by_population_folder:
                log_message("Calculating GeoE3 x Population Score Aggregation")
                layer_name = "geoe3_by_population_subnational_aggregation"
                raster_layer_path = os.path.join(self.geoe3_by_population_folder, "geoe3_by_population_score.vrt")
                output = self.aggregate(
                    cleaned_aggregation_layer,
                    raster_layer_path,
                    layer_name,
                )
                self.apply_qml_style(
                    source_qml=resources_path("resources", "qml", "geoe3_by_population_vector_score.qml"),
                    qml_path=os.path.join(self.output_dir, f"{layer_name}.qml"),
                )
                self.item.setAttribute(f"{layer_name}", f"{output}|layername={layer_name}")
            if self.geoe3_score_ghsl_masked_folder:
                log_message("Calculating GeoE3 Score GHSL Masked Aggregation")
                layer_name = "geoe3_score_ghsl_masked_subnational_aggregation"
                raster_layer_path = os.path.join(
                    self.geoe3_score_ghsl_masked_folder,
                    "geoe3_score_ghsl_masked.vrt",
                )
                output = self.aggregate(
                    cleaned_aggregation_layer,
                    raster_layer_path,
                    layer_name,
                )
                self.apply_qml_style(
                    source_qml=resources_path("resources", "qml", "geoe3_score_vector.qml"),
                    qml_path=os.path.join(self.output_dir, f"{layer_name}.qml"),
                )
                self.item.setAttribute(f"{layer_name}", f"{output}|layername={layer_name}")
            if self.geoe3_score_by_population_ghsl_masked_folder:
                log_message("Calculating GeoE3 Score by Population GHSL Masked Aggregation")
                layer_name = "geoe3_score_by_population_ghsl_masked_subnational_aggregation"
                raster_layer_path = os.path.join(
                    self.geoe3_score_by_population_ghsl_masked_folder,
                    "geoe3_score_by_population_ghsl_masked.vrt",
                )
                output = self.aggregate(
                    cleaned_aggregation_layer,
                    raster_layer_path,
                    layer_name,
                )
                self.apply_qml_style(
                    source_qml=resources_path("resources", "qml", "geoe3_by_population_vector_score.qml"),
                    qml_path=os.path.join(self.output_dir, f"{layer_name}.qml"),
                )
                self.item.setAttribute(f"{layer_name}", f"{output}|layername={layer_name}")
            log_message(self.item.attributesAsMarkdown())
            return True
        except Exception as e:
            log_message(f"Task failed: {e}")
            log_message(traceback.format_exc())
            return False

    def fix_geometries(self) -> QgsVectorLayer:
        """
        Fix geometries in the aggregation layer.

        Also detects and retains a best-guess zone name field (see
        _detect_name_field()) alongside "fid" - the aggregation boundary
        has no explicit "pick the name column" step the way the admin0
        dissolve field does, so every other attribute is otherwise
        dropped before zonal statistics run.

        Returns:
            QgsVectorLayer: The layer with fixed geometries and retained
            fid/name fields.
        """
        self.zone_name_field = self._detect_name_field(self.aggregation_layer)
        retained_fields = ["fid"] if self.zone_name_field is None else ["fid", self.zone_name_field]

        params = {
            "INPUT": self.aggregation_layer,
            "METHOD": 1,  # Structur method
            "OUTPUT": "TEMPORARY_OUTPUT",
        }
        output = processing.run("native:fixgeometries", params)["OUTPUT"]
        # Also drop all columns except fid/the detected name field.
        params = {"INPUT": output, "FIELDS": retained_fields, "OUTPUT": "TEMPORARY_OUTPUT"}
        output = processing.run("native:retainfields", params)["OUTPUT"]

        return output

    @staticmethod
    def _detect_name_field(layer: QgsVectorLayer) -> Optional[str]:
        """Best-guess the aggregation boundary's own name field: the
        first String-type field. There is no explicit "pick the name
        column" step for this layer (unlike the admin0 dissolve field,
        chosen during project setup) - mirrors
        AnalysisReport._admin0_name()'s identical heuristic.
        """
        for field in layer.fields():
            if field.typeName() == "String":
                return field.name()
        return None

    def aggregate(self, aggregation_layer: QgsVectorLayer, raster_layer_path: str, name: str) -> str:
        """
        Use aggregation vector to calculate the majority GeoE3 Score and GeoE3 x Population Score for each valid polygon.

        Args:
            aggregation_layer (QgsVectorLayer): The aggregation layer with fixed geometries.
            raster_layer_path (str): Path to the raster layer to aggregate.
            name (str): Name for the output layer.

        Returns:
            str: Path to the output geopackage file.
        """
        output = os.path.join(self.output_dir, f"{name}.gpkg")
        params = {
            "INPUT": aggregation_layer,
            "INPUT_RASTER": raster_layer_path,
            "RASTER_BAND": 1,
            "COLUMN_PREFIX": "_",
            "STATISTICS": [9],  # Majority
            "OUTPUT": output,
        }
        processing.run("native:zonalstatisticsfb", params)
        return output

    def aggregate_factor_dimension_totals(self, cleaned_aggregation_layer: QgsVectorLayer) -> None:
        """Add one column per used factor, used dimension, and the
        overall GeoE3 total score to the plain GeoE3 score subnational
        aggregation GeoPackage - the AVERAGE of every study_area_grid
        cell that spatially intersects each subnational zone, not the
        majority-class raster statistic aggregate() uses for the four
        existing products. Those classify a continuous score into
        discrete enablement classes for a map legend; factor/dimension/
        total scores are better served by a true average over the
        cells inside each zone.

        Idempotent and legacy-safe: only columns not already present
        are computed, so re-running the full analysis on a project
        whose subnational_aggregation file predates this feature
        backfills just the missing columns rather than redoing
        everything (or being silently skipped forever).
        """
        output = os.path.join(self.output_dir, "geoe3_score_subnational_aggregation.gpkg")
        if not os.path.exists(output):
            log_message(
                "geoe3_score_subnational_aggregation.gpkg not found - skipping factor/dimension averages.",
                tag="GeoE3",
            )
            return

        table_name = "geoe3_score_subnational_aggregation"
        existing_columns = self._existing_sqlite_columns(output, table_name)
        name_column_needed = self.zone_name_field is not None and "zone_name" not in existing_columns

        columns = self._factor_dimension_total_columns()
        missing_columns = [(name, col) for name, col in columns if f"avg_{col}" not in existing_columns]
        if not missing_columns and not name_column_needed:
            log_message("Subnational factor/dimension averages already present - nothing to backfill.", tag="GeoE3")
            return

        log_message(
            f"Computing {len(missing_columns)} subnational factor/dimension/total average column(s) "
            f"across {cleaned_aggregation_layer.featureCount()} zones...",
            tag="GeoE3",
        )
        zone_to_cells = self._assign_grid_cells_to_zones(cleaned_aggregation_layer)
        if not zone_to_cells:
            log_message(
                "No grid cells matched any subnational zone - skipping factor/dimension averages.",
                tag="GeoE3",
            )
            return

        zone_names = None
        if name_column_needed:
            zone_names = {
                feature.id(): feature.attribute(self.zone_name_field)
                for feature in cleaned_aggregation_layer.getFeatures()
            }

        averages_by_zone = {}
        if missing_columns:
            averages_by_zone = self._average_grid_columns_per_zone(zone_to_cells, [col for _, col in missing_columns])

        self._write_zone_results(output, table_name, missing_columns, averages_by_zone, zone_names)
        log_message("Subnational factor/dimension/total averages computed.", tag="GeoE3")

    def _factor_dimension_total_columns(self) -> list:
        """(display_name, grid_column_name) for every used dimension,
        every used factor, and the overall GeoE3 total score - the
        exact set of columns the report's subnational score table
        shows, read from the live in-memory item tree rather than
        model.json (which may not yet reflect this run's results -
        model.json is only saved back to disk after this task returns).
        """
        columns = []
        for dimension in self.item.childItems:
            if not dimension.isDimension():
                continue
            used_factors = [
                factor
                for factor in dimension.childItems
                if factor.isFactor()
                and any(
                    not is_unconfigured_analysis_mode(indicator.attribute("analysis_mode", ""))
                    for indicator in factor.childItems
                )
            ]
            if not used_factors:
                continue
            columns.append((dimension.attribute("name", ""), dimension.gridColumnName()))
            for factor in used_factors:
                columns.append((factor.attribute("name", ""), factor.gridColumnName()))
        columns.append(("GeoE3 Score", "geoe3"))
        return columns

    def _assign_grid_cells_to_zones(self, cleaned_aggregation_layer: QgsVectorLayer) -> dict:
        """Spatially match every study_area_grid cell to the
        subnational zone it falls within, via a spatial index over the
        grid (built once) plus a precise geometry test per zone -
        mirrors the established pattern in
        features_per_cell_processor.select_grid_cells_and_count_features().
        The aggregation boundary and the grid are commonly in different
        CRSes (confirmed in the field: EPSG:32632 vs EPSG:32636 for one
        real project) - explicitly reprojected here since neither
        QgsSpatialIndex nor a manual geometry intersects() test does
        this automatically.

        Returns:
            {zone_feature_id: [grid_cell_fid, ...], ...} - the grid
            cell fid values are study_area_grid's own GeoPackage fid,
            matching what the report later reads via plain SQL.
        """
        grid_layer = QgsVectorLayer(
            f"{self.study_area_gpkg_path}|layername=study_area_grid",
            "study_area_grid",
            "ogr",
        )
        if not grid_layer.isValid():
            log_message("Could not load study_area_grid for subnational averages.", tag="GeoE3")
            return {}

        transform = None
        if cleaned_aggregation_layer.crs() != grid_layer.crs():
            transform = QgsCoordinateTransform(cleaned_aggregation_layer.crs(), grid_layer.crs(), QgsProject.instance())

        grid_index = QgsSpatialIndex(grid_layer.getFeatures())

        zone_count = cleaned_aggregation_layer.featureCount()
        log_interval = max(1, zone_count // 10)
        zone_to_cells = {}
        for counter, zone in enumerate(cleaned_aggregation_layer.getFeatures(), start=1):
            zone_geom = QgsGeometry(zone.geometry())
            if not zone_geom.isEmpty():
                if transform is not None:
                    zone_geom.transform(transform)
                candidate_ids = grid_index.intersects(zone_geom.boundingBox())
                if candidate_ids:
                    prepared_geom = QgsGeometry.createGeometryEngine(zone_geom.constGet())
                    prepared_geom.prepareGeometry()
                    request = QgsFeatureRequest().setFilterFids(candidate_ids).setSubsetOfAttributes([])
                    matching_fids = [
                        grid_feature.id()
                        for grid_feature in grid_layer.getFeatures(request)
                        if prepared_geom.intersects(grid_feature.geometry().constGet())
                    ]
                    if matching_fids:
                        zone_to_cells[zone.id()] = matching_fids

            if counter % log_interval == 0 or counter == zone_count:
                percent = counter / zone_count * 100.0
                log_message(f"Subnational averages: matched {counter}/{zone_count} zones ({percent:.0f}%)", tag="GeoE3")
                self.setProgress(percent * 0.8)  # the SQL averaging step below gets the rest

        return zone_to_cells

    def _average_grid_columns_per_zone(self, zone_to_cells: dict, columns: list) -> dict:
        """SQL AVG() of each requested study_area_grid column, grouped
        by zone - computed in ONE pass via a temporary cell->zone
        mapping table, not one query per zone (there can be thousands).

        0/NULL is excluded per column before averaging - the same
        "excluded area" convention every study_area_grid read in this
        codebase follows (see AnalysisReport._read_grid_column_values()).

        A single grid cell commonly intersects MORE THAN ONE zone (the
        cell size is configurable per analysis, not fixed, but even at
        a modest size a cell routinely spans several small
        administrative zones - confirmed against real data: ~22% of
        cell/zone matches were shared by more than one zone for
        Tunisia's 1km-grid ADM4 boundary), so
        the mapping table deliberately has no unique constraint on
        fid - a cell contributes to the average of every zone it
        intersects, not just one.

        Returns:
            {zone_feature_id: {grid_column_name: average_value, ...}, ...}
        """
        try:
            quoted_columns = [_quote_sql_identifier(c) for c in columns]
        except ValueError as error:
            log_message(f"Refusing to average grid columns: {error}", tag="GeoE3")
            return {}

        connection = sqlite3.connect(self.study_area_gpkg_path)
        try:
            connection.execute("CREATE TEMP TABLE _zone_cell_map (fid INTEGER, zone_fid INTEGER)")
            rows = [(cell_fid, zone_fid) for zone_fid, cell_fids in zone_to_cells.items() for cell_fid in cell_fids]
            connection.executemany("INSERT INTO _zone_cell_map (fid, zone_fid) VALUES (?, ?)", rows)
            connection.execute("CREATE INDEX _zone_cell_map_fid_idx ON _zone_cell_map (fid)")

            select_clauses = ", ".join(f"AVG(CASE WHEN g.{c} > 0 THEN g.{c} END) AS {c}" for c in quoted_columns)
            query = (
                f"SELECT m.zone_fid, {select_clauses} "  # nosec B608
                "FROM _zone_cell_map m JOIN study_area_grid g ON g.fid = m.fid "
                "GROUP BY m.zone_fid"
            )
            self.setProgress(90.0)
            results = connection.execute(query).fetchall()
        finally:
            connection.execute("DROP TABLE IF EXISTS _zone_cell_map")
            connection.close()

        return {row[0]: dict(zip(columns, row[1:])) for row in results}

    @staticmethod
    def _write_zone_results(
        gpkg_path: str,
        table_name: str,
        missing_columns: list,
        averages_by_zone: dict,
        zone_names: Optional[dict],
    ) -> None:
        """Add any missing avg_<column>/zone_name columns to the
        aggregates GeoPackage and populate them, keyed by each zone's
        own fid - the same fid value the report reads back.

        This GeoPackage carries RTree spatial-index triggers that fire
        on ANY UPDATE to the table (not just the geometry column) and
        reference SpatiaLite functions (e.g. ST_IsEmpty) in their WHEN
        clause. A plain Python sqlite3 connection doesn't have those
        registered - loading mod_spatialite into it by bare name worked
        against the qgis/qgis Docker image this was first verified
        against, but failed on a real Nix-based QGIS install with
        "mod_spatialite.so: cannot open shared object file" (Nix has no
        standard library search path a bare name can resolve against,
        and hard-coding a nix store path is explicitly off the table -
        it's unique to the machine that built it). Writing through
        GDAL/OGR's own ExecuteSQL() instead avoids the problem
        entirely: GDAL's GeoPackage driver already has these functions
        built in, which is exactly why every OTHER GeoPackage write in
        this codebase (see grid_column_utils.py) goes through OGR, not
        a bare sqlite3 connection.
        """
        from geest.core.grid_column_utils import _commit_or_raise, _execute_sql_with_retry, _open_gpkg_for_write

        ds = _open_gpkg_for_write(gpkg_path)
        if not ds:
            log_message(f"Could not open GeoPackage for writing: {gpkg_path}", tag="GeoE3")
            return
        try:
            layer = ds.GetLayerByName(table_name)
            if layer is None:
                log_message(f"Table not found in {gpkg_path}: {table_name}", tag="GeoE3")
                return
            layer_defn = layer.GetLayerDefn()
            existing_columns = {layer_defn.GetFieldDefn(i).GetName() for i in range(layer_defn.GetFieldCount())}

            if zone_names is not None and "zone_name" not in existing_columns:
                layer.CreateField(ogr.FieldDefn("zone_name", ogr.OFTString))
            for _display_name, col in missing_columns:
                column_name = f"avg_{col}"
                if column_name not in existing_columns:
                    layer.CreateField(ogr.FieldDefn(column_name, ogr.OFTReal))

            zone_fids = set(averages_by_zone) | set(zone_names or {})
            ds.StartTransaction()
            try:
                for zone_fid in zone_fids:
                    assignments = []
                    if zone_names and zone_fid in zone_names:
                        escaped = str(zone_names[zone_fid]).replace("'", "''")
                        assignments.append(f"zone_name = '{escaped}'")
                    for col, value in averages_by_zone.get(zone_fid, {}).items():
                        value_sql = "NULL" if value is None else repr(float(value))
                        assignments.append(f'"avg_{col}" = {value_sql}')
                    if not assignments:
                        continue
                    sql = (
                        f'UPDATE "{table_name}" SET {", ".join(assignments)} WHERE fid = {int(zone_fid)}'  # nosec B608
                    )
                    _execute_sql_with_retry(ds, sql)
            except Exception:
                ds.RollbackTransaction()
                raise
            _commit_or_raise(ds, "subnational zone results")
        finally:
            ds = None

    @staticmethod
    def _existing_sqlite_columns(gpkg_path: str, table_name: str) -> set:
        """Field names already present on a GeoPackage table, read via
        OGR (not a raw sqlite3 connection, for the same reason
        _write_zone_results() doesn't use one) - used to decide which
        avg_<column>/zone_name columns still need to be added (see
        aggregate_factor_dimension_totals()'s idempotency/legacy note).
        """
        ds = ogr.Open(gpkg_path, 0)
        if not ds:
            log_message(f"Could not open GeoPackage: {gpkg_path}", tag="GeoE3")
            return set()
        try:
            layer = ds.GetLayerByName(table_name)
            if layer is None:
                return set()
            layer_defn = layer.GetLayerDefn()
            return {layer_defn.GetFieldDefn(i).GetName() for i in range(layer_defn.GetFieldCount())}
        finally:
            ds = None

    def apply_qml_style(self, source_qml: str, qml_path: str) -> None:
        """
        Apply QML style by copying from source to destination.

        Args:
            source_qml (str): Path to the source QML file.
            qml_path (str): Path where the QML file should be copied to.
        """

        log_message(f"Copying QML style from {source_qml} to {qml_path}")
        # Apply QML Style
        if os.path.exists(source_qml):
            shutil.copy(source_qml, qml_path)
        else:
            log_message("QML style file not found. Skipping QML copy.")

    def finished(self, result: bool) -> None:
        """
        Called when the task completes.

        Args:
            result (bool): The result of the task execution.
        """
        if result:
            log_message("Subnational aggregate calculation completed successfully.")
        else:
            log_message("Subnational aggregate calculation failed.")

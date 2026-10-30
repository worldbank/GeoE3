# -*- coding: utf-8 -*-
"""📦 Country pack module.

Builds a single "country pack" GeoPackage self-contained enough to
reconstruct an entire GeoE3 project elsewhere. Four kinds of content go
in, each its own named layer/raster table:

- Configured INPUT data: the raw dataset a user pointed each indicator
  at (the schools shapefile, the hazard raster, the road network, and so
  on), clipped to the study area and named after the indicator's own id
  for per-indicator sources, or a fixed name for project-level ones
  (road network, population, masks, the subnational aggregation
  boundary). See all_sources().
- The project's own study_area.gpkg, bundled wholesale (not just the
  grid boundary - study_area_grid also carries every already-computed
  indicator/factor/dimension/analysis score as its own attribute
  column, which is what makes already-computed results survive the
  round trip almost for free). See study_area_sources().
- Already-computed result rasters, when they exist (an item that's been
  run), named "{id}_result" (dim_/fac_ prefixed for dimensions/factors -
  see result_sources()'s docstring for why that matters).
- A handful of indicators (EPLEX, the WBL-sourced Contextual factors)
  have no spatial dataset at all - just a number a user typed in - and
  get a row in INDEX_SCORE_TABLE_NAME instead (index_score_values()).

The project's full model.json also goes in as a single JSON blob, in
PROJECT_MODEL_TABLE_NAME (write_project_model_table()) - everything
else in this module writes the DATA a model.json points at; this is
what lets an importer reconstruct the model.json itself.

Every function here does its own file I/O (GDAL/OGR) and never touches
QgsProject.instance() - safe to call from a QgsTask worker thread. If a
source is currently loaded in the user's live QGIS session and you want
its real styling embedded (rather than QGIS's default rendering),
resolve that style's XML on the MAIN THREAD first (reading the project's
layer registry off-thread is the same hazard class that corrupted
AnalysisReportTask - see base_report.py's history) and pass it in via
style_xml_by_path.
"""

import json
import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from osgeo import gdal, ogr, osr
from qgis.core import QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtXml import QDomDocument

from geest.utilities import log_message

# analysis_mode -> indicator uses the generic VectorDataSourceWidget
# convention: "{mode without 'use_'}_layer_source" (picked from an
# already-open layer) or "..._shapefile" (browsed file) - whichever is
# populated. use_polygon_per_cell is here too: at regional scale it's
# actually Space2Stats-backed with no local file, which indicator_source()
# handles naturally by finding neither field populated.
VECTOR_WIDGET_MODES = {
    "use_multi_buffer_point",
    "use_single_buffer_point",
    "use_point_per_cell",
    "use_polyline_per_cell",
    "use_osm_transport_polyline_per_cell",
    "use_street_lights",
    "use_polygon_per_cell",
    "use_classify_polygon_into_classes",
    "use_classify_safety_polygon_into_classes",
}

#: analysis_mode -> the field holding its raster path, when the source
#: is a local raster file.
RASTER_FIELD_BY_MODE = {
    "use_environmental_hazards": "environmental_hazards_raster",
    "use_nighttime_lights": "nighttime_lights_raster",
}

#: Both of those same two analysis_modes also have a Space2Stats-backed
#: variant (used at regional scale): instead of a local raster file, the
#: configured source is an OGR-provider vector layer (study area grid
#: cells pre-joined to an S2S field), saved under a differently-named
#: field - confirmed live on a real regional-scale project where the
#: plain raster field was empty but this one held the actual configured
#: source, silently dropping every hazard/nighttime-lights indicator
#: from the pack.
S2S_VECTOR_FIELD_BY_MODE = {
    "use_environmental_hazards": "environmental_hazards_layer_source",
    "use_nighttime_lights": "nighttime_lights_layer_source",
}

#: analysis_mode -> (csv field name, x field, y field) for the one
#: CSV-sourced indicator type (FCV, backed by ACLED data), using ACLED's
#: own column names. Field name confirmed against real model.json files
#: (StLuciaH3/Albania/Comoros) - AcledCsvDataSourceWidget.add_internal_
#: widgets() hardcodes self.widget_key = "use_csv_to_point_layer"
#: (overwriting the "use_"-stripped key the widget factory actually
#: passes in), so the field keeps the full mode string as its prefix,
#: unlike every other indicator-level field. Confirmed live: this
#: silently dropped every FCV/ACLED indicator from the pack entirely
#: until fixed, since indicator_source() was reading a field name that
#: real projects never populate.
CSV_MODE_FIELDS = {
    "use_csv_to_point_layer": ("use_csv_to_point_layer_csv_file", "longitude", "latitude"),
}

#: analysis_mode -> field holding the configured value, for indicators
#: that are a manually-typed single national score rather than a spatial
#: dataset (EPLEX, and the WBL-sourced Contextual factors). Nothing to
#: clip or copy for these - captured as rows in INDEX_SCORE_TABLE_NAME
#: instead, so a project's full configuration survives in the pack
#: rather than this handful of indicators silently having nothing to
#: show for them.
INDEX_SCORE_FIELD_BY_MODE = {
    "use_index_score": "index_score",
    "use_contextual_index_score": "index_score",
    "use_index_score_with_ghsl": "index_score",
    "use_index_score_with_ookla": "index_score",
    "use_eplex_score": "eplex_score",
}

#: Name of the aspatial (non-spatial) table build_country_pack() writes
#: the INDEX_SCORE_FIELD_BY_MODE values into.
INDEX_SCORE_TABLE_NAME = "index_score_values"

#: Project-level (not per-indicator) inputs: output layer name -> candidate
#: field names to try in order -> data kind, or None when the kind varies
#: (population can be either, see population_source below).
PROJECT_LEVEL_SOURCES = [
    ("road_network", ["road_network_layer_path"], "vector"),
    ("population", ["population_layer_source", "population_shapefile"], None),
    ("point_mask", ["point_mask_layer_source", "point_mask_shapefile"], "vector"),
    ("polygon_mask", ["polygon_mask_layer_source", "polygon_mask_shapefile"], "vector"),
    ("raster_mask", ["raster_mask_layer_source", "raster_mask_raster"], "raster"),
    ("aggregation_boundary", ["aggregation_layer_source", "aggregation_shapefile"], "vector"),
]

#: GPKG's raster driver only supports these pixel types - anything else
#: must be downcast (see _raster_needs_float32()).
GPKG_RASTER_TYPES = ("Byte", "Int16", "UInt16", "Float32")

#: IEEE 754 single-precision max - see write_raster_source()'s docstring
#: on why an out-of-range Float64 nodata sentinel must be clamped to
#: this rather than cast as-is when downcasting to Float32. The exact
#: value, not the usual rounded "3.4028235e38" - that rounds up past
#: the true max and makes GDAL re-clamp it anyway (with a warning).
FLOAT32_MAX = 3.4028234663852886e38


@dataclass
class PackSource:
    """One input dataset to copy into the country pack.

    Attributes:
        layer_name: Output layer/raster-table name in the pack.
        path: Path to the source dataset (may include a "|layername=..."
            suffix for a layer inside a GeoPackage).
        kind: "vector", "raster", or "csv".
        x_field: For kind "csv", the longitude/X column name.
        y_field: For kind "csv", the latitude/Y column name.
        clip: Whether to clip this source to the study area on write.
            False for the study area's own layers (study_area_grid alone
            can be 400k+ features - clipping it against itself is both
            pointless and, at that size, genuinely slow) and for already-
            computed result rasters (already confined to the study area
            by construction).
    """

    layer_name: str
    path: str
    kind: str
    x_field: Optional[str] = None
    y_field: Optional[str] = None
    clip: bool = True


def _indicator_source_field(indicator: dict) -> Optional[tuple]:
    """Resolve which populated field holds one indicator's configured input, if any.

    Factored out of indicator_source() so the country pack importer can
    resolve the exact same field - by the exact same rules - to know
    which one to overwrite with a freshly-extracted local path, rather
    than re-deriving this mode-dispatch logic a second time and risking
    the two falling out of step.

    Args:
        indicator: One indicator object from model.json.

    Returns:
        (field_name, kind, x_field, y_field) for the one field that's
        actually populated, or None if this indicator has no file-based
        input (see indicator_source()'s docstring for the cases this
        covers). x_field/y_field are only meaningful for kind "csv".
    """
    mode = indicator.get("analysis_mode")
    if not mode:
        return None

    if mode in RASTER_FIELD_BY_MODE:
        field_name = RASTER_FIELD_BY_MODE[mode]
        if indicator.get(field_name):
            return field_name, "raster", None, None
        s2s_field = S2S_VECTOR_FIELD_BY_MODE.get(mode)
        if s2s_field and indicator.get(s2s_field):
            return s2s_field, "vector", None, None
        return None

    if mode in CSV_MODE_FIELDS:
        field_name, x_field, y_field = CSV_MODE_FIELDS[mode]
        return (field_name, "csv", x_field, y_field) if indicator.get(field_name) else None

    if mode in VECTOR_WIDGET_MODES:
        widget_key = mode[len("use_") :]
        for candidate in (f"{widget_key}_layer_source", f"{widget_key}_shapefile"):
            if indicator.get(candidate):
                return candidate, "vector", None, None
        return None

    return None


def indicator_source(indicator: dict) -> Optional[PackSource]:
    """The configured input dataset for one indicator.

    Args:
        indicator: One indicator object from model.json.

    Returns:
        A PackSource, or None if this indicator has no file-based input
        (a manually-typed national score such as EPLEX or a WBL factor,
        an indicator nobody has configured yet, or a regional-scale
        use_polygon_per_cell indicator - unlike environmental hazards and
        nighttime lights, its Space2Stats variant has no queryable layer
        path field at all, only a join configuration).
    """
    layer_name = indicator.get("id")
    if not layer_name:
        return None
    resolved = _indicator_source_field(indicator)
    if not resolved:
        return None
    field_name, kind, x_field, y_field = resolved
    return PackSource(layer_name, indicator[field_name], kind, x_field, y_field)


def _project_level_source_field(model: dict, field_names: List[str]) -> Optional[str]:
    """The first of a project-level input's candidate field names that's actually populated.

    Factored out of project_level_sources() for the same reason as
    _indicator_source_field() - the importer needs to know exactly which
    field to overwrite, not just the path it currently holds.

    Args:
        model: The parsed model.json document.
        field_names: Candidate field names to try, in order.

    Returns:
        The first populated field name, or None if none of them are set.
    """
    for field_name in field_names:
        if model.get(field_name):
            return field_name
    return None


def project_level_sources(model: dict) -> List[PackSource]:
    """The project-wide (not per-indicator) configured inputs.

    Args:
        model: The parsed model.json document.

    Returns:
        A PackSource for each project-level input that has actually been
        configured (empty/unset ones are omitted).
    """
    sources = []
    for layer_name, field_names, kind in PROJECT_LEVEL_SOURCES:
        field_name = _project_level_source_field(model, field_names)
        if not field_name:
            continue
        actual_kind = kind
        if actual_kind is None:
            # Population is the one source whose kind varies project to
            # project - population_source records which it is.
            actual_kind = "raster" if model.get("population_source") == "raster" else "vector"
        sources.append(PackSource(layer_name, model[field_name], actual_kind))
    return sources


def all_sources(model: dict) -> List[PackSource]:
    """Every input dataset (indicator-level and project-level) this project has configured.

    Args:
        model: The parsed model.json document.

    Returns:
        One PackSource per configured input. Layer names are not
        deduplicated - several indicators can legitimately share the same
        underlying source file and each still gets its own named layer
        in the pack.
    """
    sources = list(project_level_sources(model))
    for dimension in model.get("dimensions", []):
        for factor in dimension.get("factors", []):
            for indicator in factor.get("indicators", []):
                source = indicator_source(indicator)
                if source:
                    sources.append(source)
    return sources


def study_area_sources(working_directory: str) -> List[PackSource]:
    """Every layer in the project's own study_area.gpkg, bundled as-is.

    This is what makes "preserve already-computed results" work almost
    for free: study_area_grid carries every indicator/factor/dimension/
    analysis score the project has run so far as its own attribute
    column (confirmed against a real project's schema), so bundling the
    grid wholesale captures all of that without needing to separately
    chase down every possible result layer. Every layer is included
    (not just the grid) rather than a hand-picked subset, since this
    file's own layer list can grow as the plugin evolves and a stale
    hardcoded list would silently drop something that later turned out
    to matter (GHSL settlements, the coarser display-resolution grid
    variants, etc.).

    Args:
        working_directory: The project's working directory.

    Returns:
        One PackSource per layer in study_area/study_area.gpkg (clip=False
        - see PackSource's docstring), or an empty list if that file
        doesn't exist yet (a project that was never run past setup).
    """
    study_area_gpkg = os.path.join(working_directory, "study_area", "study_area.gpkg")
    if not os.path.exists(study_area_gpkg):
        return []
    dataset = gdal.OpenEx(study_area_gpkg, gdal.OF_VECTOR)
    if dataset is None:
        return []
    sources = [
        PackSource(
            dataset.GetLayerByIndex(i).GetName(),
            f"{study_area_gpkg}|layername={dataset.GetLayerByIndex(i).GetName()}",
            "vector",
            clip=False,
        )
        for i in range(dataset.GetLayerCount())
    ]
    dataset = None
    return sources


#: Suffix appended to an indicator/factor/dimension's own id - or the
#: fixed name used for the top-level analysis result when the model has
#: no better name for it - so a computed result never collides with
#: that same item's own input-data entry in the pack.
RESULT_SUFFIX = "_result"
TOP_LEVEL_RESULT_NAME = "analysis"

#: Extra top-level composite rasters model.json can carry beyond the
#: single "result_file" - produced once the GHSL-masking/population-
#: weighting/opportunity-masking workflows have actually been run. This
#: is the authoritative list AnalysisReport displays (see
#: analysis_report.py's product_keys) - without these, a project whose
#: analysis_aggregation step has run loses every one of these composite
#: products on a country-pack round trip.
TOP_LEVEL_RESULT_RASTER_FIELDS = [
    "geoe3_score_ghsl_masked_result_file",
    "geoe3_by_population",
    "geoe3_score_by_population_ghsl_masked_result_file",
    "opportunities_mask_result_file",
]

#: Subnational aggregation outputs - one polygon-per-administrative-zone
#: vector GeoPackage per product (see analysis_report.py's
#: subnational_product_keys), carrying the majority score per zone.
TOP_LEVEL_SUBNATIONAL_AGGREGATION_FIELDS = [
    "geoe3_score_subnational_aggregation",
    "geoe3_score_ghsl_masked_subnational_aggregation",
    "geoe3_by_population_subnational_aggregation",
    "geoe3_score_by_population_ghsl_masked_subnational_aggregation",
]


def _iter_result_nodes(model: dict):
    """Yield (name, node) for every model.json node that can carry a result_file.

    Factored out of result_sources() so the country pack importer can
    walk the exact same nodes, under the exact same names, to know which
    node's result_file to overwrite with a freshly-extracted local path.

    Args:
        model: The parsed model.json document.

    Yields:
        (name, node) pairs - name is the unprefixed/un-suffixed id (see
        result_sources()'s docstring for the dim_/fac_ prefixing applied
        on top of this), node is the dict to look for "result_file" on
        (the model itself, for the top-level analysis node).
    """
    yield model.get("output_filename") or TOP_LEVEL_RESULT_NAME, model
    for dimension in model.get("dimensions", []):
        yield f"dim_{dimension.get('id')}", dimension
        for factor in dimension.get("factors", []):
            yield f"fac_{factor.get('id')}", factor
            for indicator in factor.get("indicators", []):
                yield indicator.get("id"), indicator


def result_sources(model: dict) -> List[PackSource]:
    """Every already-computed result this project has, at any level.

    Indicator, factor, dimension, and the top-level analysis node can
    each carry a result_file once that item has been run - almost always
    a .vrt, which GDAL can read and flatten into a plain raster table
    exactly like any other raster input (write_raster_source already
    handles this; .vrt is just another GDAL-readable format). The model
    can also carry extra top-level composite products
    (TOP_LEVEL_RESULT_RASTER_FIELDS, rasters; TOP_LEVEL_SUBNATIONAL_
    AGGREGATION_FIELDS, per-zone vectors) once the analysis_aggregation
    workflow has run - these use their own field name as the pack's
    table name directly (no dim_/fac_ prefixing needed - field names
    are already unique and don't collide with any id).

    Args:
        model: The parsed model.json document.

    Returns:
        One PackSource per configured result found (clip=False - a
        result is already confined to the study area by construction).
        Items that haven't been run yet (empty value) are omitted; a
        result pointing at a file that's since been moved or deleted is
        still returned here and lands in build_country_pack()'s
        "skipped" list, the same as any other missing source.

        Dimension and factor names get study_area_grid's own "dim_"/
        "fac_" column-naming convention (confirmed against a real
        project's schema), not just this module's local choice: GeoPackage
        table names are case-insensitive at the SQLite level even though
        gpkg_contents preserves the original casing for display, so a
        factor and its one child indicator sharing the same name in
        different case (e.g. factor "fcv" under indicator "FCV") would
        otherwise collide and silently drop one of the two - confirmed
        live against a real project before this prefixing was added.
    """
    sources = [
        PackSource(f"{name}{RESULT_SUFFIX}", node["result_file"], "raster", clip=False)
        for name, node in _iter_result_nodes(model)
        if node.get("result_file")
    ]
    sources += [
        PackSource(field, model[field], "raster", clip=False)
        for field in TOP_LEVEL_RESULT_RASTER_FIELDS
        if model.get(field)
    ]
    sources += [
        PackSource(field, model[field], "vector", clip=False)
        for field in TOP_LEVEL_SUBNATIONAL_AGGREGATION_FIELDS
        if model.get(field)
    ]
    return sources


def index_score_values(model: dict) -> List[dict]:
    """Every manually-typed national-score indicator's configured value.

    These indicators (EPLEX, the WBL-sourced Contextual factors, and a
    couple of others - see INDEX_SCORE_FIELD_BY_MODE) have no spatial
    dataset to bundle: the "input" is just a number a user researched and
    typed in. Returned separately from all_sources() rather than folded
    in, since there's no file to clip/copy here - build_country_pack()
    writes these as rows in one plain table instead.

    Args:
        model: The parsed model.json document.

    Returns:
        One dict per configured indicator of these modes:
        {"id", "name", "analysis_mode", "value"}. Indicators of these
        modes with no value typed in yet are omitted.
    """
    rows = []
    for dimension in model.get("dimensions", []):
        for factor in dimension.get("factors", []):
            for indicator in factor.get("indicators", []):
                mode = indicator.get("analysis_mode")
                field_name = INDEX_SCORE_FIELD_BY_MODE.get(mode)
                if not field_name:
                    continue
                value = indicator.get(field_name)
                if value in (None, ""):
                    continue
                rows.append(
                    {
                        "id": indicator.get("id", ""),
                        "name": indicator.get("indicator", ""),
                        "analysis_mode": mode,
                        "value": float(value),
                    }
                )
    return rows


def _split_source_uri(path: str):
    """Split a "file|layername=X" QGIS-style URI into (base_path, layer_name).

    This "|layername=" convention is how QGIS points at one layer inside
    a multi-layer source (a GeoPackage, typically), but GDAL's own Python
    API doesn't understand it - passed straight through, GDAL just fails
    to open the literal (unsplit) string ("ERROR 1: hSrcDS == NULL").

    Args:
        path: A plain path, or "path|layername=name".

    Returns:
        (base_path, layer_name) - layer_name is None when the input had
        no "|layername=" suffix.
    """
    base_path, _, suffix = path.partition("|")
    if suffix.startswith("layername="):
        return base_path, suffix[len("layername=") :]
    return base_path, None


def _raster_needs_float32(path: str) -> bool:
    """Whether a raster's pixel type needs downcasting for GPKG storage.

    Args:
        path: Path to the source raster.

    Returns:
        True if the raster's data type isn't one GPKG's raster driver
        accepts (Byte/Int16/UInt16/Float32), False otherwise (including
        when the raster can't be opened - the warp itself will raise a
        clearer error in that case).
    """
    base_path, _ = _split_source_uri(path)
    dataset = gdal.Open(base_path)
    if dataset is None:
        return False
    dtype = gdal.GetDataTypeName(dataset.GetRasterBand(1).DataType)
    dataset = None
    return dtype not in GPKG_RASTER_TYPES


def _float32_safe_nodata(path: str) -> Optional[float]:
    """A Float32-safe nodata value for a raster being downcast to Float32.

    Confirmed live against a real GeoE3 result raster: several result
    rasters are Float64 with NoDataValue set to Float64's own max
    (effectively an "unset" sentinel) - gdal.Warp's dtype downcast casts
    that straight into the output band's data, silently overflowing it
    to +inf, while the output's NoDataValue metadata keeps reporting the
    original, now-mismatched Float64 value. Any later `pixel == nodata`
    check that doesn't itself re-cast to Float32 first (e.g. comparing
    against a value read straight from model.json or another layer's
    metadata) then fails to recognise those pixels as nodata at all.

    Args:
        path: Path to the source raster.

    Returns:
        The source band's own nodata value, clamped to +/-FLOAT32_MAX if
        it would otherwise overflow, or None if the source has no nodata
        value set (or can't be opened - the warp itself raises a clearer
        error in that case).
    """
    base_path, _ = _split_source_uri(path)
    dataset = gdal.Open(base_path)
    if dataset is None:
        return None
    nodata = dataset.GetRasterBand(1).GetNoDataValue()
    dataset = None
    if nodata is None or abs(nodata) <= FLOAT32_MAX:
        return nodata
    return FLOAT32_MAX if nodata > 0 else -FLOAT32_MAX


def write_raster_source(
    source: PackSource,
    study_area_gpkg: str,
    study_area_layer: str,
    out_gpkg: str,
    append: bool,
) -> None:
    """Clip a raster to the study area and write it into the pack as its own raster table.

    Args:
        source: The raster input to write.
        study_area_gpkg: Path to the study area GeoPackage.
        study_area_layer: Name of the study area polygon layer to clip against.
        out_gpkg: Path to the output country pack GeoPackage.
        append: True if out_gpkg already has at least one raster table
            (GDAL's GPKG driver needs APPEND_SUBDATASET=YES from the
            second raster onward, in the same file).

    Raises:
        RuntimeError: If the warp fails.
    """
    base_path, _ = _split_source_uri(source.path)
    if not os.path.exists(base_path):
        raise RuntimeError(f"Source file not found: {base_path}")
    creation_options = [f"RASTER_TABLE={source.layer_name}"]
    if append:
        creation_options.append("APPEND_SUBDATASET=YES")
    warp_kwargs = {}
    if source.clip:
        warp_kwargs = {
            "cutlineDSName": study_area_gpkg,
            "cutlineLayer": study_area_layer,
            "cropToCutline": True,
        }
    needs_float32 = _raster_needs_float32(source.path)
    if needs_float32:
        safe_nodata = _float32_safe_nodata(source.path)
        if safe_nodata is not None:
            warp_kwargs["dstNodata"] = safe_nodata
    options = gdal.WarpOptions(
        format="GPKG",
        outputType=(gdal.GDT_Float32 if needs_float32 else gdal.GDT_Unknown),
        creationOptions=creation_options,
        **warp_kwargs,
    )
    result = gdal.Warp(out_gpkg, base_path, options=options)
    if result is None:
        raise RuntimeError(f"Failed to write raster '{source.layer_name}': {gdal.GetLastErrorMsg()}")
    result = None  # noqa: F841 - closes/flushes the dataset


def _source_vector_srs(base_path: str, source_layer_name: Optional[str], kind: str) -> Optional[osr.SpatialReference]:
    """Best-effort spatial reference of a vector/CSV source, for clip-geometry reprojection.

    Args:
        base_path: Path to the source dataset (no "|layername=" suffix).
        source_layer_name: Layer to read within base_path, or None to use the first layer.
        kind: "vector" or "csv".

    Returns:
        The source's CRS, or EPSG:4326 for a CSV (X_POSSIBLE_NAMES/
        Y_POSSIBLE_NAMES columns are always plain lon/lat - the one CSV-
        sourced indicator type here uses ACLED's own "longitude"/
        "latitude" columns), or None if it can't be determined (an
        unreadable source, or a layer with no CRS set at all).
    """
    if kind == "csv":
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        return srs
    dataset = gdal.OpenEx(base_path, gdal.OF_VECTOR)
    if dataset is None:
        return None
    layer = dataset.GetLayerByName(source_layer_name) if source_layer_name else dataset.GetLayer(0)
    return layer.GetSpatialRef() if layer else None


def _clip_geometry_wkt(study_area_gpkg: str, study_area_layer: str, target_srs: osr.SpatialReference) -> str:
    """The study area clip boundary, reprojected into a target CRS, as WKT.

    ogr2ogr's own "-clipsrc <file> -clipsrclayer <name>" form does not
    reproject the clip geometry to match the source layer's CRS on the
    GDAL version QGIS 3.34 LTR bundles (3.4.1) - confirmed live: clipping
    a WGS84 OSM point layer (StLucia's Kindergartens_Location and every
    other OSM-sourced multi_buffer_point indicator) against a UTM-
    projected study area boundary silently produced a VALID but EMPTY
    layer (gdal.VectorTranslate didn't raise, build_country_pack()'s own
    summary reported it as "written") because the clip polygon's
    coordinates (metres) never overlap the source's (degrees). Unlike
    write_raster_source()'s gdal.Warp cutline, which does handle this
    automatically. Reprojecting the clip geometry ourselves and passing
    it as a literal WKT geometry (rather than a file+layer reference)
    sidesteps the gap entirely, regardless of GDAL version.

    Args:
        study_area_gpkg: Path to the study area GeoPackage.
        study_area_layer: Name of the study area polygon layer to clip against.
        target_srs: CRS to reproject the clip geometry into (the
            source layer's own CRS - see _source_vector_srs()).

    Returns:
        WKT of the union of every feature in the clip layer, in target_srs.
    """
    dataset = ogr.Open(study_area_gpkg)
    layer = dataset.GetLayerByName(study_area_layer)
    source_srs = layer.GetSpatialRef()
    geometry = ogr.Geometry(ogr.wkbMultiPolygon)
    for feature in layer:
        geometry = geometry.Union(feature.GetGeometryRef())
    if source_srs and not source_srs.IsSame(target_srs):
        # Axis order, not just the projection, has to match how OGR
        # geometries actually store coordinates (x=easting/lon,
        # y=northing/lat) - GDAL 3.x's default "authority compliant"
        # axis strategy can otherwise swap them for CRSes (like
        # EPSG:4326) formally defined lat-before-lon.
        source_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        target_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        geometry.Transform(osr.CoordinateTransformation(source_srs, target_srs))
    dataset = None
    return geometry.ExportToWkt()


def write_vector_source(
    source: PackSource,
    study_area_gpkg: str,
    study_area_layer: str,
    out_gpkg: str,
    append: bool,
) -> None:
    """Clip a vector layer to the study area and write it into the pack as its own layer.

    Args:
        source: The vector (or CSV-derived point) input to write.
        study_area_gpkg: Path to the study area GeoPackage.
        study_area_layer: Name of the study area polygon layer to clip against.
        out_gpkg: Path to the output country pack GeoPackage.
        append: True if out_gpkg already exists (GDAL's GPKG driver needs
            accessMode="append" to add a layer to an existing file rather
            than overwriting it).

    Raises:
        RuntimeError: If the source can't be opened (CSV sources only,
            via X_POSSIBLE_NAMES/Y_POSSIBLE_NAMES) or the translate fails.
    """
    base_path, source_layer_name = _split_source_uri(source.path)
    if not os.path.exists(base_path):
        raise RuntimeError(f"Source file not found: {base_path}")
    source_ds = base_path
    extra_options = []

    if source.kind == "csv":
        source_ds = gdal.OpenEx(
            base_path,
            gdal.OF_VECTOR,
            open_options=[f"X_POSSIBLE_NAMES={source.x_field}", f"Y_POSSIBLE_NAMES={source.y_field}"],
        )
        if source_ds is None:
            raise RuntimeError(f"Could not open CSV '{source.path}' as a point source for '{source.layer_name}'")
    elif source_layer_name:
        # Select only the one layer the project actually configured -
        # without this, a multi-layer source (a GeoPackage with several
        # tables) would pull in every layer under this one name.
        extra_options = [source_layer_name]

    clip_options = []
    if source.clip:
        # Reproject the clip boundary into the source's own CRS and
        # pass it as a literal WKT geometry - see _clip_geometry_wkt()'s
        # docstring for why a plain "-clipsrc <file> -clipsrclayer
        # <name>" reference silently drops every feature when the two
        # CRSes differ. Falls back to the file+layer form (the old,
        # same-CRS-only behaviour) only if the source's CRS genuinely
        # can't be determined.
        target_srs = _source_vector_srs(base_path, source_layer_name, source.kind)
        if target_srs is not None:
            clip_options = ["-clipsrc", _clip_geometry_wkt(study_area_gpkg, study_area_layer, target_srs)]
        else:
            clip_options = ["-clipsrc", study_area_gpkg, "-clipsrclayer", study_area_layer]
    options = gdal.VectorTranslateOptions(
        format="GPKG",
        layerName=source.layer_name,
        accessMode="append" if append else None,
        options=clip_options + extra_options,
    )
    result = gdal.VectorTranslate(out_gpkg, source_ds, options=options)
    if result is None:
        raise RuntimeError(f"Failed to write vector '{source.layer_name}': {gdal.GetLastErrorMsg()}")
    result = None  # noqa: F841 - closes/flushes the dataset


def write_index_score_table(rows: List[dict], out_gpkg: str, append: bool) -> None:
    """Write the manually-typed index-score values as a plain (non-spatial) GeoPackage table.

    Args:
        rows: Rows from index_score_values().
        out_gpkg: Path to the output country pack GeoPackage.
        append: True if out_gpkg already has other content - GDAL's GPKG
            driver needs the dataset opened in update mode to add a new
            table to an existing file rather than creating a fresh one.

    Raises:
        RuntimeError: If the table can't be created.
    """
    if append:
        # gdal.OF_ALL rather than a vector-only open: see
        # _actual_table_names()'s docstring - a pack that's raster-only
        # so far can't be opened by the vector-only driver mode at all.
        dataset = gdal.OpenEx(out_gpkg, gdal.OF_UPDATE | gdal.OF_ALL)
    else:
        dataset = ogr.GetDriverByName("GPKG").CreateDataSource(out_gpkg)

    if dataset is None:
        raise RuntimeError(f"Could not open '{out_gpkg}' to write {INDEX_SCORE_TABLE_NAME}")

    layer = dataset.CreateLayer(INDEX_SCORE_TABLE_NAME, geom_type=ogr.wkbNone)
    if layer is None:
        dataset = None
        raise RuntimeError(f"Could not create the {INDEX_SCORE_TABLE_NAME} table")

    layer.CreateField(ogr.FieldDefn("id", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("analysis_mode", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("value", ogr.OFTReal))

    for row in rows:
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField("id", row["id"])
        feature.SetField("name", row["name"])
        feature.SetField("analysis_mode", row["analysis_mode"])
        feature.SetField("value", row["value"])
        layer.CreateFeature(feature)
        feature = None

    dataset = None  # noqa: F841 - closes/flushes the dataset


#: Name of the aspatial table write_project_model_table() writes the
#: project's full model.json into.
PROJECT_MODEL_TABLE_NAME = "project_model"


def write_project_model_table(model: dict, out_gpkg: str, append: bool) -> None:
    """Write the project's full model.json into the pack as a single-row, non-spatial table.

    Serialized as one JSON text field rather than one column per
    model.json key: model.json's shape (dimensions -> factors ->
    indicators, each with dozens of fields that vary by analysis_mode)
    doesn't map onto a flat table row, and a single blob means the pack
    can reconstruct the exact project it came from without this module
    needing to separately track a schema for every field model.json
    happens to have today.

    Args:
        model: The parsed model.json document.
        out_gpkg: Path to the output country pack GeoPackage.
        append: True if out_gpkg already has other content - see
            write_index_score_table()'s matching parameter.

    Raises:
        RuntimeError: If the table can't be created.
    """
    if append:
        dataset = gdal.OpenEx(out_gpkg, gdal.OF_UPDATE | gdal.OF_ALL)
    else:
        dataset = ogr.GetDriverByName("GPKG").CreateDataSource(out_gpkg)

    if dataset is None:
        raise RuntimeError(f"Could not open '{out_gpkg}' to write {PROJECT_MODEL_TABLE_NAME}")

    layer = dataset.CreateLayer(PROJECT_MODEL_TABLE_NAME, geom_type=ogr.wkbNone)
    if layer is None:
        dataset = None
        raise RuntimeError(f"Could not create the {PROJECT_MODEL_TABLE_NAME} table")

    # width=0: unlimited. GPKG's underlying SQLite TEXT column has no
    # real length cap regardless, but OGR defaults OFTString to a
    # 255-character width that some drivers DO enforce/truncate to.
    model_json_field = ogr.FieldDefn("model_json", ogr.OFTString)
    model_json_field.SetWidth(0)
    layer.CreateField(model_json_field)

    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetField("model_json", json.dumps(model))
    layer.CreateFeature(feature)
    feature = None

    dataset = None  # noqa: F841 - closes/flushes the dataset


def _apply_style(uri: str, is_raster: bool, style_xml: str) -> None:
    """Embed a style into a just-written GPKG layer's layer_styles table.

    Args:
        uri: QGIS data source URI for the layer just written (e.g.
            "GPKG:out.gpkg:Fire" for a raster, "out.gpkg|layername=Fire"
            for a vector).
        is_raster: Whether the layer is a raster.
        style_xml: Style XML previously exported from a live layer (see
            the module docstring - this must be resolved on the main
            thread, never read here).
    """
    layer = QgsRasterLayer(uri, "style-target") if is_raster else QgsVectorLayer(uri, "style-target", "ogr")
    if not layer.isValid():
        log_message(f"Could not reopen '{uri}' to apply style - skipping.", tag="GeoE3")
        return
    doc = QDomDocument()
    doc.setContent(style_xml)
    success, message = layer.importNamedStyle(doc)
    if not success:
        log_message(f"Could not import style for '{uri}': {message}", tag="GeoE3")
        return
    error = layer.saveStyleToDatabase("default", "country pack source style", True, "")
    if error:
        log_message(f"Could not save style for '{uri}' into the pack: {error}", tag="GeoE3")


def _actual_table_names(output_path: str) -> set:
    """The table names a GeoPackage genuinely contains, vector and raster alike.

    A write call succeeding doesn't guarantee a layer survives to the end
    of the build - GDAL's GPKG driver, for one real example, silently
    recreates the whole file (destroying everything already in it)
    unless told to append (see build_country_pack()'s "append" handling,
    added after this exact failure mode wiped out an already-written
    layer). Querying gpkg_contents directly, rather than GetLayerCount()
    (vector only) or GetSubDatasets() (which comes back empty when a
    GeoPackage has exactly one raster table - not "no rasters", just an
    API quirk of how GDAL exposes a single raster), is the one way to
    reliably list both kinds regardless of how many of each are present.
    Opened with gdal.OF_ALL rather than plain ogr.Open(), which returns
    None for a GeoPackage that happens to have no vector layers at all
    (confirmed live: a pack with only raster sources, e.g. after the one
    configured vector source failed and got skipped, couldn't be
    reopened by the OGR driver on its own).

    Args:
        output_path: Path to the pack GeoPackage.

    Returns:
        Every table name gpkg_contents lists, or an empty set if the
        file can't be opened at all.
    """
    dataset = gdal.OpenEx(output_path, gdal.OF_ALL)
    if dataset is None:
        return set()
    names = set()
    result = dataset.ExecuteSQL("SELECT table_name FROM gpkg_contents")
    for feature in result:
        names.add(feature.GetField("table_name"))
    dataset.ReleaseResultSet(result)
    dataset = None
    return names


def build_country_pack(
    working_directory: str,
    model: dict,
    output_path: str,
    style_xml_by_path: Optional[Dict[str, str]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, List[str]]:
    """Build a single country pack GeoPackage from a project's configured inputs.

    Args:
        working_directory: The project's working directory (where
            study_area/study_area.gpkg lives).
        model: The already-parsed model.json document.
        output_path: Path the pack GeoPackage should be written to. Any
            existing file at this path is removed first.
        style_xml_by_path: Source path -> style XML, for sources whose
            style should be embedded (resolved on the main thread - see
            the module docstring).
        progress_callback: Optional callback(done_count, total_count,
            current_layer_name), called after each source is processed.

    Returns:
        {"written": [...], "skipped": [...]} - layer names confirmed
        present in the finished file (re-verified against the file
        itself, not just "the write call didn't raise" - see
        _actual_table_names()), and names that either failed outright or
        didn't survive to the end of the build.
    """
    style_xml_by_path = style_xml_by_path or {}
    study_area_gpkg = os.path.join(working_directory, "study_area", "study_area.gpkg")
    study_area_layer = "study_area_clip_polygons"

    if os.path.exists(output_path):
        os.remove(output_path)

    sources = all_sources(model) + study_area_sources(working_directory) + result_sources(model)
    written: List[str] = []
    skipped: List[str] = []

    for index, source in enumerate(sources):
        if progress_callback:
            progress_callback(index, len(sources), source.layer_name)
        try:
            # GDAL's GPKG driver recreates the whole file from scratch
            # unless told to append - wiping out whatever's already in
            # it, vector or raster alike. So "append" has to mean "does
            # the output file exist yet at all", checked fresh each
            # write, not "have I already written a layer of this same
            # kind" - the latter let a raster write silently destroy an
            # earlier vector layer the first time the source list
            # switched from vector sources to raster ones (caught via a
            # real end-to-end run: road_network vanished the moment the
            # first raster was appended after it).
            append = os.path.exists(output_path)
            if source.kind == "raster":
                write_raster_source(source, study_area_gpkg, study_area_layer, output_path, append)
                uri = f"GPKG:{output_path}:{source.layer_name}"
                is_raster = True
            else:
                write_vector_source(source, study_area_gpkg, study_area_layer, output_path, append)
                uri = f"{output_path}|layername={source.layer_name}"
                is_raster = False

            style_xml = style_xml_by_path.get(source.path.split("|")[0])
            if style_xml:
                _apply_style(uri, is_raster, style_xml)

            written.append(source.layer_name)
        except Exception as e:
            # Broad on purpose: a missing/moved/corrupted input is a real
            # possibility across 19+ independently-configured sources, and
            # GDAL's own failure mode for "file genuinely doesn't exist" is
            # not always a clean, catchable RuntimeError - confirmed to
            # sometimes surface as a raw TypeError from the SWIG binding
            # layer instead. One bad source should drop into "skipped",
            # not abort the whole pack.
            log_message(f"Skipping '{source.layer_name}': {e}", tag="GeoE3")
            skipped.append(source.layer_name)

    if progress_callback:
        progress_callback(len(sources), len(sources), "")

    index_rows = index_score_values(model)
    if index_rows:
        try:
            write_index_score_table(index_rows, output_path, os.path.exists(output_path))
            written.append(INDEX_SCORE_TABLE_NAME)
        except Exception as e:
            log_message(f"Skipping {INDEX_SCORE_TABLE_NAME}: {e}", tag="GeoE3")
            skipped.append(INDEX_SCORE_TABLE_NAME)

    try:
        write_project_model_table(model, output_path, os.path.exists(output_path))
        written.append(PROJECT_MODEL_TABLE_NAME)
    except Exception as e:
        log_message(f"Skipping {PROJECT_MODEL_TABLE_NAME}: {e}", tag="GeoE3")
        skipped.append(PROJECT_MODEL_TABLE_NAME)

    # Final, authoritative check: re-open the finished file and confirm
    # every layer the loop above believes it wrote is actually still
    # there. A write call not raising is not proof of that - see
    # _actual_table_names()'s docstring for the exact failure mode this
    # caught live.
    actual_names = _actual_table_names(output_path) if written else set()
    verified = [name for name in written if name in actual_names]
    lost = [name for name in written if name not in actual_names]
    if lost:
        log_message(
            f"Country pack: {len(lost)} layer(s) were written but are missing from "
            f"the final file (likely overwritten by a later write): {lost}",
            tag="GeoE3",
        )
        skipped = skipped + lost

    return {"written": verified, "skipped": skipped}

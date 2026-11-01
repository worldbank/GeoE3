# -*- coding: utf-8 -*-
"""Score-distribution histogram math shared by the analysis report and the item info panel's Sparkline page.

Pure data-gathering/binning functions, extracted from
geest.core.reports.analysis_report.AnalysisReport so both the report
(which draws them as QgsLayoutItem shapes on a print page) and the GUI
(which draws them with QPainter in a widget - see
geest.gui.widgets.sparkline_chart.SparklineChart) read and bin the
exact same way, from the exact same source. No QgsLayout/report context
here - just numpy over values already in memory, and a single sqlite3/
OGR read to get them.
"""

import os
import sqlite3
from typing import List, Tuple

import numpy

from geest.core.constants import GEOE3_BY_POPULATION_COLORS, SCORE_LEGEND_COLORS
from geest.core.grid_column_utils import _quote_sql_identifier
from geest.utilities import log_message


def score_histogram_from_values(values) -> List[int]:
    """Count values per QGIS's 5-class DISCRETE colour-ramp boundaries.

    See resources/qml/analysis.qml: (0,1], (1,2], (2,3], (3,4], (4,5] -
    matching the colours actually painted on the map exactly. Only
    valid for values on the plain 0-5 scale - a bivariate product like
    "by population" uses a completely different scheme (see
    palette_histogram_from_values()).

    Args:
        values: A 1-D array-like of score values.

    Returns:
        list: Five counts, one per QML class, in (0,1] .. (4,5] order.
    """
    # right=True => bins[i-1] < value <= bins[i], matching the QML's
    # own right-inclusive class boundaries; index 5 (value > 5) is out
    # of range and dropped by only counting indices 0-4.
    class_index = numpy.digitize(values, bins=[1, 2, 3, 4, 5], right=True)
    return [int(numpy.count_nonzero(class_index == i)) for i in range(5)]


def palette_histogram_from_values(values, n_classes: int) -> List[int]:
    """Count values per EXACT integer class 1..n_classes.

    Matches a PalettedRasterRenderer's unique-value scheme (e.g.
    geoe3_by_population_score.qml's 15-class enablement x population
    bivariate palette) - unlike score_histogram_from_values()'s
    DISCRETE range bucketing, each class here is a single exact value,
    not a (lower, upper] interval.

    Args:
        values: A 1-D array-like of score values.
        n_classes: Number of palette classes (e.g. 15).

    Returns:
        list: n_classes counts, for values 1..n_classes in order.
    """
    rounded = numpy.round(values).astype(int)
    return [int(numpy.count_nonzero(rounded == v)) for v in range(1, n_classes + 1)]


def read_grid_column_values(gpkg_path: str, column_name: str):
    """Read study_area_grid's own column values directly from the GeoPackage.

    The same values every result raster was rasterised from, and the
    authoritative source for them (the raster is a resampled render,
    not the data itself).

    Exact 0/NULL is dropped: a large share of cells carry a literal 0
    (outside the populated/opportunity area, not a genuine "very low"
    score), and counting it would flatten the distribution any
    sparkline built from this exists to show.

    Args:
        gpkg_path: Path to study_area.gpkg.
        column_name: study_area_grid column to read.

    Returns:
        A 1-D numpy array of the column's non-null, non-zero values.
    """
    if not gpkg_path or not os.path.exists(gpkg_path):
        return numpy.array([])
    try:
        quoted_column = _quote_sql_identifier(column_name)
    except ValueError as error:
        log_message(f"Refusing to read grid column for sparkline: {error}", tag="GeoE3")
        return numpy.array([])

    try:
        connection = sqlite3.connect(gpkg_path)
        try:
            rows = connection.execute(
                f"SELECT {quoted_column} FROM study_area_grid "  # nosec B608
                f"WHERE {quoted_column} IS NOT NULL AND {quoted_column} > 0"
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as error:
        log_message(f"Could not read grid column '{column_name}' for sparkline: {error}", tag="GeoE3")
        return numpy.array([])

    return numpy.array([row[0] for row in rows], dtype=float)


def read_vector_field_values(layer, field_name: str):
    """Read a vector layer's own attribute values directly.

    The subnational aggregation products' authoritative per-zone score
    (one administrative zone per feature), with no study_area_grid
    column backing them the way per-cell products have.

    Args:
        layer: The QgsVectorLayer to read.
        field_name: Attribute holding the per-zone score (e.g.
            "_majority").

    Returns:
        A 1-D numpy array of the field's non-null, non-zero values.
    """
    field_index = layer.fields().indexFromName(field_name)
    if field_index < 0:
        return numpy.array([])
    values = [
        value
        for value in (feature.attribute(field_index) for feature in layer.getFeatures())
        if value is not None and value > 0
    ]
    return numpy.array(values, dtype=float)


def histogram_and_colors(values, palette: str) -> Tuple[List[int], List[str]]:
    """Bin values and look up the matching legend colour for each bar.

    One place both the report and the GUI sparkline call, so the
    colour-to-class mapping can never drift between the two.

    Args:
        values: A 1-D array-like of score values.
        palette: "likert" (plain 0-5 scale) or "by_population" (the
            1-15 enablement x population bivariate scale).

    Returns:
        (counts, hex_colors) - parallel lists, one entry per bar.
    """
    if palette == "by_population":
        counts = palette_histogram_from_values(values, len(GEOE3_BY_POPULATION_COLORS))
        colors = list(GEOE3_BY_POPULATION_COLORS.values())
    else:
        counts = score_histogram_from_values(values)
        colors = [SCORE_LEGEND_COLORS[score] for score in range(1, 6)]
    return counts, colors

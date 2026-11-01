# -*- coding: utf-8 -*-
"""📦 Analysis Report module.

This module contains functionality for analysis report.
"""

import json
import os
import tempfile
from datetime import datetime
from typing import Dict, List, Optional

import numpy
from qgis.core import (
    QgsFillSymbol,
    QgsLayout,
    QgsLayoutItemPicture,
    QgsLayoutItemShape,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsProject,
    QgsRasterLayer,
    QgsRenderContext,
    QgsSingleSymbolRenderer,
    QgsUnitTypes,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QRectF, Qt
from qgis.PyQt.QtGui import QColor, QImage, QPainter

from geest.core import sparkline_data
from geest.core.constants import GEOE3_BY_POPULATION_COLORS, SCORE_LEGEND_COLORS
from geest.core.settings import setting
from geest.utilities import log_message, resources_path

from .base_report import (
    CHARCOAL,
    CONTENT_W,
    CYAN,
    FOOTER_Y,
    GREY,
    HEADER_H,
    MARGIN,
    MIST,
    NAVY,
    RULE,
    WHITE,
    BaseReport,
    _flat_fill,
)
from .methodology import TECHNIQUES, nuance_for_analysis_mode, technique_for_indicator

# The five score classes used by every result map in this report
# (see resources/qml/analysis.qml): range, name, colour, significance.
SCORE_CLASSES = [
    (
        "0 – 1",
        "Very Low Enablement",
        "#d7191c",
        "Conditions offer little or no support for employment and " "entrepreneurship; major barriers dominate.",
    ),
    (
        "1 – 2",
        "Low Enablement",
        "#fdae61",
        "Support is limited and significant barriers remain across most " "measured factors.",
    ),
    (
        "2 – 3",
        "Moderately Enabling",
        "#ffffbf",
        "Some supportive conditions exist, but their coverage or quality " "is uneven.",
    ),
    (
        "3 – 4",
        "Enabling",
        "#bce1b8",
        "Conditions generally support access to employment and business " "opportunities.",
    ),
    (
        "4 – 5",
        "Highly Enabling",
        "#2c7bb6",
        "Strong, well-developed enabling conditions across the measured " "factors.",
    ),
]


class AnalysisReport(BaseReport):
    """
    A class to generate a PDF report from the analysis results.

    """

    def __init__(self, model_path: str, working_directory: Optional[str] = None, report_name="GeoE3 Analysis Report"):
        """
        Initialize the report.

        Args:
            model_path: Path to the model JSON file.
            working_directory: Path to the working directory containing the study area GeoPackage.
            report_name: The title to use for the report.
        """
        template_path = resources_path("resources", "qpt", "analysis_summary_report_template.qpt")
        admin0_name = self._admin0_name(working_directory)
        if admin0_name:
            report_name = f"{report_name} — {admin0_name}"
        super().__init__(template_path, report_name)

        self.report_name = report_name
        self.model_path = model_path
        self.working_directory = working_directory
        # Source of truth for _grid_column_score_histogram()'s sparklines -
        # the same GeoPackage every result raster was rasterised FROM.
        self.grid_gpkg_path = (
            os.path.join(working_directory, "study_area", "study_area.gpkg") if working_directory else None
        )
        self.temp_layers = []  # Track layers added to project for cleanup
        self.study_area_layer = None  # Will hold the study area outline layer

        # Load the study area outline layer if working_directory is provided
        if working_directory:
            self._load_study_area_layer()

        self.page_descriptions[
            "analysis_summary"
        ] = """
        This shows the relative elapsed time for each analysis step. The time is in minutes.
        """
        self.page_descriptions[
            "legend"
        ] = """
        Most maps in this report uses a colour scheme with classes ranging from 0 to
        5. This page explains what the colours mean and how the values are derived.
        """

    @staticmethod
    def _admin0_name(working_directory: Optional[str]) -> str:
        """Read the admin0 (country) name chosen during project setup.

        Project creation lets the user pick which field of their study
        area boundary layer holds the area's name (e.g. an "ADM0_EN"
        column); study_area_processing_task.py dissolves the input
        boundary by that field into
        study_area/boundaries_dissolved.gpkg, one feature (and that one
        field, plus GeoPackage's own integer "fid") per distinct value.
        Reads it by field TYPE (the first String field) rather than by
        name or position - the user could have picked any column name,
        and QGIS's own field list (unlike raw OGR's) includes "fid" as
        field 0, so position 0 is the row id, not the name.

        Args:
            working_directory: The project's working directory, or None.

        Returns:
            The admin0 name(s) found (joined with ", " if more than one
            distinct value was dissolved), or "" if the file, layer, or a
            usable field isn't there - callers should fall back to
            whatever title they already have.
        """
        if not working_directory:
            return ""
        gpkg_path = os.path.join(working_directory, "study_area", "boundaries_dissolved.gpkg")
        if not os.path.exists(gpkg_path):
            return ""
        layer = QgsVectorLayer(gpkg_path, "boundaries_dissolved", "ogr")
        if not layer.isValid():
            return ""
        name_field_index = next(
            (i for i, field in enumerate(layer.fields()) if field.typeName() == "String"),
            None,
        )
        if name_field_index is None:
            return ""
        names = []
        for feature in layer.getFeatures():
            value = feature.attribute(name_field_index)
            if value and str(value) not in names:
                names.append(str(value))
        return ", ".join(names)

    def cleanup(self):
        """
        Explicitly clean up temporary layers. Call this when done with the report,
        or use the context manager pattern.
        """
        if self._cleanup_done:
            return
        # temp_layers are never registered with QgsProject (see
        # _load_raster/_load_vector/_load_study_area_layer) - just drop the
        # references so they can be garbage collected.
        self.temp_layers = []
        # Rasterised subnational score matrix pages (see
        # _render_score_matrix_page_image()) - temp PNG files on disk,
        # not project layers.
        for path in getattr(self, "_temp_matrix_image_paths", []):
            try:
                os.remove(path)
            except OSError:
                pass
        self._temp_matrix_image_paths = []
        super().cleanup()

    def _load_study_area_layer(self):
        """
        Load the study area outline layer from the GeoPackage.
        """
        gpkg_path = self.grid_gpkg_path
        if not gpkg_path or not os.path.exists(gpkg_path):
            log_message(f"Study area GeoPackage not found at {gpkg_path}")
            return

        # Try to load study_area_clip_polygons first, fall back to study_area_polygons
        for layer_name in ["study_area_clip_polygons", "study_area_polygons"]:
            uri = f"{gpkg_path}|layername={layer_name}"
            layer = QgsVectorLayer(uri, f"Study Area ({layer_name})", "ogr")
            if layer.isValid():
                self.study_area_layer = layer
                # Outline only: the default study-area style has a solid fill
                # which, drawn over the result raster, blanks out the map
                # ("white interior with a black outline"). The report must
                # show the same styled raster the model tree shows, with just
                # a thin boundary on top.
                symbol = QgsFillSymbol.createSimple(
                    {
                        "color": "0,0,0,0",
                        "outline_color": "51,51,51,255",
                        "outline_width": "0.4",
                        "outline_style": "solid",
                    }
                )
                layer.setRenderer(QgsSingleSymbolRenderer(symbol))
                # Kept alive via temp_layers (GC only) - report generation
                # runs on a QgsTask worker thread, and QgsProject.addMapLayer()
                # mutates the GUI-thread-only layer registry, which crashes
                # intermittently (observed as a Windows access violation).
                # QgsLayoutItemMap.setLayers() renders directly from the
                # layer object; project membership was never required.
                self.temp_layers.append(layer)
                log_message(f"Loaded study area outline from {layer_name}")
                break
            else:
                log_message(f"Could not load study area layer: {layer_name}")

    def create_layout(self):
        """
        Create a QGIS layout (report) that includes a title, summary statistics,
        and individual pages for each indicator.
        """
        project = QgsProject.instance()
        self.title = "Analysis Report"
        self.layout = QgsLayout(project)
        self.layout.initializeDefaults()
        self.load_template()
        self.style_cover_page()

        # Credits sit directly behind the cover so funders and developers
        # get a designed, prominent home.
        self.make_credits_page(current_page=1)

        # Explain the colour scheme before showing any maps.
        self.make_legend_page(current_page=2)

        # The "by population" bivariate scale is a different scheme
        # entirely - explain it on its own page, before any map that
        # uses it.
        self.make_by_population_legend_page(current_page=3)

        # Then the analysis overview and the dimension/factor pages.
        current_page = self.create_detail_pages(current_page=4)

        # Insights: patterns in the analysis grid beyond the score
        # itself - what's limiting low-scoring cells, settlement/hazard
        # effects, factor correlations.
        current_page = self.create_insights_pages(current_page)

        # Methodology and weightings live near the end, after the maps
        # and insights content but before the purely technical
        # bookkeeping pages - the "how was this calculated" answer a
        # reader looks for once they've seen the results.
        current_page = self.make_methodology_pages(current_page)
        current_page = self.make_scoring_weights_page(current_page)

        # Processing times live at the back of the report — they are
        # technical bookkeeping, not analysis content.
        self.make_page(
            title="Processing Times",
            description_key="analysis_summary",
            current_page=current_page,
            show_header_and_footer=True,
        )
        bottom_y = self.create_execution_time_layout(
            entries=self.extract_execution_times_with_colors(),
            page=current_page,
        )
        total_minutes = self._total_analysis_duration_minutes()
        if total_minutes is not None:
            self._draw_total_duration_block(total_minutes, bottom_y + 6, current_page)
        current_page += 1

        # The study area summary closes the report - readers who want to
        # judge the analysis's resolution and scope land here last.
        self.make_study_area_summary_page(current_page=current_page)
        current_page += 1

    def make_legend_page(self, current_page: int) -> None:
        """Add the legend page: the score colour scheme and what it means.

        A segmented 0-5 colour bar mirrors the ramp used on every result
        map (resources/qml/analysis.qml), followed by one row per class
        explaining its significance, and a note on how scores are derived.
        """
        self.make_page(
            title="Reading the Maps",
            description_key="legend",
            current_page=current_page,
            show_header_and_footer=True,
        )
        # Segmented colour bar with 0-5 tick labels.
        bar_y = HEADER_H + 26
        bar_h = 10
        segment_w = CONTENT_W / len(SCORE_CLASSES)
        # Hairline backing keeps the palest class visible against the page.
        self._rect(MARGIN - 0.3, bar_y - 0.3, CONTENT_W + 0.6, bar_h + 0.6, RULE, current_page)
        for i, (_, _, colour, _) in enumerate(SCORE_CLASSES):
            self._rect(MARGIN + i * segment_w, bar_y, segment_w, bar_h, QColor(colour), current_page)
        for i in range(len(SCORE_CLASSES) + 1):
            self._label(
                str(i),
                MARGIN + i * segment_w - 10,
                bar_y + bar_h + 1.5,
                20,
                5,
                current_page,
                size=8.5,
                color=GREY,
                halign=Qt.AlignmentFlag.AlignHCenter,
            )

        # One row per class: swatch, range and name, significance.
        row_top = bar_y + bar_h + 14
        row_pitch = 23
        for i, (score_range, name, colour, meaning) in enumerate(SCORE_CLASSES):
            y = row_top + i * row_pitch
            self._rect(MARGIN - 0.3, y - 0.3, 22.6, 14.6, RULE, current_page)
            self._rect(MARGIN, y, 22, 14, QColor(colour), current_page)
            self._label(
                f"{score_range}   {name}",
                MARGIN + 28,
                y,
                CONTENT_W - 28,
                7,
                current_page,
                size=11.5,
                color=NAVY,
                bold=True,
            )
            self._label(
                meaning,
                MARGIN + 28,
                y + 7,
                CONTENT_W - 28,
                7,
                current_page,
                size=9.5,
                color=GREY,
            )

        # How the values are derived.
        note_y = row_top + len(SCORE_CLASSES) * row_pitch + 6
        note_h = 42
        self._rect(MARGIN, note_y, CONTENT_W, note_h, MIST, current_page)
        self._rect(MARGIN, note_y, 2.2, note_h, CYAN, current_page)
        self._label(
            "Score calculations",
            MARGIN + 8,
            note_y + 4.5,
            CONTENT_W - 16,
            7,
            current_page,
            size=12,
            color=NAVY,
            bold=True,
        )
        note_body = self._label(
            "<p>For each indicator, we score each analysis grid cell from 0 to 5. "
            "Indicator scores combine into factor scores. Factor scores combine into "
            "dimension scores. The dimension scores are then combined into the overall "
            "GeoE3 score. Each time we combine scores, they are weighted using the "
            "weights configured in the model. Blank cells mean that cell is outside the "
            "study area or has no data. A score of 0 can also mean the measured service "
            "is out of reach. For example, locations with no road network access might "
            "score 0.</p>",
            MARGIN + 8,
            note_y + 13,
            CONTENT_W - 16,
            note_h - 17,
            current_page,
            size=9.5,
            color=CHARCOAL,
            html=True,
        )
        note_body.setHAlign(Qt.AlignmentFlag.AlignJustify)

    def make_by_population_legend_page(self, current_page: int) -> None:
        """Add a second legend page explaining the 15-class "by
        population" bivariate scale (resources/qml/
        geoe3_by_population_score.qml): every one of the 5 plain
        enablement classes crossed with 3 population tercile classes -
        a different scheme entirely from the 0-5 scale make_legend_page()
        explains, used by every "By population" map in the report.
        """
        self.page_descriptions["by_population_legend"] = (
            "An enablement score in isolation does not show whether a low scoring "
            "place is home to only a few people or a large, underserved population. "
            "We use a bivariate scale to cross reference each enablement class with "
            "how many people live there. This allows places most in need of "
            "intervention and that are home to the most people to stand out."
        )
        self.make_page(
            title="Reading the By-Population Maps",
            description_key="by_population_legend",
            current_page=current_page,
            show_header_and_footer=True,
        )

        population_labels = ["Low", "Medium", "High"]
        enablement_labels = [name for _, name, _, _ in SCORE_CLASSES]
        n_cols = len(enablement_labels)
        n_rows = len(population_labels)

        grid_x = MARGIN + 24
        grid_y = HEADER_H + 36
        cell_w = (CONTENT_W - 24) / n_cols
        cell_h = 16.0
        gap = 0.6

        for col in range(n_cols):
            for row in range(n_rows):
                # Classes run enablement-major, population-minor (see
                # geoe3_by_population_vector_score.qml): value 1 is
                # "very low enablement, low population", value 3 is
                # "very low enablement, high population", value 4 moves
                # to the next enablement class, and so on.
                value = col * n_rows + row + 1
                x = grid_x + col * cell_w
                # Row 0 ("Low" population) sits at the BOTTOM of the grid.
                y = grid_y + (n_rows - 1 - row) * cell_h
                colour = QColor(GEOE3_BY_POPULATION_COLORS[value])
                self._rect(x, y, cell_w - gap, cell_h - gap, colour, current_page)

        for row, population_name in enumerate(population_labels):
            y = grid_y + (n_rows - 1 - row) * cell_h
            self._label(
                population_name,
                MARGIN,
                y + (cell_h - gap) / 2 - 3,
                22,
                6,
                current_page,
                size=9,
                color=GREY,
                halign=Qt.AlignmentFlag.AlignRight,
            )

        label_y = grid_y + n_rows * cell_h + 2
        for col, enablement_name in enumerate(enablement_labels):
            self._label(
                enablement_name,
                grid_x + col * cell_w - 4,
                label_y,
                cell_w + 8,
                10,
                current_page,
                size=7.5,
                color=GREY,
                halign=Qt.AlignmentFlag.AlignHCenter,
            )

        self._label(
            "Population density",
            MARGIN,
            grid_y - 8,
            CONTENT_W,
            6,
            current_page,
            size=9,
            color=NAVY,
            bold=True,
        )
        self._label(
            "Enablement",
            grid_x,
            label_y + 11,
            CONTENT_W - 24,
            6,
            current_page,
            size=9,
            color=NAVY,
            bold=True,
        )

        note_y = label_y + 21
        note_h = 38
        self._rect(MARGIN, note_y, CONTENT_W, note_h, MIST, current_page)
        self._rect(MARGIN, note_y, 2.2, note_h, CYAN, current_page)
        self._label(
            "Calculation of the by-population score",
            MARGIN + 8,
            note_y + 4.5,
            CONTENT_W - 16,
            7,
            current_page,
            size=12,
            color=NAVY,
            bold=True,
        )
        note_body = self._label(
            "<p>For each grid cell, the plain 0-5 score is combined with its "
            "population count, split into three classes (low, medium, high). We do "
            "this across the whole study area to categorise each cell into one of 15 "
            "classes. The colour ramp goes from deep red (low enablement, low "
            "population) to light blue (high enablement, high population).</p>",
            MARGIN + 8,
            note_y + 13,
            CONTENT_W - 16,
            note_h - 17,
            current_page,
            size=9.5,
            color=CHARCOAL,
            html=True,
        )
        note_body.setHAlign(Qt.AlignmentFlag.AlignJustify)

    def _load_raster(self, layer_uri: str, title: str) -> Optional[QgsRasterLayer]:
        """Load (and cache) a raster result layer, or None when unavailable.

        Validity is checked BEFORE any page is created, so an unreadable
        result can never produce a blank page.
        """
        if not layer_uri:
            return None
        if not hasattr(self, "_raster_cache"):
            self._raster_cache = {}
        if layer_uri in self._raster_cache:
            return self._raster_cache[layer_uri]
        layer = QgsRasterLayer(layer_uri, title)
        if not layer.isValid():
            log_message(f"Layer {layer_uri} is invalid — omitted from report.", tag="GeoE3")
            self._raster_cache[layer_uri] = None
            return None
        self.temp_layers.append(layer)
        self._raster_cache[layer_uri] = layer
        return layer

    def _load_vector(self, layer_uri: str, title: str) -> Optional[QgsVectorLayer]:
        """Load (and cache) a vector result layer with its sibling .qml
        style, or None when unavailable. Mirrors _load_raster() for the
        subnational aggregation products: plain polygons with no
        embedded symbology, whose categorized/graduated colour scheme
        (matching every other product's score ramp) lives in a .qml file
        sitting next to the GeoPackage (see
        subnational_aggregation_processor.py).
        """
        if not layer_uri:
            return None
        if not hasattr(self, "_vector_cache"):
            self._vector_cache = {}
        if layer_uri in self._vector_cache:
            return self._vector_cache[layer_uri]
        layer = QgsVectorLayer(layer_uri, title, "ogr")
        if not layer.isValid():
            log_message(f"Layer {layer_uri} is invalid — omitted from report.", tag="GeoE3")
            self._vector_cache[layer_uri] = None
            return None
        gpkg_path = layer_uri.split("|", 1)[0]
        qml_path = os.path.splitext(gpkg_path)[0] + ".qml"
        if os.path.exists(qml_path):
            layer.loadNamedStyle(qml_path)
            AnalysisReport._thin_vector_outlines(layer)
        self.temp_layers.append(layer)
        self._vector_cache[layer_uri] = layer
        return layer

    #: Outline width (mm) for subnational aggregation report maps - the
    #: style's normal 0.26mm outline is sized for the interactive QGIS
    #: canvas, where only a handful of zones are usually on screen at
    #: once. A report page packs hundreds of zones into 180mm, where
    #: that same width eats into a large share of each tiny zone's
    #: visible area, obscuring the fill colour it's meant to show.
    REPORT_VECTOR_OUTLINE_WIDTH_MM = 0.08

    @staticmethod
    def _thin_vector_outlines(layer: QgsVectorLayer, width_mm: float = REPORT_VECTOR_OUTLINE_WIDTH_MM) -> None:
        """Thin every symbol's outline for report rendering only - the
        layer's own .qml style file (used by the interactive map too) is
        left untouched. See REPORT_VECTOR_OUTLINE_WIDTH_MM for why.
        """
        renderer = layer.renderer()
        if renderer is None:
            return
        for symbol in renderer.symbols(QgsRenderContext()):
            for i in range(symbol.symbolLayerCount()):
                symbol_layer = symbol.symbolLayer(i)
                if hasattr(symbol_layer, "setStrokeWidth"):
                    symbol_layer.setStrokeWidth(width_mm)

    @staticmethod
    def _read_vector_field_values(layer: QgsVectorLayer, field_name: str):
        """Read a vector layer's own attribute values directly - the
        subnational aggregation products' authoritative per-zone score
        (one administrative zone per feature), with no study_area_grid
        column backing them the way per-cell products have.

        Delegates to geest.core.sparkline_data, shared with the item
        info panel's Sparkline page so both read/bin identically.

        Args:
            layer: The vector layer to read.
            field_name: Attribute holding the per-zone score (e.g.
                "_majority").

        Returns:
            A 1-D numpy array of the field's non-null, non-zero values.
        """
        return sparkline_data.read_vector_field_values(layer, field_name)

    def _map_layers(self, layer: QgsRasterLayer) -> list:
        """Raster plus the study area outline when available."""
        layers = [layer]
        if self.study_area_layer:
            layers.append(self.study_area_layer)
        return layers

    def _add_map_page(
        self,
        title: str,
        description_key: str,
        layer_uri: str,
        current_page: int,
        minimaps: Optional[list] = None,
        grid_column: Optional[str] = None,
        palette: str = "likert",
    ) -> bool:
        """Add a page with a large map and an optional grid of minimaps.

        Args:
            title: The title for the page.
            description_key: Key for the page description in self.page_descriptions.
            layer_uri: Path to the raster layer file.
            current_page: The current page number.
            minimaps: Optional list of (caption, QgsRasterLayer, grid_column,
                palette) tuples laid out as a grid beneath the main map.
                grid_column is the study_area_grid column backing that
                layer, or None if it isn't on a scale a sparkline can
                usefully show.
            grid_column: study_area_grid column backing the main map
                itself, or None to skip its own corner sparkline.
            palette: "likert" (plain 0-5 scale) or "by_population" (the
                1-15 enablement x population bivariate scale) - which
                colour scheme grid_column's sparkline (both the main map's
                and every minimap's) should use.

        Returns:
            bool: True if the page was added, False otherwise.
        """
        layer = self._load_raster(layer_uri, title)
        if layer is None:
            log_message(f"No usable layer for '{title}', skipping page", tag="GeoE3")
            return False

        self.make_page(
            title=title,
            description_key=description_key,
            current_page=current_page,
            show_header_and_footer=True,
        )

        minimaps = [m for m in (minimaps or []) if m[1] is not None]
        main_h = 105.0 if minimaps else 200.0
        main_x, main_y, main_w = 15, 52, 180
        self.make_map(
            layers=self._map_layers(layer),
            current_page=current_page,
            crs=layer.crs(),
            x=main_x,
            y=main_y,
            map_width_mm=main_w,
            map_height_mm=main_h,
        )
        if grid_column:
            self._draw_main_map_sparkline(
                column_name=grid_column,
                palette=palette,
                map_x=main_x,
                map_y=main_y,
                map_w=main_w,
                map_h=main_h,
                page=current_page,
            )
        if minimaps:
            # 12 mm clearance leaves room for the main map's outside-frame
            # coordinate annotations.
            self._add_minimap_grid(minimaps, current_page, top=main_y + main_h + 12)
        return True

    def _add_vector_map_page(
        self,
        title: str,
        description_key: str,
        layer_uri: str,
        current_page: int,
        score_field: str = "_majority",
        palette: str = "likert",
    ) -> bool:
        """Add a page for a subnational-aggregation vector product: one
        polygon per administrative zone (the boundary the user chose
        during project setup), coloured by its majority score, with the
        same inset sparkline treatment _add_map_page() gives raster
        products.

        Args:
            title: The title for the page.
            description_key: Key for the page description in self.page_descriptions.
            layer_uri: Path to the vector GeoPackage layer, e.g.
                "<path>.gpkg|layername=<name>".
            current_page: The current page number.
            score_field: Attribute holding the per-zone majority score.
            palette: "likert" (plain 0-5 scale) or "by_population" (the
                1-15 enablement x population bivariate scale) - which
                colour scheme the inset sparkline should use.

        Returns:
            bool: True if the page was added, False otherwise.
        """
        layer = self._load_vector(layer_uri, title)
        if layer is None:
            log_message(f"No usable layer for '{title}', skipping page", tag="GeoE3")
            return False

        self.make_page(
            title=title,
            description_key=description_key,
            current_page=current_page,
            show_header_and_footer=True,
        )

        # Unlike the raster pages, the study area outline isn't overlaid
        # here: the zone polygons already tile the whole study area, so
        # it would be redundant, and it often sits in a different CRS
        # than the aggregation layer (zones come from a user-chosen
        # boundary layer, not the analysis grid) - make_map() combines
        # layer extents without reprojecting, so mixing CRSes there
        # silently produces a near-empty page.
        main_x, main_y, main_w, main_h = 15, 52, 180, 200.0
        self.make_map(
            layers=[layer],
            current_page=current_page,
            crs=layer.crs(),
            x=main_x,
            y=main_y,
            map_width_mm=main_w,
            map_height_mm=main_h,
        )
        values = self._read_vector_field_values(layer, score_field)
        if values.size:
            self._draw_main_map_sparkline_for_values(
                values=values,
                palette=palette,
                map_x=main_x,
                map_y=main_y,
                map_w=main_w,
                map_h=main_h,
                page=current_page,
            )
        return True

    @staticmethod
    def _grid_column_name(role: str, item_id: str) -> str:
        """Mirror JsonTreeItem.gridColumnName()'s sanitisation for report
        code that only has the model dict (not a JsonTreeItem) to work
        from: lower-case, space/hyphen -> underscore, 63-char GeoPackage
        field name limit, with the dim_/fac_ role prefix workflows use.
        """
        raw_id = (item_id or "").lower().replace(" ", "_").replace("-", "_")
        if role == "dimension":
            return f"dim_{raw_id}"[:63]
        if role == "factor":
            return f"fac_{raw_id}"[:63]
        return raw_id[:63]

    def _read_grid_column_values(self, column_name: str):
        """Read study_area_grid's own column values directly from the
        GeoPackage - the same values every result raster was rasterised
        from, and the authoritative source for them (the raster is a
        resampled render, not the data itself).

        Exact 0/NULL is dropped: a large share of cells carry a literal 0
        (outside the populated/opportunity area, not a genuine "very low"
        score), and counting it would flatten the distribution any
        sparkline built from this exists to show.

        Delegates to geest.core.sparkline_data, shared with the item
        info panel's Sparkline page so both read/bin identically.

        Args:
            column_name: study_area_grid column to read.

        Returns:
            A 1-D numpy array of the column's non-null, non-zero values.
        """
        return sparkline_data.read_grid_column_values(self.grid_gpkg_path, column_name)

    def _read_grid_columns(self, column_names: list) -> list:
        """Fetch several study_area_grid columns at once as a list of
        row tuples (one row per grid cell, in column_names order) -
        unlike _read_grid_column_values(), which reads one column in
        isolation and can't preserve the per-cell relationship between
        columns some insights need (e.g. "which of these columns is
        lowest for this cell").

        Only rows where every requested column is non-null and > 0 are
        returned - the same "exclude 0/NULL" convention every other grid
        read in this file follows (0 typically means outside the
        populated/opportunity area, not a genuine low score).

        Returns:
            A list of row tuples, or [] if the grid isn't available or
            no column name is safe to use.
        """
        if not self.grid_gpkg_path or not os.path.exists(self.grid_gpkg_path):
            return []
        import sqlite3

        from geest.core.grid_column_utils import _quote_sql_identifier

        try:
            quoted = [_quote_sql_identifier(c) for c in column_names]
        except ValueError as error:
            log_message(f"Refusing to read grid columns: {error}", tag="GeoE3")
            return []

        where_sql = " AND ".join(f"{c} IS NOT NULL AND {c} > 0" for c in quoted)
        query = f"SELECT {', '.join(quoted)} FROM study_area_grid WHERE {where_sql}"  # nosec B608
        try:
            connection = sqlite3.connect(self.grid_gpkg_path)
            try:
                rows = connection.execute(query).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as error:
            log_message(f"Could not read grid columns {column_names}: {error}", tag="GeoE3")
            return []
        return rows

    def _read_grid_columns_with_gaps(self, column_names: list):
        """Fetch several study_area_grid columns at once with 0/NULL
        preserved as NaN rather than dropping the row - unlike
        _read_grid_columns(), which requires EVERY requested column to
        be valid for a row to be kept. With many columns of very
        different spatial coverage (e.g. 16 factors, one covering 175k
        cells and another covering 200), requiring all of them at once
        can leave zero rows even though plenty of PAIRWISE overlap
        exists between any two columns.

        Returns:
            An (n_rows, n_columns) numpy array, or an empty array if the
            grid isn't available or no column name is safe to use.
        """
        if not self.grid_gpkg_path or not os.path.exists(self.grid_gpkg_path):
            return numpy.empty((0, len(column_names)))
        import sqlite3

        from geest.core.grid_column_utils import _quote_sql_identifier

        try:
            quoted = [_quote_sql_identifier(c) for c in column_names]
        except ValueError as error:
            log_message(f"Refusing to read grid columns: {error}", tag="GeoE3")
            return numpy.empty((0, len(column_names)))

        query = f"SELECT {', '.join(quoted)} FROM study_area_grid"  # nosec B608
        try:
            connection = sqlite3.connect(self.grid_gpkg_path)
            try:
                rows = connection.execute(query).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as error:
            log_message(f"Could not read grid columns {column_names}: {error}", tag="GeoE3")
            return numpy.empty((0, len(column_names)))

        data = numpy.array(rows, dtype=float)
        # 0 means "outside the populated/opportunity area", the same
        # exclusion convention every other grid read in this file
        # follows - treat it the same as NULL (already NaN from SQLite).
        data[data == 0] = numpy.nan
        return data

    def _grid_column_score_histogram(self, column_name: str) -> list:
        """Count study_area_grid's own column values per QGIS's 5-class
        DISCRETE colour-ramp boundaries (see resources/qml/analysis.qml):
        (0,1], (1,2], (2,3], (3,4], (4,5] - matching the colours actually
        painted on the map exactly. Only valid for columns confirmed to
        be on the plain 0-5 scale (see _add_minimap_grid()'s palette
        parameter) - a bivariate product like "by population" uses a
        completely different scheme (see _grid_column_palette_histogram).

        Args:
            column_name: study_area_grid column to read.

        Returns:
            list: Five counts, one per QML class, in (0,1] .. (4,5] order.
        """
        return AnalysisReport._score_histogram_from_values(self._read_grid_column_values(column_name))

    def _grid_column_palette_histogram(self, column_name: str, n_classes: int) -> list:
        """Count study_area_grid's own column values per EXACT integer
        class 1..n_classes, matching a PalettedRasterRenderer's
        unique-value scheme (e.g. geoe3_by_population_score.qml's 15-class
        enablement x population bivariate palette) - unlike
        _grid_column_score_histogram()'s DISCRETE range bucketing, each
        class here is a single exact value, not a (lower, upper] interval.

        Args:
            column_name: study_area_grid column to read.
            n_classes: Number of palette classes (e.g. 15).

        Returns:
            list: n_classes counts, for values 1..n_classes in order.
        """
        return AnalysisReport._palette_histogram_from_values(self._read_grid_column_values(column_name), n_classes)

    @staticmethod
    def _score_histogram_from_values(values) -> list:
        """Count values per QGIS's 5-class DISCRETE colour-ramp boundaries
        (see resources/qml/analysis.qml): (0,1], (1,2], (2,3], (3,4], (4,5]
        - matching the colours actually painted on the map exactly. Only
        valid for values confirmed to be on the plain 0-5 scale - a
        bivariate product like "by population" uses a completely
        different scheme (see _palette_histogram_from_values()). Shared by
        both study_area_grid columns (per-cell) and subnational
        aggregation vector fields (per-zone), which carry the same 0-5
        score but from different sources.

        Delegates to geest.core.sparkline_data, shared with the item
        info panel's Sparkline page so both read/bin identically.

        Returns:
            list: Five counts, one per QML class, in (0,1] .. (4,5] order.
        """
        return sparkline_data.score_histogram_from_values(values)

    @staticmethod
    def _palette_histogram_from_values(values, n_classes: int) -> list:
        """Count values per EXACT integer class 1..n_classes, matching a
        PalettedRasterRenderer's unique-value scheme (e.g.
        geoe3_by_population_score.qml's 15-class enablement x population
        bivariate palette) - unlike _score_histogram_from_values()'s
        DISCRETE range bucketing, each class here is a single exact
        value, not a (lower, upper] interval.

        Delegates to geest.core.sparkline_data, shared with the item
        info panel's Sparkline page so both read/bin identically.

        Returns:
            list: n_classes counts, for values 1..n_classes in order.
        """
        return sparkline_data.palette_histogram_from_values(values, n_classes)

    def _draw_sparkline_for_values(self, values, palette: str, x: float, y: float, w: float, h: float, page: int):
        """Draw a score-distribution sparkline for an already-read array
        of values, coloured with the same ramp the result map itself uses
        for that product, so the bars read as "more of this colour"
        rather than needing a separate legend.

        Args:
            palette: "likert" (plain 0-5 scale) or "by_population" (the
                1-15 enablement x population bivariate scale).
        """
        if palette == "by_population":
            counts = AnalysisReport._palette_histogram_from_values(values, len(GEOE3_BY_POPULATION_COLORS))
            colors = [QColor(color) for color in GEOE3_BY_POPULATION_COLORS.values()]
        else:
            counts = AnalysisReport._score_histogram_from_values(values)
            colors = [QColor(SCORE_LEGEND_COLORS[score]) for score in range(1, 6)]
        self._draw_sparkline(counts, colors, x, y, w, h, page)

    def _draw_sparkline_for_column(
        self, column_name: str, palette: str, x: float, y: float, w: float, h: float, page: int
    ):
        """Draw a score-distribution sparkline for one study_area_grid
        column - see _draw_sparkline_for_values().

        Args:
            column_name: study_area_grid column to read.
            palette: "likert" (plain 0-5 scale) or "by_population" (the
                1-15 enablement x population bivariate scale).
        """
        self._draw_sparkline_for_values(self._read_grid_column_values(column_name), palette, x, y, w, h, page)

    @staticmethod
    def _sparkline_inset_geometry(map_x: float, map_y: float, map_w: float, map_h: float) -> tuple:
        """Position and size for a sparkline inset into a map's own
        bottom-right corner, shared by both the grid-column and the
        vector-field sparkline insets.
        """
        margin = 4.0
        w, h = 36.0, 10.0
        x = map_x + map_w - w - margin
        y = map_y + map_h - h - margin
        return x, y, w, h

    def _draw_main_map_sparkline(
        self,
        column_name: str,
        palette: str,
        map_x: float,
        map_y: float,
        map_w: float,
        map_h: float,
        page: int,
    ) -> None:
        """Inset a small sparkline into the main map's own bottom-right
        corner, backed by a translucent white panel so the bars stay
        legible over whatever colours the map itself shows underneath.
        """
        x, y, w, h = self._sparkline_inset_geometry(map_x, map_y, map_w, map_h)
        pad = 1.5
        self._rect(x - pad, y - pad, w + 2 * pad, h + 2 * pad, WHITE, page, opacity=0.78)
        self._draw_sparkline_for_column(column_name, palette, x, y, w, h, page)

    def _draw_main_map_sparkline_for_values(
        self,
        values,
        palette: str,
        map_x: float,
        map_y: float,
        map_w: float,
        map_h: float,
        page: int,
    ) -> None:
        """Inset a small sparkline into the main map's own bottom-right
        corner for an already-read array of values - see
        _draw_main_map_sparkline(), used for the subnational aggregation
        vector products, which have no study_area_grid column backing
        them.
        """
        x, y, w, h = self._sparkline_inset_geometry(map_x, map_y, map_w, map_h)
        pad = 1.5
        self._rect(x - pad, y - pad, w + 2 * pad, h + 2 * pad, WHITE, page, opacity=0.78)
        self._draw_sparkline_for_values(values, palette, x, y, w, h, page)

    def _add_minimap_grid(
        self,
        minimaps: list,
        current_page: int,
        top: float,
        columns: int = 4,
        bottom: float = 280.0,
    ) -> None:
        """Lay out (caption, layer, grid_column, palette) tuples as a
        captioned minimap grid. Each is followed by a small sparkline of
        its score distribution (excluding 0 - see
        _grid_column_score_histogram()/_grid_column_palette_histogram())
        when grid_column is set - some products (e.g. the binary
        opportunities mask) aren't on any scale a sparkline can usefully
        show, and pass grid_column=None to skip it rather than render a
        meaningless chart.
        """
        gap = 5.0
        cell_w = (180.0 - (columns - 1) * gap) / columns
        caption_h = cell_w + 7  # square map face + caption strip
        sparkline_h = 8.0
        has_any_sparkline = any(grid_column for _caption, _layer, grid_column, _palette in minimaps)
        cell_h = caption_h + sparkline_h if has_any_sparkline else caption_h
        max_rows = max(1, int((bottom - top + gap) // (cell_h + gap)))
        capacity = max_rows * columns
        if len(minimaps) > capacity:
            log_message(
                f"Minimap grid clipped to {capacity} of {len(minimaps)} entries on page {current_page}",
                tag="GeoE3",
            )
            minimaps = minimaps[:capacity]
        for index, (caption, layer, grid_column, palette) in enumerate(minimaps):
            row, col = divmod(index, columns)
            x = 15 + col * (cell_w + gap)
            y = top + row * (cell_h + gap)
            self.make_minimap(
                caption=caption,
                layers=self._map_layers(layer),
                crs=layer.crs(),
                current_page=current_page,
                x=x,
                y=y,
                w=cell_w,
                h=caption_h,
            )
            if grid_column:
                self._draw_sparkline_for_column(
                    column_name=grid_column,
                    palette=palette,
                    x=x,
                    y=y + caption_h,
                    w=cell_w,
                    h=sparkline_h,
                    page=current_page,
                )

    def _has_used_indicators(self, factor: dict) -> bool:
        """Check if a factor has any indicators that are not 'Do Not Use'.

        Args:
            factor: Factor dictionary from the model.

        Returns:
            bool: True if at least one indicator is used.
        """
        for indicator in factor.get("indicators", []):
            if indicator.get("analysis_mode", "") != "Do Not Use":
                return True
        return False

    def _has_used_factors(self, dimension: dict) -> bool:
        """Check if a dimension has any factors with used indicators.

        Args:
            dimension: Dimension dictionary from the model.

        Returns:
            bool: True if at least one factor has used indicators.
        """
        for factor in dimension.get("factors", []):
            if self._has_used_indicators(factor):
                return True
        return False

    def create_detail_pages(self, current_page: int = 1):
        """Iterate over dimensions, factors, and indicators to create detail pages.

        Args:
            current_page: The current page number to start from. Incremented for each new page.
        """

        with open(self.model_path, "r", encoding="utf-8") as f:
            model = json.load(f)

        # --- Analysis overview: the main GeoE3 score map on top, then the
        # dimension aggregates as minimaps, then any additional analysis
        # products (population/mask variants) as further minimaps.
        self.page_descriptions["analysis_overview"] = (
            "Overall GeoE3 score, with the aggregated score for each "
            "dimension and any derived analysis products shown below."
        )
        main_uri = model.get("geoe3_score_ghsl_masked_result_file") or model.get("result_file")
        main_grid_column = "geoe3_masked" if model.get("geoe3_score_ghsl_masked_result_file") else "geoe3"
        # grid_column is None for products not on any scale a sparkline can
        # usefully show: the "x opportunities" products are a combination
        # of two columns with no single grid column of their own, and the
        # opportunities mask itself is binary, not a 1-5 or 1-15 score.
        product_keys = [
            ("result_file", "GeoE3 score", "geoe3", "likert"),
            ("geoe3_score_ghsl_masked_result_file", "GHSL masked", "geoe3_masked", "likert"),
            ("geoe3_by_population", "By population", "geoe3_by_population", "by_population"),
            (
                "geoe3_score_by_population_ghsl_masked_result_file",
                "By population (GHSL)",
                "geoe3_by_population_masked",
                "by_population",
            ),
            ("opportunities_mask_result_file", "Opportunities mask", None, None),
        ]
        dimension_minimaps = [
            (
                dimension.get("name", ""),
                self._load_raster(dimension.get("result_file"), dimension.get("name", "")),
                self._grid_column_name("dimension", dimension.get("id", "")),
                "likert",
            )
            for dimension in model.get("dimensions", [])
            if self._has_used_factors(dimension)
        ]
        product_minimaps = [
            (label, self._load_raster(model.get(key), label), grid_column, palette)
            for key, label, grid_column, palette in product_keys
            if model.get(key) and model.get(key) != main_uri
        ]
        if self._add_map_page(
            "Analysis Overview",
            "analysis_overview",
            main_uri,
            current_page,
            minimaps=dimension_minimaps + product_minimaps,
            grid_column=main_grid_column,
            palette="likert",
        ):
            current_page += 1

        # --- One page per dimension: its map + a grid of factor minimaps
        for dimension in model.get("dimensions", []):
            dim_name = dimension.get("name", "")

            if not self._has_used_factors(dimension):
                log_message(f"Skipping dimension '{dim_name}' - no used indicators", tag="GeoE3")
                continue

            used_factors = [factor for factor in dimension.get("factors", []) if self._has_used_indicators(factor)]

            self.page_descriptions[dim_name] = dimension.get(
                "description", f"Aggregated analysis for dimension: {dim_name}"
            )
            # A dimension with a single factor aggregates to the same surface
            # as that factor — a one-cell minimap grid would just repeat the
            # main map, so skip it.
            factor_minimaps = (
                [
                    (
                        factor.get("name", ""),
                        self._load_raster(factor.get("result_file"), factor.get("name", "")),
                        self._grid_column_name("factor", factor.get("id", "")),
                        "likert",
                    )
                    for factor in used_factors
                ]
                if len(used_factors) > 1
                else []
            )
            if self._add_map_page(
                f"{dim_name} Dimension",
                dim_name,
                dimension.get("result_file"),
                current_page,
                minimaps=factor_minimaps,
                grid_column=self._grid_column_name("dimension", dimension.get("id", "")),
                palette="likert",
            ):
                current_page += 1

            # --- One page per factor: its map + a grid of indicator minimaps
            for factor in used_factors:
                factor_name = factor.get("name", "")
                self.page_descriptions[factor_name] = factor.get(
                    "description", f"Aggregated analysis for factor: {factor_name}"
                )
                used_indicators = [
                    indicator
                    for indicator in factor.get("indicators", [])
                    if indicator.get("analysis_mode", "") != "Do Not Use"
                ]
                # A factor with a single indicator produces the same surface
                # as that indicator — skip the redundant one-cell grid.
                indicator_minimaps = (
                    [
                        (
                            indicator.get("indicator", ""),
                            self._load_raster(indicator.get("result_file"), indicator.get("indicator", "")),
                            self._grid_column_name("indicator", indicator.get("id", "")),
                            "likert",
                        )
                        for indicator in used_indicators
                    ]
                    if len(used_indicators) > 1
                    else []
                )
                if self._add_map_page(
                    f"{factor_name}",
                    factor_name,
                    factor.get("result_file"),
                    current_page,
                    minimaps=indicator_minimaps,
                    grid_column=self._grid_column_name("factor", factor.get("id", "")),
                    palette="likert",
                ):
                    current_page += 1

        # --- Subnational aggregation: one page per product, each a
        # vector GeoPackage (one polygon per administrative zone the
        # user chose during project setup) carrying the majority score
        # within that zone - a different source (per-zone, not
        # per-cell), so _add_map_page()'s raster loader can't show them.
        subnational_product_keys = [
            (
                "geoe3_score_subnational_aggregation",
                "GeoE3 Score — Subnational Aggregation",
                "likert",
            ),
            (
                "geoe3_score_ghsl_masked_subnational_aggregation",
                "GHSL Masked — Subnational Aggregation",
                "likert",
            ),
            (
                "geoe3_by_population_subnational_aggregation",
                "By Population — Subnational Aggregation",
                "by_population",
            ),
            (
                "geoe3_score_by_population_ghsl_masked_subnational_aggregation",
                "By Population (GHSL Masked) — Subnational Aggregation",
                "by_population",
            ),
        ]
        for key, label, palette in subnational_product_keys:
            layer_uri = model.get(key)
            if not layer_uri:
                continue
            score_kind = "enablement x population" if palette == "by_population" else "GeoE3"
            self.page_descriptions[label] = (
                f"Majority {score_kind} score within each administrative zone, " "aggregated from the analysis grid."
            )
            if self._add_vector_map_page(label, label, layer_uri, current_page, palette=palette):
                current_page += 1

        if self._subnational_score_matrix_enabled():
            current_page = self.make_subnational_score_matrix_pages(current_page)

        return current_page

    def parse_iso_datetime(self, iso_str: str) -> Optional[datetime]:
        """Parse ISO 8601 datetime string safely.

        Args:
            iso_str: ISO 8601 formatted datetime string.

        Returns:
            datetime: Parsed datetime object, or None if parsing fails.
        """
        try:
            return datetime.fromisoformat(iso_str)
        except Exception:
            return None

    def interpolate_color(self, rel: float) -> str:
        """Linearly interpolate between forest green and off-red.

        rel = 0.0 => forest green (#228B22), rel = 1.0 => off-red (#CC4444)

        Args:
            rel: Relative value from 0.0 to 1.0.

        Returns:
            str: Hex color string (e.g., "#228B22").
        """
        fg = (34, 139, 34)  # Forest Green
        or_ = (204, 68, 68)  # Off Red
        r = int(fg[0] + (or_[0] - fg[0]) * rel)
        g = int(fg[1] + (or_[1] - fg[1]) * rel)
        b = int(fg[2] + (or_[2] - fg[2]) * rel)
        return f"#{r:02x}{g:02x}{b:02x}"  # noqa E231

    def extract_execution_times_with_colors(self) -> List[Dict[str, Optional[str]]]:
        """Extract execution times for indicators with relative time and color gradient.

        Returns:
            List[Dict]: A sorted list of dictionaries with indicator, factor, dimension,
                execution_time_minutes, relative_time (0.0-1.0), and color (hex string).
        """

        with open(self.model_path, "r", encoding="utf-8") as f:
            model = json.load(f)

        results = []

        for dimension in model.get("dimensions", []):
            dim_name = dimension.get("name", "")
            for factor in dimension.get("factors", []):
                factor_name = factor.get("name", "")
                for indicator in factor.get("indicators", []):
                    # Skip indicators that are not used
                    analysis_mode = indicator.get("analysis_mode", "")
                    if analysis_mode == "Do Not Use":
                        continue

                    ind_name = indicator.get("indicator", "")
                    start_str = indicator.get("execution_start_time", "")
                    end_str = indicator.get("execution_end_time", "")

                    start_dt = self.parse_iso_datetime(start_str)
                    end_dt = self.parse_iso_datetime(end_str)

                    if start_dt and end_dt:
                        duration = round((end_dt - start_dt).total_seconds() / 60, 2)
                    else:
                        duration = None

                    results.append(
                        {
                            "indicator": ind_name,
                            "factor": factor_name,
                            "dimension": dim_name,
                            "execution_time_minutes": duration,
                        }
                    )

        # Compute relative times
        valid_times = [r["execution_time_minutes"] for r in results if r["execution_time_minutes"] is not None]

        if valid_times:
            min_time = min(valid_times)
            max_time = max(valid_times)
            range_time = max_time - min_time if max_time > min_time else 1.0  # avoid division by zero

            for r in results:
                exec_time = r["execution_time_minutes"]
                if exec_time is not None:
                    rel = (exec_time - min_time) / range_time
                    r["relative_time"] = round(rel, 2)
                    r["color"] = self.interpolate_color(rel)
                else:
                    r["relative_time"] = None
                    r["color"] = None

        # Sort by execution time descending, placing None last
        results.sort(
            key=lambda r: (
                r["execution_time_minutes"] is None,
                -(r["execution_time_minutes"] or 0),
            )
        )

        return results

    def create_execution_time_layout(self, entries: list, max_bar_width_mm: float = 78.0, page: int = 1) -> float:
        """Add a clean horizontal bar chart of indicator execution times.

        Layout per row: indicator name right-aligned in a left column, a
        length-encoded bar, and the duration at the bar's end. Rows carry a
        subtle alternating tint. Indicators that were not run render as a
        greyed label with no bar.

        Args:
            entries: Output from `extract_execution_times_with_colors()`.
            max_bar_width_mm: Bar width for the slowest indicator, in mm.
            page: Page number to draw the chart on.

        Returns:
            float: Y position (mm) just below the last thing drawn, so a
            caller can place more content on the same page without
            overlapping it.
        """
        top = 44.0
        row_pitch = 7.0
        bar_h = 3.6
        label_x = 15.0
        label_w = 72.0
        bar_x = label_x + label_w + 3.0
        max_rows = 32

        clipped = len(entries) > max_rows
        for i, entry in enumerate(entries[:max_rows]):
            y = top + i * row_pitch
            indicator = entry["indicator"]
            duration = entry["execution_time_minutes"]

            if i % 2 == 0:
                self._rect(label_x - 1, y - 1.4, 181.0, row_pitch - 0.6, MIST, page)

            name = indicator if len(indicator) <= 52 else indicator[:49] + "…"
            self._label(
                name,
                label_x,
                y - 0.6,
                label_w,
                row_pitch,
                page,
                size=8,
                color=CHARCOAL if duration is not None else GREY,
                halign=Qt.AlignmentFlag.AlignRight,
            )

            if duration is None:
                self._label("not run", bar_x, y - 0.6, 30, row_pitch, page, size=8, color=GREY)
                continue

            bar_width = max(0.6, max_bar_width_mm * (entry.get("relative_time") or 0.0))
            bar = QgsLayoutItemShape(self.layout)
            bar.attemptMove(QgsLayoutPoint(bar_x, y, QgsUnitTypes.LayoutUnit.LayoutMillimeters), page=page)
            bar.setFixedSize(QgsLayoutSize(bar_width, bar_h, QgsUnitTypes.LayoutUnit.LayoutMillimeters))
            _flat_fill(bar, CYAN)
            self.layout.addLayoutItem(bar)

            self._label(
                f"{duration:g} min",
                bar_x + bar_width + 2,
                y - 0.6,
                28,
                row_pitch,
                page,
                size=8,
                color=GREY,
            )
        rows_shown = min(len(entries), max_rows)
        bottom_y = top + rows_shown * row_pitch
        if clipped:
            self._label(
                f"Showing the {max_rows} slowest steps of {len(entries)}.",
                label_x,
                bottom_y + 2,
                180,
                6,
                page,
                size=8,
                color=GREY,
            )
            bottom_y += 8
        return bottom_y

    def _total_analysis_duration_minutes(self) -> Optional[float]:
        """Wall-clock span of the whole analysis run: the earliest
        execution_start_time to the latest execution_end_time found
        anywhere in the model (dimensions, factors and indicators each
        carry their own pair) - not a sum of every step's own duration,
        which would overstate the real elapsed time for anything that
        ran concurrently.

        Returns:
            Minutes elapsed, or None if the model has no usable
            timestamps (e.g. nothing has been run yet).
        """
        with open(self.model_path, "r", encoding="utf-8") as f:
            model = json.load(f)

        timestamps = []

        def collect(entry: dict) -> None:
            for key in ("execution_start_time", "execution_end_time"):
                parsed = self.parse_iso_datetime(entry.get(key, ""))
                if parsed:
                    timestamps.append(parsed)

        for dimension in model.get("dimensions", []):
            collect(dimension)
            for factor in dimension.get("factors", []):
                collect(factor)
                for indicator in factor.get("indicators", []):
                    collect(indicator)

        if not timestamps:
            return None
        return round((max(timestamps) - min(timestamps)).total_seconds() / 60, 2)

    def _draw_total_duration_block(self, total_minutes: float, y: float, page: int) -> None:
        """A highlighted block stating the whole analysis run's
        wall-clock duration, styled like make_legend_page()'s "How the
        scores are calculated" note.
        """
        note_h = 24.0
        if y + note_h > FOOTER_Y:
            log_message("Not enough room for the total analysis time block - omitted", tag="GeoE3")
            return
        self._rect(MARGIN, y, CONTENT_W, note_h, MIST, page)
        self._rect(MARGIN, y, 2.2, note_h, CYAN, page)
        self._label(
            "Total analysis time",
            MARGIN + 8,
            y + 4.5,
            CONTENT_W - 16,
            7,
            page,
            size=12,
            color=NAVY,
            bold=True,
        )
        hours, minutes = divmod(round(total_minutes), 60)
        duration_text = f"{hours} h {minutes} min" if hours else f"{minutes} min"
        self._label(
            duration_text,
            MARGIN + 8,
            y + 13,
            CONTENT_W - 16,
            note_h - 17,
            page,
            size=11,
            color=CHARCOAL,
            bold=True,
        )

    def _study_area_stats(self) -> list:
        """Key facts about the study area and analysis grid, for the
        closing summary page.

        Returns:
            A list of (label, value) pairs, or [] if the grid
            GeoPackage isn't available.
        """
        if not self.grid_gpkg_path or not os.path.exists(self.grid_gpkg_path):
            return []

        import sqlite3

        try:
            connection = sqlite3.connect(self.grid_gpkg_path)
            try:
                cell_count = connection.execute("SELECT COUNT(*) FROM study_area_grid").fetchone()[0]
            finally:
                connection.close()
        except sqlite3.Error as error:
            log_message(f"Could not read study_area_grid for the study area summary: {error}", tag="GeoE3")
            return []

        with open(self.model_path, "r", encoding="utf-8") as f:
            model = json.load(f)
        cell_size_m = model.get("analysis_cell_size_m")
        analysis_scale = model.get("analysis_scale")

        crs_label = ""
        grid_layer = QgsVectorLayer(f"{self.grid_gpkg_path}|layername=study_area_grid", "study_area_grid", "ogr")
        if grid_layer.isValid():
            crs = grid_layer.crs()
            crs_label = f"{crs.authid()} — {crs.description()}" if crs.authid() else crs.description()

        stats = []
        admin0_name = self._admin0_name(self.working_directory)
        if admin0_name:
            stats.append(("Study area", admin0_name))
        if analysis_scale:
            stats.append(("Analysis scale", str(analysis_scale).title()))
        stats.append(("Number of grid cells", f"{cell_count:,}"))
        if cell_size_m:
            stats.append(("Grid cell size", f"{cell_size_m:g} m × {cell_size_m:g} m"))
            total_area_km2 = cell_count * (float(cell_size_m) ** 2) / 1_000_000
            stats.append(("Total analysis area", f"{total_area_km2:,.0f} km²"))
        if crs_label:
            stats.append(("Coordinate reference system", crs_label))
        return stats

    def make_study_area_summary_page(self, current_page: int) -> None:
        """Add the closing page: key facts about the study area and the
        analysis grid, so a reader can judge the analysis's resolution
        and scope without opening the GeoPackage themselves.
        """
        stats = self._study_area_stats()
        if not stats:
            log_message("No study area stats available - summary page skipped", tag="GeoE3")
            return

        self.page_descriptions["study_area_summary"] = (
            "Key facts about the study area and the analysis grid these results were computed on."
        )
        self.make_page(
            title="Study Area",
            description_key="study_area_summary",
            current_page=current_page,
            show_header_and_footer=True,
        )

        row_top = HEADER_H + 30
        row_pitch = 14
        for i, (label, value) in enumerate(stats):
            y = row_top + i * row_pitch
            if i % 2 == 0:
                self._rect(MARGIN, y - 2, CONTENT_W, row_pitch - 2, MIST, current_page)
            self._label(label, MARGIN + 6, y, 85, 8, current_page, size=10.5, color=GREY)
            self._label(
                value,
                MARGIN + 95,
                y,
                CONTENT_W - 95 - 6,
                8,
                current_page,
                size=11.5,
                color=NAVY,
                bold=True,
            )

    # ------------------------------------------------------------------
    # Insights: patterns in study_area_grid beyond the score itself -
    # which dimension most limits low-scoring cells, how much of the
    # score comes from uninhabited land, whether economic opportunity
    # and enablement line up, whether hazard exposure and enablement
    # move together, and which factors move together. Each is read
    # straight from study_area_grid/model.json - no new geoprocessing,
    # consistent with the rest of this report-only module.
    # ------------------------------------------------------------------

    def _limiting_dimension_counts(self) -> list:
        """For cells in the two lowest enablement classes (score <= 2),
        which dimension is dragging the cell down - the dimension with
        the lowest value for that cell. Whichever dimension appears most
        often is the single biggest lever for moving the most low-
        scoring cells up a class.

        Returns:
            [(dimension_name, count), ...] sorted by count descending,
            or [] if there are fewer than two usable dimensions.
        """
        with open(self.model_path, "r", encoding="utf-8") as f:
            model = json.load(f)
        dims = [
            (dimension.get("name", ""), AnalysisReport._grid_column_name("dimension", dimension.get("id", "")))
            for dimension in model.get("dimensions", [])
            if self._has_used_factors(dimension)
        ]
        if len(dims) < 2:
            return []

        rows = self._read_grid_columns(["geoe3"] + [col for _, col in dims])
        counts = {name: 0 for name, _ in dims}
        for row in rows:
            if row[0] > 2:
                continue
            dim_values = row[1:]
            min_index = min(range(len(dim_values)), key=lambda i: dim_values[i])
            counts[dims[min_index][0]] += 1

        return sorted(counts.items(), key=lambda item: item[1], reverse=True)

    def _ghsl_settlement_gap_stats(self) -> Optional[dict]:
        """Compare the average GeoE3 score across the whole study area
        to the average within GHSL-identified settlements only - how
        much of an apparently "good" overall score comes from
        uninhabited land rather than places people actually live.

        Returns:
            {"avg_all", "avg_settlement", "settlement_share"}, with
            avg_settlement/settlement_share None/0.0 if no settlement
            cells are scored, or None if the grid isn't available.
        """
        rows_all = self._read_grid_columns(["geoe3"])
        if not rows_all:
            return None
        rows_settlement = self._read_grid_columns(["geoe3_masked"])

        avg_all = sum(row[0] for row in rows_all) / len(rows_all)
        if not rows_settlement:
            return {"avg_all": avg_all, "avg_settlement": None, "settlement_share": 0.0}
        avg_settlement = sum(row[0] for row in rows_settlement) / len(rows_settlement)
        return {
            "avg_all": avg_all,
            "avg_settlement": avg_settlement,
            "settlement_share": len(rows_settlement) / len(rows_all),
        }

    def _opportunities_mask_score_histogram(self) -> list:
        """Among cells flagged as an economic opportunity
        (opportunities_mask = 1), how many fall into each enablement
        class - the highest-priority cells for investment are
        opportunity cells that ALSO score low: economic potential
        exists but the conditions to access it don't (yet).

        Returns:
            Five counts, one per enablement class (see SCORE_CLASSES).
        """
        if not self.grid_gpkg_path or not os.path.exists(self.grid_gpkg_path):
            return [0, 0, 0, 0, 0]
        import sqlite3

        try:
            connection = sqlite3.connect(self.grid_gpkg_path)
            try:
                rows = connection.execute(
                    "SELECT geoe3 FROM study_area_grid "
                    "WHERE opportunities_mask = 1 AND geoe3 IS NOT NULL AND geoe3 > 0"
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as error:
            log_message(f"Could not read opportunities mask overlap: {error}", tag="GeoE3")
            return [0, 0, 0, 0, 0]
        values = numpy.array([row[0] for row in rows], dtype=float)
        return AnalysisReport._score_histogram_from_values(values)

    #: Minimum number of cells where two factors both have a valid
    #: score before their correlation is shown - below this, a handful
    #: of coincidentally-aligned cells can produce a misleadingly
    #: strong-looking coefficient.
    MIN_CORRELATION_OVERLAP_CELLS = 30

    def _factor_correlation_matrix(self) -> Optional[tuple]:
        """Pairwise Pearson correlation between every pair of factor
        scores, read directly from study_area_grid - factors that move
        together signal a shared root cause, and a bundled intervention
        might address both at once.

        Computed PAIRWISE (only requiring the two factors in each pair
        to both have a valid score for a cell), not across all factors
        at once: factors cover very different shares of the study area
        (a location-based factor might score a few hundred cells, an
        index-based one scores almost all of them), so requiring every
        factor to be valid simultaneously can leave zero usable cells
        even though plenty of pairwise overlap exists. A factor with NO
        valid cells anywhere (so it can never form a pair) is dropped
        entirely rather than shown as a blank row/column.

        Returns:
            (factor_names, matrix) where matrix is an NxN numpy array of
            correlation coefficients (NaN where two factors overlap on
            fewer than MIN_CORRELATION_OVERLAP_CELLS cells), or None if
            there are too few usable factors.
        """
        with open(self.model_path, "r", encoding="utf-8") as f:
            model = json.load(f)
        factors = []
        for dimension in model.get("dimensions", []):
            for factor in dimension.get("factors", []):
                if self._has_used_indicators(factor):
                    factors.append(
                        (factor.get("name", ""), AnalysisReport._grid_column_name("factor", factor.get("id", "")))
                    )
        if len(factors) < 2:
            return None

        data = self._read_grid_columns_with_gaps([col for _, col in factors])
        if data.shape[0] < AnalysisReport.MIN_CORRELATION_OVERLAP_CELLS:
            return None

        has_any_data = ~numpy.all(numpy.isnan(data), axis=0)
        if numpy.count_nonzero(has_any_data) < 2:
            return None
        data = data[:, has_any_data]
        names = [name for (name, _), keep in zip(factors, has_any_data) if keep]

        n = data.shape[1]
        matrix = numpy.full((n, n), numpy.nan)
        for i in range(n):
            matrix[i, i] = 1.0
            for j in range(i + 1, n):
                overlap = ~numpy.isnan(data[:, i]) & ~numpy.isnan(data[:, j])
                if numpy.count_nonzero(overlap) >= AnalysisReport.MIN_CORRELATION_OVERLAP_CELLS:
                    coefficient = numpy.corrcoef(data[overlap, i], data[overlap, j])[0, 1]
                    matrix[i, j] = matrix[j, i] = coefficient

        return names, matrix

    def _hazard_exposure_tercile_scores(self) -> list:
        """Average GeoE3 score for cells grouped into hazard-exposure
        terciles (low/medium/high), via fac_environmental_hazards -
        tests whether climate/hazard-exposed areas also tend to have
        lower enablement, the case for pairing resilience and
        empowerment investment rather than treating them separately.

        fac_environmental_hazards follows the same 0-5 "higher is
        better" convention as every other factor - a HIGH value means
        LOW hazard exposure - so the lowest tercile of this column is
        the highest-exposure group.

        Returns:
            [("High hazard exposure", avg_score), ("Medium ...", ...),
            ("Low ...", ...)], with avg_score None for an empty bin, or
            [] if there are too few scored cells to bin.
        """
        rows = self._read_grid_columns(["fac_environmental_hazards", "geoe3"])
        if len(rows) < 3:
            return []
        hazards = numpy.array([row[0] for row in rows])
        scores = numpy.array([row[1] for row in rows])
        low_cut, high_cut = numpy.percentile(hazards, [33.33, 66.67])
        bins = [
            ("High hazard exposure", scores[hazards <= low_cut]),
            ("Medium hazard exposure", scores[(hazards > low_cut) & (hazards <= high_cut)]),
            ("Low hazard exposure", scores[hazards > high_cut]),
        ]
        return [(label, float(numpy.mean(values)) if values.size else None) for label, values in bins]

    @staticmethod
    def _diverging_color(value: float) -> QColor:
        """White at 0, deepening to NAVY for +1 and off-red for -1 - a
        standard diverging scale for the factor correlation heatmap
        (distinct from interpolate_color(), which is a good/bad scale
        for hazard/score values, not a magnitude-and-sign scale).
        """
        value = max(-1.0, min(1.0, value))
        white = (255, 255, 255)
        if value >= 0:
            target = (0, 34, 68)  # NAVY
            t = value
        else:
            target = (204, 68, 68)  # off-red, matches interpolate_color()
            t = -value
        r = int(white[0] + (target[0] - white[0]) * t)
        g = int(white[1] + (target[1] - white[1]) * t)
        b = int(white[2] + (target[2] - white[2]) * t)
        return QColor(r, g, b)

    def _draw_factor_distribution_grid(self, factors: list, current_page: int, top: float) -> None:
        """Lay out one small score-distribution histogram per factor, 4
        to a row - which specific factor has the widest spread or worst
        tail, not just the final blended score.
        """
        columns = 4
        gap = 6.0
        cell_w = (CONTENT_W - (columns - 1) * gap) / columns
        label_h = 8.0
        sparkline_h = 20.0
        row_pitch = label_h + sparkline_h + gap
        for index, (name, grid_column) in enumerate(factors):
            row, col = divmod(index, columns)
            x = MARGIN + col * (cell_w + gap)
            y = top + row * row_pitch
            self._label(name, x, y, cell_w, label_h, current_page, size=7.5, color=CHARCOAL, bold=True)
            self._draw_sparkline_for_column(
                column_name=grid_column,
                palette="likert",
                x=x,
                y=y + label_h,
                w=cell_w,
                h=sparkline_h,
                page=current_page,
            )

    def make_factor_distributions_page(self, current_page: int) -> bool:
        """Add a page showing every factor's own score distribution -
        reuses the same sparkline this report already draws under every
        minimap, just without the map.
        """
        with open(self.model_path, "r", encoding="utf-8") as f:
            model = json.load(f)
        factors = [
            (factor.get("name", ""), AnalysisReport._grid_column_name("factor", factor.get("id", "")))
            for dimension in model.get("dimensions", [])
            for factor in dimension.get("factors", [])
            if self._has_used_indicators(factor)
        ]
        if not factors:
            return False

        self.page_descriptions["factor_distributions"] = (
            "Each factor's score distribution across the analysis grid. The impact "
            "of a single factor should be visible even when the blended score above "
            "looks fine."
        )
        self.make_page(
            title="Factor Score Patterns",
            description_key="factor_distributions",
            current_page=current_page,
            show_header_and_footer=True,
        )
        self._draw_factor_distribution_grid(factors, current_page, top=HEADER_H + 28)
        return True

    def _draw_limiting_dimension_chart(self, counts: list, current_page: int, top: float) -> float:
        """Horizontal bar chart: among cells in the two lowest enablement
        classes, how often each dimension is the one dragging the cell
        down.

        Returns:
            Y position (mm) just below the chart.
        """
        total = sum(n for _, n in counts) or 1
        row_pitch = 12.0
        bar_h = 6.0
        label_w = 65.0
        bar_x = MARGIN + label_w + 4
        bar_max_w = CONTENT_W - label_w - 4 - 28
        for i, (name, count) in enumerate(counts):
            y = top + i * row_pitch
            percentage = count / total * 100
            self._label(
                name,
                MARGIN,
                y,
                label_w,
                bar_h,
                current_page,
                size=9.5,
                color=CHARCOAL,
                halign=Qt.AlignmentFlag.AlignRight,
            )
            bar_w = max(0.6, bar_max_w * count / total)
            self._rect(bar_x, y, bar_w, bar_h, CYAN, current_page)
            self._label(f"{percentage:.0f}%", bar_x + bar_w + 2, y, 24, bar_h, current_page, size=9, color=GREY)
        return top + len(counts) * row_pitch

    def _draw_opportunities_overlap_chart(self, counts: list, current_page: int, top: float) -> float:
        """Horizontal bar chart: among cells flagged as an economic
        opportunity, how many fall into each enablement class, coloured
        to match the main legend.

        Returns:
            Y position (mm) just below the chart.
        """
        total = sum(counts) or 1
        row_pitch = 12.0
        bar_h = 6.0
        label_w = 65.0
        bar_x = MARGIN + label_w + 4
        bar_max_w = CONTENT_W - label_w - 4 - 28
        for i, (count, (_range, class_name, colour, _meaning)) in enumerate(zip(counts, SCORE_CLASSES)):
            y = top + i * row_pitch
            percentage = count / total * 100
            self._label(
                class_name,
                MARGIN,
                y,
                label_w,
                bar_h,
                current_page,
                size=9.5,
                color=CHARCOAL,
                halign=Qt.AlignmentFlag.AlignRight,
            )
            bar_w = max(0.6, bar_max_w * count / total)
            self._rect(bar_x, y, bar_w, bar_h, QColor(colour), current_page)
            self._label(f"{percentage:.0f}%", bar_x + bar_w + 2, y, 24, bar_h, current_page, size=9, color=GREY)
        return top + len(counts) * row_pitch

    def make_low_score_drivers_page(self, current_page: int) -> bool:
        """Add a page pairing two "where to intervene first" views: what
        most often limits the lowest-scoring cells, and where existing
        economic opportunity isn't yet matched by enabling conditions.
        """
        limiting = self._limiting_dimension_counts()
        opportunities = self._opportunities_mask_score_histogram()
        has_opportunities = sum(opportunities) > 0
        if not limiting and not has_opportunities:
            return False

        self.page_descriptions["low_score_drivers"] = (
            "The biggest gain availability can be discovered in two ways: which "
            "dimension most often limits a low-scoring cell, and where economic "
            "opportunity is not yet matched by enabling conditions."
        )
        self.make_page(
            title="Low Scores",
            description_key="low_score_drivers",
            current_page=current_page,
            show_header_and_footer=True,
        )
        y = HEADER_H + 24
        if limiting:
            self._label(
                "What limits the lowest scoring cells",
                MARGIN,
                y,
                CONTENT_W,
                7,
                current_page,
                size=11.5,
                color=NAVY,
                bold=True,
            )
            self._label(
                "In cells scoring 2 or below, the dimension with the lowest value is "
                "the single biggest lever for moving the cell up a class.",
                MARGIN,
                y + 7,
                CONTENT_W,
                10,
                current_page,
                size=8.5,
                color=GREY,
            )
            y = self._draw_limiting_dimension_chart(limiting, current_page, top=y + 18) + 14
        if has_opportunities:
            self._label(
                "Economic opportunity vs enablement",
                MARGIN,
                y,
                CONTENT_W,
                7,
                current_page,
                size=11.5,
                color=NAVY,
                bold=True,
            )
            self._label(
                "Among cells flagged as an economic opportunity, their enablement class - "
                "opportunity cells that also score low are the highest-priority investment targets.",
                MARGIN,
                y + 7,
                CONTENT_W,
                10,
                current_page,
                size=8.5,
                color=GREY,
            )
            self._draw_opportunities_overlap_chart(opportunities, current_page, top=y + 18)
        return True

    def _draw_ghsl_gap_block(self, stats: dict, current_page: int, top: float) -> float:
        """Two stat cards side by side: average score across the whole
        study area vs within GHSL-identified settlements only.

        Returns:
            Y position (mm) just below the block.
        """
        card_w = (CONTENT_W - 8) / 2
        card_h = 28.0
        cards = [("Average score, whole study area", f"{stats['avg_all']:.2f}")]
        if stats["avg_settlement"] is not None:
            cards.append(("Average score, GHSL settlements only", f"{stats['avg_settlement']:.2f}"))
        for i, (label, value) in enumerate(cards):
            x = MARGIN + i * (card_w + 8)
            self._rect(x, top, card_w, card_h, MIST, current_page)
            self._rect(x, top, 2.2, card_h, CYAN, current_page)
            self._label(label, x + 8, top + 5, card_w - 16, 10, current_page, size=9, color=GREY)
            self._label(value, x + 8, top + 14, card_w - 16, 12, current_page, size=18, color=NAVY, bold=True)
        bottom = top + card_h
        if stats["avg_settlement"] is not None:
            self._label(
                f"GHSL-identified settlements cover {stats['settlement_share'] * 100:.0f}% "
                "of the scored study area.",
                MARGIN,
                bottom + 4,
                CONTENT_W,
                6,
                current_page,
                size=8.5,
                color=GREY,
            )
            bottom += 10
        return bottom

    def _draw_hazard_exposure_chart(self, bins: list, current_page: int, top: float) -> None:
        """Vertical bar chart: average GeoE3 score for cells in each
        hazard-exposure tercile, low exposure to high, left to right.
        """
        ordered = list(reversed(bins))  # low -> medium -> high exposure
        colours = [QColor("#2c7bb6"), QColor("#ffffbf"), QColor("#d7191c")]
        values = [value for _, value in ordered if value is not None]
        if not values:
            return
        peak = max(values) or 1.0
        n = len(ordered)
        gap = 8.0
        bar_w = (CONTENT_W - (n - 1) * gap) / n
        bar_area_h = 40.0
        for i, (label, value) in enumerate(ordered):
            x = MARGIN + i * (bar_w + gap)
            if value is None:
                continue
            bar_h = bar_area_h * (value / peak)
            y = top + (bar_area_h - bar_h)
            self._rect(x, y, bar_w, bar_h, colours[i], current_page)
            self._label(
                f"{value:.2f}",
                x,
                y - 6,
                bar_w,
                5,
                current_page,
                size=9,
                color=NAVY,
                bold=True,
                halign=Qt.AlignmentFlag.AlignHCenter,
            )
            self._label(
                label,
                x,
                top + bar_area_h + 2,
                bar_w,
                10,
                current_page,
                size=8,
                color=GREY,
                halign=Qt.AlignmentFlag.AlignHCenter,
            )

    def make_settlement_hazard_page(self, current_page: int) -> bool:
        """Add a page showing how much of the score comes from areas
        people actually live in, and whether hazard-exposed areas also
        tend to be less enabling.
        """
        ghsl_stats = self._ghsl_settlement_gap_stats()
        hazard_bins = self._hazard_exposure_tercile_scores()
        if ghsl_stats is None and not hazard_bins:
            return False

        self.page_descriptions["settlement_hazard"] = (
            "How much of the overall score comes from areas people actually live "
            "in, and whether hazard-exposed areas also tend to be less enabling."
        )
        self.make_page(
            title="Settlement and Hazard Patterns",
            description_key="settlement_hazard",
            current_page=current_page,
            show_header_and_footer=True,
        )
        y = HEADER_H + 24
        if ghsl_stats is not None:
            self._label("Settlement coverage", MARGIN, y, CONTENT_W, 7, current_page, size=11.5, color=NAVY, bold=True)
            y = self._draw_ghsl_gap_block(ghsl_stats, current_page, top=y + 10) + 10
        if hazard_bins:
            self._label(
                "Hazard exposure vs enablement",
                MARGIN,
                y,
                CONTENT_W,
                7,
                current_page,
                size=11.5,
                color=NAVY,
                bold=True,
            )
            self._label(
                "Average GeoE3 score for cells grouped by environmental hazard exposure "
                "(fire, flood, landslide, cyclone, drought).",
                MARGIN,
                y + 7,
                CONTENT_W,
                10,
                current_page,
                size=8.5,
                color=GREY,
            )
            self._draw_hazard_exposure_chart(hazard_bins, current_page, top=y + 24)
        return True

    def _draw_correlation_heatmap(self, names: list, matrix, current_page: int, top: float) -> float:
        """NxN heatmap of factor-score correlations - NAVY for strong
        positive correlation, off-red for strong negative, white for
        none. Factors that move together signal a shared root cause; a
        bundled intervention might address both at once.

        Returns:
            The y-coordinate (mm) immediately below the last element
            drawn, so a caller can place further content beneath it
            without duplicating this layout's geometry.
        """
        n = len(names)
        cell = min(9.0, CONTENT_W / n)
        grid_x = MARGIN + 10
        for row in range(n):
            y = top + row * cell
            self._label(
                str(row + 1),
                MARGIN,
                y,
                8,
                cell,
                current_page,
                size=6,
                color=GREY,
                halign=Qt.AlignmentFlag.AlignRight,
                valign=Qt.AlignmentFlag.AlignVCenter,
            )
            for col in range(n):
                x = grid_x + col * cell
                value = matrix[row][col]
                colour = WHITE if numpy.isnan(value) else AnalysisReport._diverging_color(value)
                self._rect(x, y, cell - 0.3, cell - 0.3, colour, current_page)

        label_y = top + n * cell + 1
        for col in range(n):
            x = grid_x + col * cell
            self._label(
                str(col + 1),
                x,
                label_y,
                cell,
                5,
                current_page,
                size=6,
                color=GREY,
                halign=Qt.AlignmentFlag.AlignHCenter,
            )

        legend_y = label_y + 8
        legend_rows = (n + 1) // 2
        legend_col_w = CONTENT_W / 2
        for i, name in enumerate(names):
            col, row = divmod(i, legend_rows)
            x = MARGIN + col * legend_col_w
            y = legend_y + row * 4.2
            self._label(f"{i + 1}. {name}", x, y, legend_col_w - 4, 4.2, current_page, size=6.5, color=CHARCOAL)

        return legend_y + legend_rows * 4.2

    def _draw_correlation_scale_bar(self, current_page: int, top: float) -> None:
        """A diverging colour-scale strip (red -1 -> white 0 -> navy +1)
        with tick labels, plus a short "how to read this" caption - the
        heatmap's own colours alone don't explain which direction is
        good or what the diagonal means.
        """
        self._label(
            "How to read this grid",
            MARGIN,
            top,
            CONTENT_W,
            5,
            current_page,
            size=8.5,
            color=NAVY,
            bold=True,
        )
        caption_top = top + 5.5
        caption = self._label(
            "<p>Row and column numbers refer to the same factor, in the same order as the "
            "key above - cell (3, 7) compares factor 3 against factor 7. The diagonal running "
            "top-left to bottom-right is always deepest navy, since every factor correlates "
            "perfectly with itself; it isn't a finding. Off the diagonal, deep navy means the "
            "two factors tend to score high in the same places, deep red means one tends to "
            "score high where the other scores low, and pale/white means no real relationship "
            "either way.</p>",
            MARGIN,
            caption_top,
            CONTENT_W,
            14,
            current_page,
            size=8,
            color=CHARCOAL,
            html=True,
        )
        caption.setHAlign(Qt.AlignmentFlag.AlignJustify)

        bar_top = caption_top + 16
        bar_w = 100.0
        bar_h = 5.0
        bar_x = MARGIN + (CONTENT_W - bar_w) / 2
        steps = 60
        for i in range(steps):
            value = -1.0 + 2.0 * i / (steps - 1)
            segment_w = bar_w / steps
            self._rect(
                bar_x + i * segment_w,
                bar_top,
                segment_w + 0.3,
                bar_h,
                AnalysisReport._diverging_color(value),
                current_page,
            )

        label_y = bar_top + bar_h + 1.5
        self._label(
            "-1  opposite", bar_x, label_y, 40, 4, current_page, size=6.5, color=GREY, halign=Qt.AlignmentFlag.AlignLeft
        )
        self._label(
            "0  no relationship",
            bar_x + bar_w / 2 - 30,
            label_y,
            60,
            4,
            current_page,
            size=6.5,
            color=GREY,
            halign=Qt.AlignmentFlag.AlignHCenter,
        )
        self._label(
            "+1  together",
            bar_x + bar_w - 40,
            label_y,
            40,
            4,
            current_page,
            size=6.5,
            color=GREY,
            halign=Qt.AlignmentFlag.AlignRight,
        )

    def make_factor_correlation_page(self, current_page: int) -> bool:
        """Add a page showing which factors tend to move together -
        strongly correlated factors suggest a shared root cause, where a
        bundled intervention might address more than one at once.
        """
        result = self._factor_correlation_matrix()
        if result is None:
            return False
        names, matrix = result

        self.page_descriptions["factor_correlation"] = (
            "Which factors tend to move together across the analysis grid. A "
            "strong correlation suggests a shared root cause - a single "
            "intervention may move both factors at once."
        )
        self.make_page(
            title="Factor Correlations",
            description_key="factor_correlation",
            current_page=current_page,
            show_header_and_footer=True,
        )
        legend_bottom = self._draw_correlation_heatmap(names, matrix, current_page, top=HEADER_H + 26)
        self._draw_correlation_scale_bar(current_page, top=legend_bottom + 6)
        return True

    def create_insights_pages(self, current_page: int) -> int:
        """Add every available insights page (see the module-level
        comment above _limiting_dimension_counts()) in sequence, each
        only if it has real data to show.
        """
        for page_builder in (
            self.make_factor_distributions_page,
            self.make_low_score_drivers_page,
            self.make_settlement_hazard_page,
            self.make_factor_correlation_page,
        ):
            if page_builder(current_page):
                current_page += 1
        return current_page

    def _subnational_score_matrix_columns(self) -> list:
        """(display_name, grid_column) for every used dimension, every
        used factor, and the overall GeoE3 total - mirrors
        SubnationalAggregationProcessingTask._factor_dimension_total_columns()'s
        column set/order EXACTLY, so the Nth column shown here is the
        Nth avg_<column> field actually written into the aggregates
        GeoPackage. Read from model.json, not a live item tree (the
        report has no item tree to walk).
        """
        with open(self.model_path, "r", encoding="utf-8") as f:
            model = json.load(f)
        columns = []
        for dimension in model.get("dimensions", []):
            if not self._has_used_factors(dimension):
                continue
            columns.append(
                (dimension.get("name", ""), AnalysisReport._grid_column_name("dimension", dimension.get("id", "")))
            )
            for factor in dimension.get("factors", []):
                if self._has_used_indicators(factor):
                    columns.append(
                        (factor.get("name", ""), AnalysisReport._grid_column_name("factor", factor.get("id", "")))
                    )
        columns.append(("GeoE3 Score", "geoe3"))
        return columns

    def _subnational_score_matrix_rows(self) -> Optional[tuple]:
        """Read the subnational score matrix: every administrative
        zone's own average score (not the single majority-class product
        shown on the subnational map pages) for every used dimension,
        factor, and the overall total - see
        SubnationalAggregationProcessingTask.aggregate_factor_dimension_totals(),
        which computes and writes these avg_<column>/zone_name fields.

        Returns:
            (columns, rows) where columns is [(display_name,
            grid_column), ...] and rows is [(zone_name, [value_or_None,
            ...]), ...] in the same column order, or None if the
            project has no subnational boundary configured, or its
            aggregates file predates these columns (an analysis that
            hasn't been re-run since this feature was added).
        """
        if not self.working_directory:
            return None
        gpkg_path = os.path.join(
            self.working_directory, "subnational_aggregation", "geoe3_score_subnational_aggregation.gpkg"
        )
        if not os.path.exists(gpkg_path):
            return None

        columns = self._subnational_score_matrix_columns()
        if not columns:
            return None

        import sqlite3

        from geest.core.grid_column_utils import _quote_sql_identifier

        try:
            quoted_columns = [_quote_sql_identifier(f"avg_{col}") for _, col in columns]
        except ValueError as error:
            log_message(f"Refusing to read subnational score matrix: {error}", tag="GeoE3")
            return None

        try:
            connection = sqlite3.connect(gpkg_path)
            try:
                existing = {
                    row[1]
                    for row in connection.execute(  # nosec B608
                        "PRAGMA table_info(geoe3_score_subnational_aggregation)"
                    ).fetchall()
                }
                required = {f"avg_{col}" for _, col in columns} | {"zone_name"}
                if not required.issubset(existing):
                    log_message(
                        "Subnational score matrix columns not found - re-run the full analysis to add them.",
                        tag="GeoE3",
                    )
                    return None
                select_columns = ", ".join(quoted_columns)
                rows = connection.execute(
                    f"SELECT zone_name, {select_columns} "  # nosec B608
                    "FROM geoe3_score_subnational_aggregation ORDER BY fid"
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as error:
            log_message(f"Could not read subnational score matrix: {error}", tag="GeoE3")
            return None

        result_rows = [(row[0] or "—", list(row[1:])) for row in rows]
        return columns, result_rows

    @staticmethod
    def _score_class_color(value: Optional[float]) -> QColor:
        """The same 5-class enablement colour a score of this value
        would be painted on the map (see resources/qml/analysis.qml's
        DISCRETE boundaries), or white for no data.
        """
        if value is None or value <= 0:
            return WHITE
        class_index = int(numpy.digitize([value], bins=[1, 2, 3, 4, 5], right=True)[0])
        class_index = min(class_index, 4)
        return QColor(SCORE_LEGEND_COLORS[class_index + 1])

    def _place_picture(self, image_path: str, x: float, y: float, w: float, h: float, page: int) -> None:
        """Embed an image file at the given position/size - a drawing
        primitive like _rect()/_label(), kept separate from
        _render_score_matrix_page_image() so it can be mocked out in
        tests without needing a real QgsLayout object.
        """
        picture = QgsLayoutItemPicture(self.layout)
        picture.setPicturePath(image_path)
        self.layout.addLayoutItem(picture)
        picture.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutUnit.LayoutMillimeters), page=page)
        picture.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutUnit.LayoutMillimeters))

    def _render_score_matrix_page_image(
        self,
        page_rows: list,
        n_cols: int,
        name_col_w: float,
        swatch_w: float,
        row_h: float,
        header_h: float,
    ) -> str:
        """Render one subnational score matrix page's zone-name column,
        numbered column headers, and coloured swatches as a SINGLE
        raster image, saved to a temp PNG (cleaned up in cleanup()) and
        embedded via one QgsLayoutItemPicture.

        A matrix page can hold dozens of columns x dozens of rows - one
        QgsLayoutItem per cell (the same _label()/_rect() primitives
        every other page in this report uses) adds up to thousands of
        full graphics-scene items per page, which brings QGIS's layout
        engine to a crawl (confirmed: report generation hung rather
        than completing, against a real 2084-zone boundary). A single
        rasterised image per page has none of that per-item overhead.
        """
        scale = 10  # px/mm - crisp at print resolution, plain and simple
        width_mm = name_col_w + n_cols * swatch_w
        height_mm = header_h + len(page_rows) * row_h
        image = QImage(max(1, round(width_mm * scale)), max(1, round(height_mm * scale)), QImage.Format.Format_ARGB32)
        image.fill(QColor(255, 255, 255, 0))

        painter = QPainter(image)
        try:
            font = painter.font()
            font.setPointSizeF(15.0)
            painter.setFont(font)

            painter.setPen(GREY)
            for col_index in range(n_cols):
                x = (name_col_w + col_index * swatch_w) * scale
                painter.drawText(
                    QRectF(x, 0, swatch_w * scale, header_h * scale),
                    Qt.AlignmentFlag.AlignCenter,
                    str(col_index + 1),
                )

            for row_index, (zone_name, values) in enumerate(page_rows):
                y = (header_h + row_index * row_h) * scale
                painter.setPen(CHARCOAL)
                painter.drawText(
                    QRectF(0, y, (name_col_w - 2) * scale, row_h * scale),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    str(zone_name),
                )
                for col_index, value in enumerate(values):
                    x = (name_col_w + col_index * swatch_w) * scale
                    colour = AnalysisReport._score_class_color(value)
                    painter.fillRect(QRectF(x, y, (swatch_w - 0.4) * scale, (row_h - 0.4) * scale), colour)
        finally:
            painter.end()

        if not hasattr(self, "_temp_matrix_image_paths"):
            self._temp_matrix_image_paths = []
        descriptor, path = tempfile.mkstemp(suffix=".png", prefix="geoe3_score_matrix_")
        os.close(descriptor)
        image.save(path, "PNG")
        self._temp_matrix_image_paths.append(path)
        return path

    @staticmethod
    def _subnational_score_matrix_enabled() -> bool:
        """Whether the user has opted in to the Subnational Score Matrix
        section (Settings > GeoE3) - off by default, since it can add
        many pages for a project with a large number of zones.
        """
        return bool(setting(key="include_subnational_score_matrix", default=False))

    def make_subnational_score_matrix_pages(self, current_page: int) -> int:
        """Add the subnational score matrix: one row per administrative
        zone, one colour-coded cell per used dimension/factor/the
        overall total, paginated across as many pages as needed (there
        is no cap - a fine-grained boundary can mean hundreds of rows),
        with a numbered key explaining each column up front, before the
        table pages themselves.

        Returns:
            current_page, advanced past every page added (0 if the
            project has no subnational boundary / these columns yet).
        """
        result = self._subnational_score_matrix_rows()
        if result is None:
            return current_page
        columns, rows = result
        if not rows:
            return current_page

        self.page_descriptions["subnational_score_matrix"] = (
            "The average score for each admin zone for each dimension, factor and "
            "the analysis total. Column numbers are explained in the key on the "
            "preceding page."
        )

        name_col_w = 48.0
        n_cols = len(columns)
        swatch_w = (CONTENT_W - name_col_w) / n_cols
        row_h = 12.0
        header_h = 16.0
        top = HEADER_H + 24
        rows_per_page = max(1, int((FOOTER_Y - top - header_h) // row_h))

        self.make_page(
            title="Subnational Score Matrix — Key",
            description_key="subnational_score_matrix",
            current_page=current_page,
            show_header_and_footer=True,
        )
        key_rows_per_col = (n_cols + 1) // 2
        key_col_w = CONTENT_W / 2
        key_row_h = 6.0
        key_top = HEADER_H + 24
        for i, (name, _col) in enumerate(columns):
            col, row = divmod(i, key_rows_per_col)
            x = MARGIN + col * key_col_w
            y = key_top + row * key_row_h
            self._label(f"{i + 1}. {name}", x, y, key_col_w - 4, key_row_h, current_page, size=7.5, color=CHARCOAL)
        current_page += 1

        for page_start in range(0, len(rows), rows_per_page):
            page_rows = rows[page_start : page_start + rows_per_page]
            self.make_page(
                title="Subnational Score Matrix",
                description_key="subnational_score_matrix",
                current_page=current_page,
                show_header_and_footer=True,
            )
            image_path = self._render_score_matrix_page_image(page_rows, n_cols, name_col_w, swatch_w, row_h, header_h)
            self._place_picture(
                image_path,
                x=MARGIN,
                y=top,
                w=name_col_w + n_cols * swatch_w,
                h=header_h + len(page_rows) * row_h,
                page=current_page,
            )
            current_page += 1

        return current_page

    def _methodology_entries(self) -> list:
        """Every used indicator in this analysis, grouped by the
        computation technique behind its analysis_mode (see
        geest.core.reports.methodology) - in TECHNIQUES' own order, and
        only the techniques this project actually uses.

        Returns:
            [(technique_key, [(indicator_name, nuance), ...]), ...]
        """
        with open(self.model_path, "r", encoding="utf-8") as f:
            model = json.load(f)

        # A handful of analysis_mode values (national-scale Active
        # Transport) use a different technique depending on the
        # project's own analysis_scale - see technique_for_indicator().
        analysis_scale = model.get("analysis_scale")

        by_technique = {key: [] for key in TECHNIQUES}
        for dimension in model.get("dimensions", []):
            for factor in dimension.get("factors", []):
                for indicator in factor.get("indicators", []):
                    analysis_mode = indicator.get("analysis_mode", "")
                    technique_key = technique_for_indicator(analysis_mode, analysis_scale)
                    if technique_key is None:
                        continue
                    name = indicator.get("indicator", "")
                    by_technique[technique_key].append((name, nuance_for_analysis_mode(analysis_mode)))

        return [(key, entries) for key, entries in by_technique.items() if entries]

    def make_methodology_pages(self, current_page: int) -> int:
        """Add the "Methodology" section: one page per computation
        technique actually used in this analysis, each with a plain-
        language explanation, an illustration, and the list of this
        project's own indicators that use it - grouped by technique
        rather than repeated indicator by indicator, since several
        indicators are collected the same way.
        """
        entries_by_technique = self._methodology_entries()
        if not entries_by_technique:
            return current_page

        self.page_descriptions["methodology_intro"] = (
            "Every grid cell in this analysis has a score from 0 to 5 for each "
            "indicator, combined into factor, dimension and overall scores as shown "
            "below. The pages that follow explain how each indicator actually used "
            "in this analysis was measured - grouped by technique, since several "
            "indicators are collected the same way."
        )
        self.make_page(
            title="Methodology",
            description_key="methodology_intro",
            current_page=current_page,
            show_header_and_footer=True,
        )
        # "How Scores Combine" augments this intro rather than claiming a
        # page of its own - it's the same "how was this calculated"
        # answer as the text above, just as a diagram instead of prose.
        diagram_w = CONTENT_W
        diagram_h = diagram_w * 780.0 / 1000.0
        self._place_picture(
            resources_path("resources", "methodology", "scoring_pipeline.svg"),
            x=MARGIN,
            y=58,
            w=diagram_w,
            h=diagram_h,
            page=current_page,
        )
        current_page += 1

        illustration_size = 46.0
        text_x = MARGIN + illustration_size + 8
        text_w = CONTENT_W - illustration_size - 8

        for technique_key, indicator_entries in entries_by_technique:
            technique = TECHNIQUES[technique_key]
            description_key = f"methodology_{technique_key}"
            self.page_descriptions[description_key] = ""
            self.make_page(
                title=technique["name"],
                description_key=description_key,
                current_page=current_page,
                show_header_and_footer=True,
            )

            top = HEADER_H + 10
            self._place_picture(
                resources_path("resources", "methodology", technique["svg"]),
                x=MARGIN,
                y=top,
                w=illustration_size,
                h=illustration_size,
                page=current_page,
            )
            description_label = self._label(
                f"<p>{technique['description']}</p>",
                text_x,
                top,
                text_w,
                illustration_size,
                current_page,
                size=9.5,
                color=CHARCOAL,
                html=True,
            )
            description_label.setHAlign(Qt.AlignmentFlag.AlignJustify)

            list_top = top + illustration_size + 10
            self._label(
                "Indicators in this analysis that use this technique:",
                MARGIN,
                list_top,
                CONTENT_W,
                6,
                current_page,
                size=9.5,
                color=NAVY,
                bold=True,
            )
            row_pitch = 6.0
            for i, (indicator_name, nuance) in enumerate(indicator_entries):
                y = list_top + 8 + i * row_pitch
                text = f"•  {indicator_name}"
                if nuance:
                    text += f" — {nuance}"
                self._label(text, MARGIN + 4, y, CONTENT_W - 4, row_pitch, current_page, size=8.5, color=CHARCOAL)
            current_page += 1

        return current_page

    def _dimension_factor_weightings(self) -> list:
        """The configured weight of every used dimension within the
        overall analysis, and every used factor within its own
        dimension - read straight from model.json's own
        analysis_weighting/dimension_weighting attributes (the same
        values FactorAggregationWorkflow/DimensionAggregationWorkflow/
        AnalysisAggregationWorkflow use to blend scores together).

        Returns:
            [(dimension_name, dimension_weight_0_to_1,
            [(factor_name, factor_weight_0_to_1), ...]), ...]
        """
        with open(self.model_path, "r", encoding="utf-8") as f:
            model = json.load(f)

        weightings = []
        for dimension in model.get("dimensions", []):
            if not self._has_used_factors(dimension):
                continue
            dimension_weight = float(dimension.get("analysis_weighting", 0.0) or 0.0)
            factor_rows = [
                (factor.get("name", ""), float(factor.get("dimension_weighting", 0.0) or 0.0))
                for factor in dimension.get("factors", [])
                if self._has_used_indicators(factor)
            ]
            weightings.append((dimension.get("name", ""), dimension_weight, factor_rows))
        return weightings

    def make_scoring_weights_page(self, current_page: int) -> int:
        """Add the "Scoring Weights" page: how much each dimension
        counts toward the overall score, and how much each factor
        counts toward its own dimension - the weights this specific
        analysis was configured with, made visible for transparency.
        """
        weightings = self._dimension_factor_weightings()
        if not weightings:
            return current_page

        # Factor rows show a bare percentage, not "x% of <dimension>" - the
        # dimension name is already the header band directly above them,
        # and a long dimension name (e.g. "Place Characterization") made
        # that phrasing wrap onto a second line and crowd the row below.
        rows = []
        for dimension_name, dimension_weight, factor_rows in weightings:
            rows.append((True, dimension_name, f"{dimension_weight * 100:.0f}% of analysis"))
            for factor_name, factor_weight in factor_rows:
                rows.append((False, factor_name, f"{factor_weight * 100:.0f}% of this dimension"))

        self.page_descriptions["scoring_weights"] = (
            "The amount each dimension counts toward the overall GeoE3 score, and the "
            "amount each factor counts toward its own dimension's score - the weights "
            "configured for this analysis."
        )

        row_h = 7.0
        top = HEADER_H + 26
        rows_per_page = max(1, int((FOOTER_Y - top) // row_h))

        for page_start in range(0, len(rows), rows_per_page):
            page_rows = rows[page_start : page_start + rows_per_page]
            self.make_page(
                title="Scoring Weights",
                description_key="scoring_weights",
                current_page=current_page,
                show_header_and_footer=True,
            )
            y = top
            for is_dimension, label, weight_text in page_rows:
                if is_dimension:
                    self._rect(MARGIN, y, CONTENT_W, row_h, NAVY, current_page)
                    self._label(
                        label,
                        MARGIN + 4,
                        y,
                        CONTENT_W - 50,
                        row_h,
                        current_page,
                        size=10,
                        color=WHITE,
                        bold=True,
                        valign=Qt.AlignmentFlag.AlignVCenter,
                    )
                    self._label(
                        weight_text,
                        MARGIN + CONTENT_W - 48,
                        y,
                        44,
                        row_h,
                        current_page,
                        size=9,
                        color=WHITE,
                        halign=Qt.AlignmentFlag.AlignRight,
                        valign=Qt.AlignmentFlag.AlignVCenter,
                    )
                else:
                    self._label(
                        label,
                        MARGIN + 10,
                        y,
                        CONTENT_W - 50,
                        row_h,
                        current_page,
                        size=9,
                        color=CHARCOAL,
                        valign=Qt.AlignmentFlag.AlignVCenter,
                    )
                    self._label(
                        weight_text,
                        MARGIN + CONTENT_W - 48,
                        y,
                        44,
                        row_h,
                        current_page,
                        size=8.5,
                        color=GREY,
                        halign=Qt.AlignmentFlag.AlignRight,
                        valign=Qt.AlignmentFlag.AlignVCenter,
                    )
                y += row_h
            current_page += 1

        return current_page

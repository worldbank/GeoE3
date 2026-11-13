# -*- coding: utf-8 -*-
"""📦 Study Area Report module.

This module contains functionality for study area report.
"""

from qgis.core import QgsLayout, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import Qt

from geest.core.h3_utils import h3_cell_area_km2
from geest.utilities import log_message, resources_path

from .base_report import CHARCOAL, CONTENT_W, CYAN, GREY, HEADER_H, MARGIN, MIST, NAVY, BaseReport

# Friendly page titles for the raw GeoPackage layer names.
LAYER_DISPLAY_NAMES = {
    "study_area_bbox": "Study Area Bounding Box",
    "study_area_bboxes": "Part Bounding Boxes",
    "study_area_polygons": "Study Area Polygons",
    "study_area_clip_polygons": "Clip Polygons",
    "chunks": "Processing Chunks",
    "study_area_creation_status": "Creation Timings",
    "ghsl_settlements": "GHSL Settlements",
}


class StudyAreaReport(BaseReport):
    """
    A class to generate a PDF report from a GeoPackage table of study area creation status data.

    The report computes summary statistics (based on the field "geom_total_duration_secs")
    and creates a QGIS layout (report) that is then exported to PDF.
    """

    def __init__(self, gpkg_path: str, report_name="Study Area Creation Report"):
        """
        Initialize the report.

        Parameters:
            layer_input (str): A file path to the GeoPackage (from which the
                layer "study_area_creation_status" and other layers will be loaded).
            report_name (str): The title to use for the report.

        Raises:
            ValueError: If the layer cannot be loaded from the given file path.
            TypeError: If layer_input is neither a string nor a QgsVectorLayer.
        """
        # Shares the analysis report cover (artwork + frosted title panel)
        # so the two reports form a matched set.
        template_path = resources_path("resources", "qpt", "analysis_summary_report_template.qpt")
        super().__init__(template_path, report_name)

        self.layers = None  # Will hold the loaded layers from the GeoPackage

        uri = f"{gpkg_path}|layername=study_area_creation_status"
        self.gpkg_path = gpkg_path
        layer = QgsVectorLayer(uri, "study_area_creation_status", "ogr")
        if not layer.isValid():
            raise ValueError("Failed to load layer from the given file path.")

        self.report_name = report_name
        self.load_layers_from_gpkg()
        self.page_descriptions = {}
        self.page_descriptions[
            "summary"
        ] = """
        How long each step of the study area preparation took, followed by the
        processed study area itself. Each internal data product used by the
        analysis is described on the pages that follow.
        """
        self.page_descriptions[
            "study_area_bbox"
        ] = """
        The study area bounding box (bbox) is the outer extent of the entire study area.
        The bounding box width and height is guaranteed to be a factor of the
        analysis dimension. All other data products are then aligned to this bbox.
        """
        self.page_descriptions[
            "study_area_bboxes"
        ] = """
        The study area bboxes are a set of smaller bounding boxes that surround each
        polygon in the study area. They are grid aligned such that the origin and
        furthest corners are guaranteed to be a factor of the analysis dimension
        apart.
        """
        self.page_descriptions[
            "study_area_polygons"
        ] = """
        The study area polygons are the single part form of all polygons in the
        study area. Any invalid geometries will have been discarded.
        """
        self.page_descriptions[
            "study_area_grid"
        ] = """
        The study area grid is a set of polygon squares that each have the
        x and y dimension of the analysis cell size. They are guaranteed to
        be aligned to the study area bbox and bboxes layers. The grid is used
        to create a version of the study_area_polygons that have been expanded
        out so that the edges align exactly to the grid.

        The grid is also used to perform certain types of spatial analysis such as
        the Active Transport layer analyses.
        """
        self.page_descriptions[
            "chunks"
        ] = """
        The chunks are the result of splitting the study area grid into smaller
        chunks that are used to process the study area more efficiently. Each chunk
        is labelled as to whether it is inside, on the edge of, or outside the
        geometry of a study area polygon. Grid cells in chunks that are 'inside' can be processed
        more efficiently as we can skip the intersection test with the study area polygons.
        """
        self.page_descriptions[
            "study_area_clip_polygons"
        ] = """
        The study area clip polygons are the original polygon areas but expanded so that the edges
        of the polygon exactly coincide with the edges of the grid. This will ensure that all analysis
        results are coherant with the grid."""
        self.page_descriptions[
            "study_area_creation_status"
        ] = """
        The study area creation status is a record of the time taken to process each part of the study area.
        """
        self.page_descriptions[
            "ghsl_settlements"
        ] = """
        The Global Human Settlement Layer is used to identify settled areas within the study region. Study area polygons are marked with whether they intersect GHSL settlement data, which is used in various analysis workflows.
        """
        self.page_descriptions[
            "grid_summary"
        ] = """
        Key facts about the study area and the analysis grid built from it.
        """
        self._cleanup_done = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup happens."""
        self.cleanup()
        return False  # Don't suppress exceptions

    def cleanup(self):
        """
        Explicitly clean up layers. Call this when done with the report,
        or use the context manager pattern.
        """
        if self._cleanup_done:
            return
        if self.layers:
            for layer_name, layer in self.layers.items():
                if layer and layer.isValid():
                    try:
                        QgsProject.instance().removeMapLayer(layer.id())
                        log_message(f"Layer '{layer_name}' removed from project.")
                    except Exception as e:
                        log_message(f"Could not remove layer '{layer_name}': {e}")
            self.layers = None
        self._cleanup_done = True

    def compute_ghsl_statistics(self):
        """
        Compute GHSL intersection statistics from the study_area_polygons layer.

        Returns:
            dict: A dictionary containing 'total', 'intersects', 'percentage', and 'has_ghsl'.
                  Returns None if GHSL data is not available.
        """
        uri = f"{self.gpkg_path}|layername=study_area_polygons"
        layer = QgsVectorLayer(uri, "study_area_polygons", "ogr")

        if not layer.isValid():
            return None

        # Check if intersects_ghsl field exists
        field_names = [field.name() for field in layer.fields()]
        if "intersects_ghsl" not in field_names:
            return None

        total_count = 0
        intersects_count = 0

        for feat in layer.getFeatures():
            total_count += 1
            intersects_ghsl = feat["intersects_ghsl"]
            if intersects_ghsl == 1:
                intersects_count += 1

        if total_count == 0:
            return None

        percentage = (intersects_count / total_count) * 100

        return {
            "total": total_count,
            "intersects": intersects_count,
            "percentage": percentage,
            "has_ghsl": True,
        }

    def compute_study_area_creation_statistics(self, field_name="geom_total_duration_secs"):
        """
        Compute statistical summary for a given field in the layer.

        Parameters:
            field_name (str): The attribute field on which to compute statistics.

        Returns:
            dict: A dictionary containing 'count', 'min', 'max', 'mean', 'sum', and 'std_dev'.
        """
        values = []
        uri = f"{self.gpkg_path}|layername=study_area_creation_status"
        layer = QgsVectorLayer(uri, "study_area_creation_status", "ogr")
        for feat in layer.getFeatures():
            val = feat[field_name]
            if val is not None:
                values.append(val)
        if not values:
            raise ValueError(f"No valid data found for field '{field_name}'.")

        count_val = len(values)
        sum_val = sum(values)
        min_val = min(values)
        max_val = max(values)
        mean_val = sum_val / count_val
        # Compute population standard deviation
        var = sum((x - mean_val) ** 2 for x in values) / count_val
        std_dev = var**0.5

        return {
            "count": count_val,
            "min": min_val,
            "max": max_val,
            "mean": mean_val,
            "sum": sum_val,
            "std_dev": std_dev,
        }

    def add_ghsl_info_to_page(self, current_page, y: float = 214):
        """Add GHSL statistics and attribution as a styled panel.

        Parameters:
            current_page (int): The page number where the GHSL info should be added.
            y (float): Top of the panel in mm.
        """
        ghsl_stats = self.compute_ghsl_statistics()
        if not ghsl_stats:
            return
        panel_h = 42
        self._rect(MARGIN, y, CONTENT_W, panel_h, MIST, current_page)
        self._rect(MARGIN, y, 2.2, panel_h, CYAN, current_page)
        self._label(
            "Settlement coverage",
            MARGIN + 8,
            y + 4.5,
            CONTENT_W - 16,
            7,
            current_page,
            size=12,
            color=NAVY,
            bold=True,
        )
        self._label(
            f"<p>{ghsl_stats['intersects']} of {ghsl_stats['total']} study area parts "
            f"({ghsl_stats['percentage']:.1f}%) intersect GHSL settlement data.<br/>"  # noqa E231
            "Source: Copernicus / EC JRC — GHS-SMOD R2023A, licensed CC BY 4.0.</p>",
            MARGIN + 8,
            y + 13,
            CONTENT_W - 16,
            panel_h - 17,
            current_page,
            size=9.5,
            color=CHARCOAL,
            html=True,
        )

    def make_summary_page(self, current_page: int) -> int:
        """Add the summary page: creation statistics as stat cards over a map.

        Returns the next free page number.
        """
        self.make_page(
            title="Study Area Summary",
            description_key="summary",
            current_page=current_page,
            show_header_and_footer=True,
        )
        stats = self.compute_study_area_creation_statistics()
        cards = [
            (f"{stats['count']}", "Parts processed"),
            (f"{stats['sum']:.1f} s", "Total processing time"),  # noqa E231
            (f"{stats['mean']:.1f} s", "Average per part"),  # noqa E231
            (f"{stats['min']:.1f} s", "Fastest part"),  # noqa E231
            (f"{stats['max']:.1f} s", "Slowest part"),  # noqa E231
            (f"{stats['std_dev']:.1f} s", "Standard deviation"),  # noqa E231
        ]
        card_w = 56
        card_h = 24
        gap = (CONTENT_W - 3 * card_w) / 2
        top = HEADER_H + 26
        for i, (value, caption) in enumerate(cards):
            x = MARGIN + (i % 3) * (card_w + gap)
            y = top + (i // 3) * (card_h + 6)
            self._rect(x, y, card_w, card_h, MIST, current_page)
            self._rect(x, y, card_w, 1.4, CYAN, current_page)
            self._label(
                value,
                x,
                y + 4,
                card_w,
                10,
                current_page,
                size=15,
                color=NAVY,
                bold=True,
                halign=Qt.AlignmentFlag.AlignHCenter,
            )
            self._label(
                caption,
                x,
                y + 15.5,
                card_w,
                6,
                current_page,
                size=8,
                color=GREY,
                halign=Qt.AlignmentFlag.AlignHCenter,
            )
        polygons_layer = self.layers.get("study_area_polygons")
        if polygons_layer:
            self.make_map(
                layers=[polygons_layer],
                crs=polygons_layer.crs(),
                current_page=current_page,
                x=MARGIN,
                y=top + 2 * card_h + 14,
                map_width_mm=CONTENT_W,
                map_height_mm=160,
            )
        return current_page + 1

    def _grid_facts(self) -> list:
        """Key facts about the study area and its analysis grid, for the closing summary page.

        Everything here is read straight from the GeoPackage - area
        names from study_area_polygons, grid type/resolution/cell size
        from study_area_grid - so this report stays self-contained from
        the GeoPackage alone, the same as the rest of this module,
        rather than also needing model.json.

        Returns:
            A list of (label, value) pairs, or [] if the grid isn't
            available.
        """
        grid_layer = self.layers.get("study_area_grid") if self.layers else None
        if not grid_layer or not grid_layer.isValid():
            return []
        cell_count = grid_layer.featureCount()
        if cell_count == 0:
            return []

        first_feature = next(grid_layer.getFeatures(), None)
        field_names = {field.name() for field in grid_layer.fields()}
        h3_resolution = None
        if first_feature is not None and "h3_resolution" in field_names:
            h3_resolution = first_feature["h3_resolution"]

        facts = []

        polygons_layer = self.layers.get("study_area_polygons") if self.layers else None
        area_names = []
        if polygons_layer and polygons_layer.isValid():
            polygon_field_names = {field.name() for field in polygons_layer.fields()}
            if "area_name" in polygon_field_names:
                area_names = sorted({feat["area_name"] for feat in polygons_layer.getFeatures() if feat["area_name"]})
        if area_names:
            label = "Study area" if len(area_names) == 1 else f"Study areas ({len(area_names)})"
            facts.append((label, ", ".join(area_names)))

        facts.append(("Number of grid cells", f"{cell_count:,}"))

        if h3_resolution:
            facts.append(("Grid type", "H3 hexagonal"))
            facts.append(("H3 resolution", str(h3_resolution)))
            cell_area_km2 = h3_cell_area_km2(int(h3_resolution))
            facts.append(("Average cell area", f"{cell_area_km2:,.3f} km²"))
            facts.append(("Total analysis area", f"{cell_count * cell_area_km2:,.0f} km²"))
        else:
            facts.append(("Grid type", "Square"))
            if first_feature is not None and first_feature.hasGeometry():
                cell_size_m = first_feature.geometry().boundingBox().width()
                facts.append(("Grid cell size", f"{cell_size_m:,.0f} m × {cell_size_m:,.0f} m"))
                total_area_km2 = cell_count * (cell_size_m**2) / 1_000_000
                facts.append(("Total analysis area", f"{total_area_km2:,.0f} km²"))

        crs = grid_layer.crs()
        crs_label = f"{crs.authid()} — {crs.description()}" if crs.authid() else crs.description()
        if crs_label:
            facts.append(("Coordinate reference system", crs_label))

        return facts

    def make_grid_summary_page(self, current_page: int) -> int:
        """Add the closing page: key facts about the study area and the analysis grid.

        Mirrors AnalysisReport.make_study_area_summary_page() - the two
        reports show the same kind of "how was this built" facts, one at
        study-area-creation time and the other after the analysis runs.

        Returns:
            The next free page number (unchanged if the page was skipped).
        """
        facts = self._grid_facts()
        if not facts:
            log_message("No grid facts available - grid summary page skipped", tag="GeoE3")
            return current_page

        self.make_page(
            title="Grid Summary",
            description_key="grid_summary",
            current_page=current_page,
            show_header_and_footer=True,
        )

        row_top = HEADER_H + 30
        row_pitch = 14
        for i, (label, value) in enumerate(facts):
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
        return current_page + 1

    def create_layout(self):
        """
        Create a QGIS layout (report) with a styled cover, credits, a summary
        page, and one page per internal data product.

        The layout is stored in the attribute self.layout.
        """
        project = QgsProject.instance()
        self.layout = QgsLayout(project)
        self.layout.initializeDefaults()
        self.load_template()
        self.style_cover_page()

        self.make_credits_page(current_page=1)
        current_page = self.make_summary_page(current_page=2)

        # One page per remaining layer. The grid is skipped (too many
        # features to render); the polygons layer is the summary page's map.
        layers_to_skip = {"study_area_grid", "study_area_polygons"}
        for layer_name, layer in self.layers.items():
            if layer_name in layers_to_skip:
                log_message(f"Skipping layer '{layer_name}' in report")
                continue
            title = LAYER_DISPLAY_NAMES.get(layer_name, layer_name.replace("_", " ").title())
            self.make_page(
                title=title,
                description_key=layer_name,
                current_page=current_page,
                show_header_and_footer=True,
            )
            if layer_name == "study_area_creation_status":
                self.make_text_table(
                    vector_layer=layer,
                    sort_column="geom_total_duration_secs",
                    current_page=current_page,
                )
            elif layer_name == "ghsl_settlements":
                self.make_map(
                    layers=[layer],
                    crs=layer.crs(),
                    current_page=current_page,
                    x=MARGIN,
                    y=64,
                    map_width_mm=CONTENT_W,
                    map_height_mm=140,
                )
                self.add_ghsl_info_to_page(current_page)
            else:
                self.make_map(
                    layers=[layer],
                    crs=layer.crs(),
                    current_page=current_page,
                    x=MARGIN,
                    y=64,
                    map_width_mm=CONTENT_W,
                    map_height_mm=195,
                )
            current_page += 1

        # Closes the report, same as AnalysisReport's own study area
        # summary page - key facts about the study area and the grid
        # built from it, so a reader can judge its resolution and scope
        # without opening the GeoPackage themselves.
        self.make_grid_summary_page(current_page)

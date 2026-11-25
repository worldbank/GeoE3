# -*- coding: utf-8 -*-
"""📦 Single Buffer Configuration Widget module.

This module contains functionality for single buffer configuration widget.
"""

import traceback

from qgis.core import Qgis
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QHBoxLayout, QLabel, QSpinBox

from geest.core.workflows.mappings import MAPPING_REGISTRY
from geest.utilities import log_message

from .base_configuration_widget import BaseConfigurationWidget, legend_cell_html


class SingleBufferConfigurationWidget(BaseConfigurationWidget):
    """
    A specialized radio button with additional QSpinBox buffer distance.
    """

    @staticmethod
    def _generate_scale_table_html(scale_label: str, config: dict) -> str:
        """Render one scale's own table: percentage-overlap scoring
        (Regional - a single buffer distance, scored by how much of the
        cell it covers) or binary in/out-of-buffer scoring (National/
        Local).

        Args:
            scale_label: Heading text for this table (e.g. "Regional
                (current)").
            config: That scale's config dict from the mappings module.

        Returns:
            HTML for this one scale's table.
        """
        buffer_distance = config.get("buffer_distance")
        scores = config.get("scores", {})
        scoring_method = config.get("scoring_method", "")
        percentage_scores = config.get("percentage_scores", {})

        if scoring_method == "percentage_intersection" and percentage_scores:
            html = f"""
            <p><b>{scale_label} Scale</b></p>
            <table border='1' cellpadding='4' cellspacing='0'>
                <tr><th>Coverage Percentage</th><th>Score</th><th>Legend</th></tr>
            """
            # Ranges are computed ascending (each one needs the previous,
            # lower threshold), then displayed highest-score-first to
            # match the National/Local tables below (their own "scores"
            # list is already ordered that way - worldbank/GeoE3 field
            # report, 2026-11-25).
            sorted_thresholds = sorted(percentage_scores.items())
            prev_pct = 0
            rows = []
            for i, (min_pct, score) in enumerate(sorted_thresholds):
                if score == 0:
                    pct_range = "0% (no intersection)"
                elif i == len(sorted_thresholds) - 1:
                    pct_range = f"{prev_pct + 0.01:.2f}% - 100%"
                elif prev_pct == 0:
                    pct_range = f"0.01% - {min_pct:.2f}%"
                else:
                    pct_range = f"{prev_pct + 0.01:.2f}% - {min_pct:.2f}%"
                rows.append(f"<tr><td>{pct_range}</td><td>{score}</td>{legend_cell_html(score)}</tr>")
                prev_pct = min_pct
            html += "".join(reversed(rows))
            html += "</table>"
        else:
            inside_score = scores.get("intersects", 0)
            outside_score = scores.get("no_intersection", 0)
            html = f"""
            <p><b>{scale_label} Scale</b></p>
            <table border='1' cellpadding='4' cellspacing='0'>
                <tr><th>Distance Range (m)</th><th>Score</th><th>Legend</th></tr>
                <tr><td>≤ {buffer_distance}</td><td>{inside_score}</td>{legend_cell_html(inside_score)}</tr>
                <tr><td>&gt; {buffer_distance}</td><td>{outside_score}</td>{legend_cell_html(outside_score)}</tr>
            </table>
            """
        return html

    def _add_mapping_thresholds_table(self) -> None:
        """
        Adds reference tables for all three scales side by side - labelling
        whichever matches this project's actual analysis_scale as
        "(current)", since Regional's scoring method (a single buffer
        distance scored by percentage overlap) is genuinely different from
        National/Local's binary in/out-of-buffer scoring, not just a
        smaller/larger number (worldbank/GeoE3 field report, 2026-11-25 -
        same fix as MultiBufferConfigurationWidget, applied here since
        WATER_SANITATION_ACCESS has the identical national/local-vs-
        regional split).
        """
        self.mapping_buffer_distance = None
        try:
            analysis_scale = self.attributes.get("analysis_scale") or "national"
            factor_id = self.attributes.get("factor_id")
            factor_name = self.attributes.get("factor_name") or "Single Buffer Analysis"

            mapping = MAPPING_REGISTRY.get(factor_id) if factor_id else None
            if not mapping:
                return

            selected_config = mapping.get(analysis_scale, mapping.get("national"))
            if selected_config:
                buffer_distance = selected_config.get("buffer_distance")
                if buffer_distance is not None:
                    self.mapping_buffer_distance = buffer_distance

            html = f"<p><b>{factor_name}</b></p>"
            html += '<table border="0" cellpadding="5" cellspacing="0"><tr>'
            for scale_name, scale_label in (
                ("regional", "Regional"),
                ("national", "National"),
                ("local", "Local"),
            ):
                config = mapping.get(scale_name)
                if not config:
                    continue
                if scale_name == analysis_scale:
                    scale_label = f"{scale_label} (current)"
                html += '<td valign="top">'
                html += self._generate_scale_table_html(scale_label, config)
                html += "</td>"
            html += "</tr></table>"
            html += "<p><i>Note: You can override the current scale's default below</i></p>"

            self.mapping_table_label = QLabel()
            self.mapping_table_label.setWordWrap(True)
            self.mapping_table_label.setTextFormat(Qt.TextFormat.RichText)
            self.mapping_table_label.setText(html)
            self.internal_layout.addWidget(self.mapping_table_label)

        except Exception as e:
            log_message(f"Error adding mapping thresholds table: {e}", level=Qgis.Warning)
            log_message(traceback.format_exc(), level=Qgis.Warning)

    def add_internal_widgets(self) -> None:
        """
        Adds internal widgets specific to self.set_internal_widgets_visible(self.isChecked()) - in this case there are none.
        """
        try:

            self._add_mapping_thresholds_table()

            # Travel Increments input
            self.buffer_distance_layout = QHBoxLayout()
            self.buffer_distance_label = QLabel("Buffer Distance (m):")
            self.buffer_distance_input = QSpinBox()
            self.buffer_distance_input.setRange(0, 100000)
            self.buffer_distance_layout.addWidget(self.buffer_distance_label)
            self.buffer_distance_layout.addWidget(self.buffer_distance_input)
            default_distance = self.attributes.get("default_single_buffer_distance", 0)
            buffer_distance = self.attributes.get("single_buffer_point_layer_distance", default_distance)
            if buffer_distance == 0:
                buffer_distance = default_distance
            if self.mapping_buffer_distance is not None and buffer_distance == default_distance:
                buffer_distance = self.mapping_buffer_distance
            try:
                self.buffer_distance_input.setValue(int(buffer_distance))
            except (ValueError, TypeError):
                self.buffer_distance_input.setValue(int(default_distance))

            # Add all layouts to the main layout
            self.internal_layout.addLayout(self.buffer_distance_layout)
            self.buffer_distance_input.valueChanged.connect(self.update_data)

        except Exception as e:
            log_message(f"Error in add_internal_widgets: {e}", level=Qgis.Critical)
            log_message(traceback.format_exc(), level=Qgis.Critical)

    def get_data(self) -> dict:
        """
        Return the data as a dictionary, updating attributes with current value.
        """
        if not self.isChecked():
            return None

        self.attributes["single_buffer_point_layer_distance"] = self.buffer_distance_input.value()

        return self.attributes

    def set_internal_widgets_enabled(self, enabled: bool) -> None:
        """
        Enables or disables the internal widgets based on the state of the radio button.
        """
        try:
            self.buffer_distance_input.setEnabled(enabled)
            self.buffer_distance_label.setEnabled(enabled)
        except Exception as e:
            log_message(
                f"Error in set_internal_widgets_enabled: {e}",
                tag="GeoE3",
                level=Qgis.Critical,
            )

    def update_widgets(self, attributes: dict) -> None:
        """
        Updates the internal widgets with the current attributes.

        Only needed in cases where a) there are internal widgets and b)
        the attributes may change externally e.g. in the datasource widget.
        """
        pass

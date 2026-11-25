# -*- coding: utf-8 -*-
"""Regression test for the single-buffer configuration widget's reference
table only ever showing the currently-active scale - the same class of
bug fixed in MultiBufferConfigurationWidget (worldbank/GeoE3 field
report, 2026-11-25): WATER_SANITATION_ACCESS's "regional" entry uses a
genuinely different scoring method (percentage overlap of a single
buffer, not binary in/out-of-buffer like national/local), so showing
only the active scale's table gave no way to see how it differs from
the other two. Now shows all three side by side, labelling whichever
matches the project's actual analysis_scale as "(current)".
"""
import unittest

from utilities_for_testing import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()

from geest.gui.widgets.configuration_widgets.single_buffer_configuration_widget import (  # noqa: E402
    SingleBufferConfigurationWidget,
)


def _make_widget(analysis_scale):
    attributes = {
        "id": "Water_Sanitation",
        "factor_id": "water_sanitation",
        "factor_name": "Water Sanitation",
        "analysis_scale": analysis_scale,
        "default_single_buffer_distance": 0,
    }
    return SingleBufferConfigurationWidget("use_single_buffer_point", attributes, parent=PARENT)


class TestSingleBufferConfigurationWidgetScaleTables(unittest.TestCase):
    def test_all_three_scales_are_shown_regardless_of_which_is_active(self):
        widget = _make_widget("regional")

        html = widget.mapping_table_label.text()

        self.assertIn("Regional", html)
        self.assertIn("National", html)
        self.assertIn("Local", html)

    def test_regional_scale_is_labelled_current_on_a_regional_project(self):
        widget = _make_widget("regional")

        html = widget.mapping_table_label.text()

        self.assertIn("Regional (current)", html)
        self.assertNotIn("National (current)", html)
        self.assertNotIn("Local (current)", html)

    def test_local_scale_is_labelled_current_on_a_local_project(self):
        widget = _make_widget("local")

        html = widget.mapping_table_label.text()

        self.assertIn("Local (current)", html)
        self.assertNotIn("Regional (current)", html)
        self.assertNotIn("National (current)", html)

    def test_regional_table_shows_percentage_scoring_not_binary(self):
        widget = _make_widget("regional")

        html = widget.mapping_table_label.text()

        self.assertIn("Coverage Percentage", html)

    def test_regional_table_does_not_repeat_the_buffer_distance(self):
        """Redundant with (and can go stale against) the input box
        below, and broke the three-column layout alignment since none
        of the other scales have an equivalent line (worldbank/GeoE3
        field report, 2026-11-25)."""
        widget = _make_widget("regional")

        html = widget.mapping_table_label.text()

        self.assertNotIn("Buffer Distance", html)

    def test_national_table_shows_binary_distance_scoring(self):
        widget = _make_widget("national")

        html = widget.mapping_table_label.text()

        self.assertIn("Distance Range (m)", html)

    def test_the_buffer_distance_still_matches_only_the_active_scale(self):
        widget = _make_widget("regional")

        self.assertEqual(widget.mapping_buffer_distance, 3000)


if __name__ == "__main__":
    unittest.main()

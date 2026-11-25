# -*- coding: utf-8 -*-
"""Regression test for the multi-buffer configuration widget's reference
table always showing National/Local regardless of the project's actual
scale - a Regional-scale project's input box holds a single buffer
distance (that scale's own scoring method, percentage-overlap against
one buffer, is genuinely different from national/local's distance-ring
thresholds), but the table above it never showed the Regional config
driving that value at all, only National and Local (neither of which
applies). Fixed by always showing all three, labelling whichever one
matches the project's actual analysis_scale as "(current)"
(worldbank/GeoE3 field report, 2026-11-25).
"""
import tempfile
import unittest

from utilities_for_testing import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()

from qgis.PyQt.QtCore import QSettings  # noqa: E402

from geest.gui.widgets.configuration_widgets.multi_buffer_configuration_widget import (  # noqa: E402
    MultiBufferConfigurationWidget,
)


def _make_widget(analysis_scale):
    attributes = {
        "id": "Primary_School_Location",
        "factor_id": "women_s_travel_patterns",
        "factor_name": "Women's Travel Patterns",
        "analysis_scale": analysis_scale,
    }
    return MultiBufferConfigurationWidget("use_multi_buffer_point", attributes, parent=PARENT)


class TestMultiBufferConfigurationWidgetScaleTables(unittest.TestCase):
    def setUp(self):
        # _add_mapping_thresholds_table() falls back to reading
        # analysis_scale from a model.json at last_working_directory if
        # one exists there - point it somewhere empty so these tests
        # deterministically use the analysis_scale passed in attributes,
        # not whatever another test left behind.
        self._empty_dir = tempfile.mkdtemp(prefix="test_multi_buffer_widget_")
        QSettings().setValue("last_working_directory", self._empty_dir)

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

    def test_national_scale_is_labelled_current_on_a_national_project(self):
        widget = _make_widget("national")

        html = widget.mapping_table_label.text()

        self.assertIn("National (current)", html)
        self.assertNotIn("Regional (current)", html)
        self.assertNotIn("Local (current)", html)

    def test_regional_table_shows_its_own_buffer_distance_and_percentage_scoring(self):
        """Regional's table must render its OWN scoring method (a single
        buffer distance + percentage-overlap bands), not be silently
        skipped or rendered as an empty/broken distance-ring table.

        The buffer distance itself is deliberately NOT repeated here -
        it's redundant with (and can go stale against) the input box
        below, and broke the three-column layout alignment since none
        of the other scales have an equivalent line (worldbank/GeoE3
        field report, 2026-11-25).
        """
        widget = _make_widget("regional")

        html = widget.mapping_table_label.text()

        self.assertIn("Coverage Percentage", html)
        self.assertNotIn("Buffer Distance", html)

    def test_the_input_box_still_holds_only_the_regional_buffer_distance(self):
        """The fix is to the reference table only - the input box itself
        must still hold exactly the active scale's own value, a single
        number for Regional, not a comma-separated list."""
        widget = _make_widget("regional")

        self.assertEqual(widget.increments_input.text(), "1500")


if __name__ == "__main__":
    unittest.main()

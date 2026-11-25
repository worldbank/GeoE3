# -*- coding: utf-8 -*-
"""Unit tests for TreePanel's per-item context menu gating.

"Add to map"/"Add to map (Grid)"/"Add GeoE3 Score to Map" and "Clear
Item" stayed clickable for an item with nothing behind them (never
configured, never run, or a failed run) - clicking did nothing useful.
This applies at every level of the tree (indicator, factor, dimension,
analysis), see TreePanel._item_has_a_result()/_item_has_clearable_output()
(worldbank/GeoE3 field report, 2026-11-25).
"""
import unittest

from geest.core.json_tree_item import JsonTreeItem
from geest.gui.panels.tree_panel import TreePanel


def _indicator(**attrs) -> JsonTreeItem:
    """A single indicator with a minimal dimension/factor parent chain."""
    base = {
        "id": "ind",
        "analysis_mode": "use_nighttime_lights",
        "factor_weighting": 1.0,
        "result": "",
        "result_file": "",
    }
    base.update(attrs)
    dimension = JsonTreeItem(["Dim", "Configured", 1.0, {"id": "dim", "analysis_weighting": 1.0}], role="dimension")
    factor = JsonTreeItem(
        ["Factor", "Configured", 1.0, {"id": "fac", "dimension_weighting": 1.0}],
        role="factor",
        parent=dimension,
    )
    dimension.appendChild(factor)
    indicator = JsonTreeItem(["Indicator", "Configured", 1.0, base], role="indicator", parent=factor)
    factor.appendChild(indicator)
    return indicator


class TestItemHasAResult(unittest.TestCase):
    def test_false_when_never_configured(self):
        item = _indicator(analysis_mode="Not Configured")
        self.assertFalse(TreePanel._item_has_a_result(item))

    def test_false_when_configured_but_not_run(self):
        item = _indicator(result="Not Run", result_file="")
        self.assertFalse(TreePanel._item_has_a_result(item))

    def test_false_when_the_last_run_failed(self):
        item = _indicator(result="Workflow Failed: boom", result_file="", error="boom")
        self.assertFalse(TreePanel._item_has_a_result(item))

    def test_true_when_completed_successfully(self):
        item = _indicator(result="use_nighttime_lights Workflow Completed", result_file="study_area/out.tif")
        self.assertTrue(TreePanel._item_has_a_result(item))


class TestItemHasClearableOutput(unittest.TestCase):
    def test_false_when_never_run(self):
        item = _indicator(result="Not Run", result_file="")
        self.assertFalse(TreePanel._item_has_clearable_output(item))

    def test_true_when_a_result_file_exists(self):
        item = _indicator(result="use_nighttime_lights Workflow Completed", result_file="study_area/out.tif")
        self.assertTrue(TreePanel._item_has_clearable_output(item))

    def test_true_when_an_error_is_recorded_even_with_no_result_file(self):
        item = _indicator(result="Workflow Failed: boom", result_file="", error="boom")
        self.assertTrue(TreePanel._item_has_clearable_output(item))


if __name__ == "__main__":
    unittest.main()

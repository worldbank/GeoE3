# -*- coding: utf-8 -*-
"""Unit tests for TreePanel's integrity-check pre-flight gating.

Run All, Run Incomplete, and a single-indicator run must all check the
integrity ontology (working directory, study area grid, network layer)
*before* showing the progress UI - a blocked run should never get as far
as starting at all. This is separate from, and in addition to, the
existing per-indicator configuredness gating in
test_tree_panel_run_all_gating.py.

TreePanel is a heavy QWidget that needs a loaded .ui file to construct,
so these tests call the unbound methods against a lightweight MagicMock
stand-in, following the established pattern in
test_tree_panel_run_all_gating.py.
"""
import tempfile
import types
import unittest
from unittest.mock import MagicMock

from geest.core.json_tree_item import JsonTreeItem
from geest.gui.panels.tree_panel import TreePanel


def _bind(panel, *names):
    for name in names:
        setattr(panel, name, types.MethodType(getattr(TreePanel, name), panel))


def _indicator(analysis_mode: str) -> JsonTreeItem:
    """A single indicator with a minimal dimension/factor parent chain.

    getStatus() treats a parentless indicator as "Excluded from analysis"
    (it reads dimension_weighting/factor_weighting off the parent chain,
    defaulting to 0.0 with no parent at all) - matching
    test_tree_panel_run_all_gating.py's own _build_tree() helper avoids
    that trap the same way.
    """
    dimension = JsonTreeItem(["Dim", "Configured", 1.0, {"id": "dim", "analysis_weighting": 1.0}], role="dimension")
    factor = JsonTreeItem(
        ["Factor", "Configured", 1.0, {"id": "fac", "dimension_weighting": 1.0}],
        role="factor",
        parent=dimension,
    )
    dimension.appendChild(factor)
    indicator = JsonTreeItem(
        [
            "Indicator",
            "Configured",
            1.0,
            {"id": "ind", "analysis_mode": analysis_mode, "factor_weighting": 1.0, "result": "", "result_file": ""},
        ],
        role="indicator",
        parent=factor,
    )
    factor.appendChild(indicator)
    return indicator


class TestBlockRunIfNeeded(unittest.TestCase):
    def setUp(self):
        self.panel = MagicMock()
        self.panel.working_directory = None
        self.panel.road_network_layer_path = MagicMock(return_value=None)
        _bind(self.panel, "_block_run_if_needed", "_collect_integrity_problems")

    def test_no_problems_returns_false_and_does_not_touch_the_info_panel(self):
        blocked = TreePanel._block_run_if_needed(self.panel, [], "Can't run all")

        self.assertFalse(blocked)
        self.panel.item_info_panel.show_blocked.assert_not_called()

    def test_a_problem_returns_true_and_shows_it_with_the_given_heading(self):
        self.panel.working_directory = "/does/not/exist/geoe3-integrity-test-dir"

        blocked = TreePanel._block_run_if_needed(self.panel, [], "Can't run all")

        self.assertTrue(blocked)
        self.panel.item_info_panel.show_blocked.assert_called_once()
        heading, _intro, rows = self.panel.item_info_panel.show_blocked.call_args[0]
        self.assertEqual(heading, "Can't run all")
        self.assertEqual(len(rows), 1)


class TestRunEntryPointsRespectIntegrityBlocking(unittest.TestCase):
    def setUp(self):
        self.panel = MagicMock()
        self.panel.working_directory = None
        self.panel.road_network_layer_path = MagicMock(return_value=None)
        _bind(self.panel, "_block_run_if_needed", "_collect_integrity_problems", "_all_indicators")

    def test_run_all_aborts_before_queueing_when_blocked(self):
        self.panel.working_directory = "/does/not/exist/geoe3-integrity-test-dir"
        self.panel.model.get_analysis_item.return_value = None

        TreePanel.run_all(self.panel)

        self.panel.item_info_panel.show_blocked.assert_called_once()
        self.panel._count_workflows_to_run.assert_not_called()
        self.panel._queue_workflows.assert_not_called()

    def test_run_all_proceeds_when_nothing_is_blocking(self):
        self.panel.model.get_analysis_item.return_value = None

        TreePanel.run_all(self.panel)

        self.panel.item_info_panel.show_blocked.assert_not_called()
        self.panel._queue_workflows.assert_called_once()

    def test_run_incomplete_aborts_before_queueing_when_blocked(self):
        self.panel.working_directory = "/does/not/exist/geoe3-integrity-test-dir"
        self.panel.model.get_analysis_item.return_value = None

        TreePanel.run_incomplete(self.panel)

        self.panel.item_info_panel.show_blocked.assert_called_once()
        self.panel._queue_workflows.assert_not_called()

    def test_run_item_aborts_before_showing_progress_when_blocked(self):
        self.panel.working_directory = "/does/not/exist/geoe3-integrity-test-dir"

        TreePanel.run_item(self.panel, _indicator("use_nighttime_lights"), shift_pressed=False)

        self.panel.item_info_panel.show_blocked.assert_called_once()
        self.panel.item_info_panel.show_progress.assert_not_called()

    def test_run_item_needing_network_is_blocked_when_network_layer_is_unset(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.panel.working_directory = tmp_dir

            TreePanel.run_item(self.panel, _indicator("use_multi_buffer_point"), shift_pressed=False)

        self.panel.item_info_panel.show_blocked.assert_called_once()
        _heading, _intro, rows = self.panel.item_info_panel.show_blocked.call_args[0]
        self.assertIn("network", rows[0][0].lower())

    def test_run_item_not_needing_network_proceeds_when_network_layer_is_unset(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.panel.working_directory = tmp_dir

            TreePanel.run_item(self.panel, _indicator("use_nighttime_lights"), shift_pressed=False)

        self.panel.item_info_panel.show_blocked.assert_not_called()
        self.panel.item_info_panel.show_progress.assert_called_once()


if __name__ == "__main__":
    unittest.main()

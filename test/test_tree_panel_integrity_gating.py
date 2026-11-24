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


def _factor_with_indicators(*indicator_attrs: dict) -> JsonTreeItem:
    """A factor with one indicator per attrs dict given, for testing scope-wide checks.

    Each dict is merged over a "Not Run"/un-configured baseline, so a
    test only needs to specify what makes that one indicator different
    (e.g. {"analysis_mode": "use_nighttime_lights"} for a configured
    one, {} for one left at its unconfigured default).
    """
    dimension = JsonTreeItem(["Dim", "Configured", 1.0, {"id": "dim", "analysis_weighting": 1.0}], role="dimension")
    factor = JsonTreeItem(
        ["Factor", "Configured", 1.0, {"id": "fac", "dimension_weighting": 1.0}],
        role="factor",
        parent=dimension,
    )
    dimension.appendChild(factor)
    for i, attrs in enumerate(indicator_attrs):
        base = {
            "id": f"ind{i}",
            "analysis_mode": "Not Configured",
            "factor_weighting": 1.0,
            "result": "",
            "result_file": "",
        }
        base.update(attrs)
        indicator = JsonTreeItem([f"Indicator{i}", "Configured", 1.0, base], role="indicator", parent=factor)
        factor.appendChild(indicator)
    return factor


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


class TestRunItemActionState(unittest.TestCase):
    """The context menu's "Run Item Workflow" action must already be
    disabled for an item (or any descendant) failing an integrity check -
    not merely blocked after the user clicks it.
    """

    def setUp(self):
        self.panel = MagicMock()
        self.panel.working_directory = None
        self.panel.road_network_layer_path = MagicMock(return_value=None)
        _bind(self.panel, "_run_item_action_state", "_collect_integrity_problems")

    def test_enabled_with_no_problems(self):
        enabled, tooltip = TreePanel._run_item_action_state(
            self.panel, _indicator("use_nighttime_lights"), shift_pressed=False
        )

        self.assertTrue(enabled)
        self.assertEqual(tooltip, "")

    def test_disabled_when_a_global_problem_exists(self):
        self.panel.working_directory = "/does/not/exist/geoe3-integrity-test-dir"

        enabled, tooltip = TreePanel._run_item_action_state(
            self.panel, _indicator("use_nighttime_lights"), shift_pressed=False
        )

        self.assertFalse(enabled)
        self.assertIn("no longer exists", tooltip)

    def test_disabled_when_this_item_needs_the_network_layer_and_it_is_unset(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.panel.working_directory = tmp_dir

            enabled, tooltip = TreePanel._run_item_action_state(
                self.panel, _indicator("use_multi_buffer_point"), shift_pressed=False
            )

        self.assertFalse(enabled)
        self.assertIn("network", tooltip.lower())

    def test_enabled_when_this_item_does_not_need_the_network_layer(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.panel.working_directory = tmp_dir

            enabled, tooltip = TreePanel._run_item_action_state(
                self.panel, _indicator("use_nighttime_lights"), shift_pressed=False
            )

        self.assertTrue(enabled)
        self.assertEqual(tooltip, "")

    def test_disabled_when_no_indicator_in_scope_is_configured(self):
        """worldbank/GeoE3 field report, 2026-11-24: right-clicking a factor
        whose indicators were all still at their unconfigured default and
        choosing "Run Item Workflow" did nothing visible - every indicator
        got silently skipped rather than run. The action itself must
        already be disabled in that case, not merely a no-op once clicked.
        """
        factor = _factor_with_indicators({}, {}, {})

        enabled, tooltip = TreePanel._run_item_action_state(self.panel, factor, shift_pressed=False)

        self.assertFalse(enabled)
        self.assertIn("no configured indicators", tooltip)

    def test_enabled_when_every_indicator_in_scope_is_disabled(self):
        """A fully-disabled factor stays enabled here - getDescendantIndicators(
        include_disabled=False) excludes every disabled child, so the scope
        this check sees is simply empty (nothing to flag as unconfigured).
        Clicking it is still safe: run_item()'s own items_to_run == 0 check
        (see test_tree_panel_run_all_gating.py) shows its own "Nothing to
        run" message once nothing ends up queued."""
        factor = _factor_with_indicators(
            {"analysis_mode": "Do Not Use", "factor_weighting": 0.0},
            {"analysis_mode": "Do Not Use", "factor_weighting": 0.0},
        )

        enabled, tooltip = TreePanel._run_item_action_state(self.panel, factor, shift_pressed=False)

        self.assertTrue(enabled)
        self.assertEqual(tooltip, "")

    def test_enabled_when_at_least_one_indicator_in_scope_is_configured(self):
        """A partial run (some indicators configured, some not) is still
        useful - only block when literally nothing in scope can run."""
        factor = _factor_with_indicators({}, {"analysis_mode": "use_nighttime_lights"})

        enabled, tooltip = TreePanel._run_item_action_state(self.panel, factor, shift_pressed=False)

        self.assertTrue(enabled)
        self.assertEqual(tooltip, "")

    def test_enabled_for_an_already_completed_indicator(self):
        factor = _factor_with_indicators({"result": "Workflow Completed", "result_file": "result.tif"})

        enabled, tooltip = TreePanel._run_item_action_state(self.panel, factor, shift_pressed=False)

        self.assertTrue(enabled)
        self.assertEqual(tooltip, "")


class TestRunItemConfiguredness(unittest.TestCase):
    """run_item() itself must refuse to start for the same reason
    _run_item_action_state() already disables the context menu action for -
    belt and braces in case it's ever reached another way."""

    def setUp(self):
        self.panel = MagicMock()
        self.panel.working_directory = None
        self.panel.road_network_layer_path = MagicMock(return_value=None)
        _bind(self.panel, "run_item", "_block_run_if_needed", "_collect_integrity_problems")

    def test_run_item_refuses_and_shows_blocked_when_nothing_is_configured(self):
        factor = _factor_with_indicators({}, {})

        TreePanel.run_item(self.panel, factor, shift_pressed=False)

        self.panel.item_info_panel.show_blocked.assert_called_once()
        self.panel.queue_manager.add_workflow.assert_not_called()


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Unit tests for TreePanel's Run All gating.

TreePanel is a heavy QWidget that needs a loaded .ui file and a full
JsonTreeModel to construct, so these tests call the unbound methods
against a lightweight stand-in object (with a real JsonTreeItem tree for
the model to walk) instead of a real TreePanel.

Run All must stay disabled while any indicator is "Required and not
configured" or "Not configured (optional)" - the analysis can't produce
a complete result around either. "Workflow failed" is deliberately
allowed through, so a user can retry a failed run without first having
to touch anything.
"""
import types
import unittest
from unittest.mock import MagicMock

from geest.core.json_tree_item import JsonTreeItem
from geest.gui.panels.tree_panel import TreePanel


def _build_tree(indicator_attrs_list):
    """One dimension/factor, with one indicator per attrs dict given."""
    root = JsonTreeItem(["Analysis", "Configured", 1.0, {"id": "analysis"}], role="analysis")
    dimension = JsonTreeItem(
        ["Dimension", "Configured", 1.0, {"id": "dim", "analysis_weighting": 1.0}],
        role="dimension",
        parent=root,
    )
    root.appendChild(dimension)
    factor = JsonTreeItem(
        ["Factor", "Configured", 1.0, {"id": "fac", "dimension_weighting": 1.0}],
        role="factor",
        parent=dimension,
    )
    dimension.appendChild(factor)
    for i, attrs in enumerate(indicator_attrs_list):
        indicator = JsonTreeItem(
            [attrs.get("id", f"Indicator{i}"), "Configured", 1.0, attrs],
            role="indicator",
            parent=factor,
        )
        factor.appendChild(indicator)
    return root


class TestCollectRunAllBlockers(unittest.TestCase):
    def setUp(self):
        self.panel = MagicMock()

    def test_a_configured_and_a_completed_indicator_block_nothing(self):
        root = _build_tree(
            [
                {
                    "id": "A",
                    "analysis_mode": "use_eplex_score",
                    "factor_weighting": 1.0,
                    "result": "",
                    "result_file": "",
                },
                {
                    "id": "B",
                    "analysis_mode": "use_eplex_score",
                    "factor_weighting": 1.0,
                    "result": "Workflow Completed",
                    "result_file": "/some/output.vrt",
                },
            ]
        )
        self.panel.model.get_analysis_item.return_value = root

        blockers = TreePanel._collect_run_all_blockers(self.panel)

        self.assertEqual(blockers, [])

    def test_a_disabled_indicator_blocks_nothing(self):
        root = _build_tree(
            [{"id": "Disabled_One", "analysis_mode": "Do Not Use", "factor_weighting": 0.0}],
        )
        self.panel.model.get_analysis_item.return_value = root

        blockers = TreePanel._collect_run_all_blockers(self.panel)

        self.assertEqual(blockers, [])

    def test_a_failed_indicator_blocks_nothing(self):
        root = _build_tree(
            [
                {
                    "id": "Failed_One",
                    "analysis_mode": "use_eplex_score",
                    "factor_weighting": 1.0,
                    "result": "Workflow Failed: boom",
                }
            ],
        )
        self.panel.model.get_analysis_item.return_value = root

        blockers = TreePanel._collect_run_all_blockers(self.panel)

        self.assertEqual(blockers, [])

    def test_a_required_and_unconfigured_indicator_blocks(self):
        root = _build_tree(
            [{"id": "Needs_Setup", "analysis_mode": "", "factor_weighting": 1.0}],
        )
        self.panel.model.get_analysis_item.return_value = root

        blockers = TreePanel._collect_run_all_blockers(self.panel)

        self.assertEqual(blockers, ["Needs_Setup"])

    def test_an_optional_and_unconfigured_indicator_blocks(self):
        root = _build_tree(
            [{"id": "Optional_Not_Set", "analysis_mode": "use_csv_to_point_layer", "factor_weighting": 1.0}],
        )
        self.panel.model.get_analysis_item.return_value = root

        blockers = TreePanel._collect_run_all_blockers(self.panel)

        self.assertEqual(blockers, ["Optional_Not_Set"])


class TestUpdateRunAllButtonState(unittest.TestCase):
    def setUp(self):
        self.panel = MagicMock()
        self.panel.warning_message_label.text.return_value = ""
        # _update_run_all_button_state() calls self._collect_run_all_blockers()
        # internally - bind the real implementation onto the mock so that
        # resolves to actual logic instead of an auto-mocked stub.
        self.panel._collect_run_all_blockers = types.MethodType(TreePanel._collect_run_all_blockers, self.panel)

    def test_no_blockers_enables_the_button(self):
        self.panel.model.get_analysis_item.return_value = _build_tree([])

        TreePanel._update_run_all_button_state(self.panel)

        self.panel.prepare_analysis_button.setEnabled.assert_called_once_with(True)
        self.panel.show_validation_error.assert_not_called()

    def test_blockers_disable_the_button_and_show_the_banner(self):
        self.panel.model.get_analysis_item.return_value = _build_tree(
            [{"id": "Needs_Setup", "analysis_mode": "", "factor_weighting": 1.0}],
        )

        TreePanel._update_run_all_button_state(self.panel)

        self.panel.prepare_analysis_button.setEnabled.assert_called_once_with(False)
        self.panel.show_validation_error.assert_called_once()
        self.assertIn("Needs_Setup", self.panel.show_validation_error.call_args[0][1])

    def test_clearing_blockers_hides_only_our_own_banner_message(self):
        self.panel.warning_message_label.text.return_value = "<b>Analysis Not Ready:</b> Configure X."
        self.panel.model.get_analysis_item.return_value = _build_tree([])

        TreePanel._update_run_all_button_state(self.panel)

        self.panel.hide_validation_warning.assert_called_once()

    def test_clearing_blockers_leaves_an_unrelated_banner_alone(self):
        self.panel.warning_message_label.text.return_value = "<b>Road Network Issue:</b> file not found."
        self.panel.model.get_analysis_item.return_value = _build_tree([])

        TreePanel._update_run_all_button_state(self.panel)

        self.panel.hide_validation_warning.assert_not_called()


if __name__ == "__main__":
    unittest.main()

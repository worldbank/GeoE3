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
to touch anything. Each blocker is shown in the item info panel with its
own status icon - the same one the tree itself already shows for that
indicator - not a separate top-of-panel banner.
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

        self.assertEqual(blockers, [("Needs_Setup", "Required and not configured")])

    def test_an_optional_and_unconfigured_indicator_blocks(self):
        root = _build_tree(
            [{"id": "Optional_Not_Set", "analysis_mode": "use_csv_to_point_layer", "factor_weighting": 1.0}],
        )
        self.panel.model.get_analysis_item.return_value = root

        blockers = TreePanel._collect_run_all_blockers(self.panel)

        self.assertEqual(blockers, [("Optional_Not_Set", "Not configured (optional)")])


class TestUpdateRunAllButtonState(unittest.TestCase):
    def setUp(self):
        self.panel = MagicMock()
        self.panel.item_info_panel.item_heading_label.text.return_value = ""
        # _update_run_all_button_state() calls self._collect_run_all_blockers()
        # internally - bind the real implementation onto the mock so that
        # resolves to actual logic instead of an auto-mocked stub.
        self.panel._collect_run_all_blockers = types.MethodType(TreePanel._collect_run_all_blockers, self.panel)

    def test_no_blockers_enables_the_button(self):
        self.panel.model.get_analysis_item.return_value = _build_tree([])

        TreePanel._update_run_all_button_state(self.panel)

        self.panel.prepare_analysis_button.setEnabled.assert_called_once_with(True)
        self.panel.item_info_panel.show_run_all_blocked.assert_not_called()

    def test_blockers_disable_the_button_and_populate_the_info_panel(self):
        self.panel.model.get_analysis_item.return_value = _build_tree(
            [{"id": "Needs_Setup", "analysis_mode": "", "factor_weighting": 1.0}],
        )

        TreePanel._update_run_all_button_state(self.panel)

        self.panel.prepare_analysis_button.setEnabled.assert_called_once_with(False)
        self.panel.item_info_panel.show_run_all_blocked.assert_called_once()
        (icon_pairs,) = self.panel.item_info_panel.show_run_all_blocked.call_args[0]
        self.assertEqual(len(icon_pairs), 1)
        name, icon_path = icon_pairs[0]
        self.assertEqual(name, "Needs_Setup")
        self.assertTrue(icon_path.endswith("required-not-configured.svg"))

    def test_clearing_blockers_clears_only_our_own_info_panel_message(self):
        self.panel.item_info_panel.item_heading_label.text.return_value = "Run All is disabled"
        self.panel.model.get_analysis_item.return_value = _build_tree([])

        TreePanel._update_run_all_button_state(self.panel)

        self.panel.item_info_panel.clear.assert_called_once()

    def test_clearing_blockers_leaves_an_unrelated_selection_alone(self):
        self.panel.item_info_panel.item_heading_label.text.return_value = "Some Selected Indicator"
        self.panel.model.get_analysis_item.return_value = _build_tree([])

        TreePanel._update_run_all_button_state(self.panel)

        self.panel.item_info_panel.clear.assert_not_called()


if __name__ == "__main__":
    unittest.main()

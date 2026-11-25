# -*- coding: utf-8 -*-
"""Regression test for TreePanel.on_workflow_completed()'s failure path.

TreePanel is a heavy QWidget that needs a loaded .ui file and a full
JsonTreeModel to construct, so this test calls the unbound method
against a lightweight MagicMock stand-in instead of a real TreePanel,
matching the pattern in test_tree_panel_clear_item.py.

Guards against a real production bug: on_workflow_completed() only
called item.invalidateAncestors() on success - a failed indicator left
every ancestor (factor, dimension, analysis) showing its last cached
"Completed successfully" untouched, since nothing marked them failed
and nothing re-aggregates on its own just because one child's own run
failed. A user running a single broken indicator saw it correctly
marked "Workflow failed", while its parent factor, dimension and the
top-level analysis all kept claiming the run completed normally
(worldbank/GeoE3 field report, 2026-11-25: a Nigeria Regional indicator
with no point layer set).
"""
import unittest
from unittest.mock import MagicMock

from geest.core.json_tree_item import JsonTreeItem
from geest.gui.panels.tree_panel import TreePanel


def _make_item(name, role, parent=None, **attrs):
    data = [name, "Configured", 1.0, {"id": name, "result": "Completed successfully", **attrs}]
    item = JsonTreeItem(data, role=role, parent=parent)
    if parent is not None:
        parent.appendChild(item)
    return item


class TestWorkflowFailureCascadesToAncestors(unittest.TestCase):
    def setUp(self):
        # Every weighting attribute is non-zero so getStatus()'s own
        # "Excluded from analysis" checks don't short-circuit before
        # reaching the failure-marker check this test is about.
        self.analysis = _make_item("Analysis", "analysis")
        self.dimension = _make_item("Accessibility", "dimension", parent=self.analysis, analysis_weighting=1.0)
        self.factor = _make_item("Women's Travel Patterns", "factor", parent=self.dimension, dimension_weighting=1.0)
        self.indicator = _make_item(
            "Location of primary schools",
            "indicator",
            parent=self.factor,
            factor_weighting=1.0,
            analysis_mode="use_multi_buffer_point",
            result="Workflow Error",
            error="No point layer is set for this indicator. Open its data source settings and choose a point layer.",
        )

        self.panel = MagicMock()
        self.panel.items_to_run = 1
        self.panel.overall_progress_bar.value.return_value = 0

    def test_a_failed_indicator_marks_every_ancestor_failed(self):
        TreePanel.on_workflow_completed(self.panel, self.indicator, False)

        for ancestor in (self.factor, self.dimension, self.analysis):
            self.assertEqual(ancestor.getStatus(), "Workflow failed")
            self.assertIn("Location of primary schools", ancestor.attribute("error", ""))

    def test_a_failed_indicator_refreshes_the_tree_view(self):
        TreePanel.on_workflow_completed(self.panel, self.indicator, False)

        self.panel._refresh_tree_view.assert_called_once()

    def test_a_failed_indicator_does_not_invalidate_ancestors_the_success_way(self):
        """invalidateAncestors() clears result/result_file to "" - a failed
        run must use the distinct "Workflow Error" marker instead, not
        that one (which would just read as "Configured, not run")."""
        TreePanel.on_workflow_completed(self.panel, self.indicator, False)

        self.assertNotEqual(self.factor.attribute("result", ""), "")

    def test_a_successful_indicator_still_only_invalidates_not_marks_failed(self):
        """The success path is untouched by this fix."""
        self.indicator.attributes()["result"] = "use_multi_buffer_point Workflow Completed"
        self.indicator.attributes()["error"] = ""
        TreePanel.on_workflow_completed(self.panel, self.indicator, True)

        for ancestor in (self.factor, self.dimension, self.analysis):
            self.assertEqual(ancestor.attribute("result", ""), "")
            self.assertNotEqual(ancestor.getStatus(), "Workflow failed")


if __name__ == "__main__":
    unittest.main()

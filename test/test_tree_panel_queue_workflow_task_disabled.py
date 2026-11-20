# -*- coding: utf-8 -*-
"""Unit test for TreePanel.queue_workflow_task() skipping disabled indicators.

TreePanel is a heavy QWidget that needs a loaded .ui file and a full
JsonTreeModel to construct, so this test calls the unbound method against
a lightweight stand-in item instead of a real TreePanel/JsonTreeItem.

Reproduces a reported bug: EPLEX must never run while women's
considerations are enabled. apply_women_considerations_logic() only
flips is_enabled() (greys the row out, hides the context menu) - it
never touches analysis_mode - so queue_workflow_task(), which only
skipped items explicitly set to "Do Not Use", still queued and ran a
disabled EPLEX indicator's own workflow, producing a real result.
aggregation_workflow_base.py already excludes disabled children from the
weighted combination the same way; queue_workflow_task() must too, or
the indicator's own result still gets computed for no reason.
"""
import unittest
from unittest.mock import MagicMock

from geest.gui.panels.tree_panel import TreePanel


class TestQueueWorkflowTaskSkipsDisabledIndicators(unittest.TestCase):
    def test_disabled_indicator_is_skipped_and_marked_excluded(self):
        item = MagicMock()
        attributes = {"analysis_mode": "use_eplex_score"}
        item.attributes.return_value = attributes
        item.is_enabled.return_value = False
        item.attribute.return_value = "EPLEX_Score"

        panel = MagicMock()

        TreePanel.queue_workflow_task(panel, item, "indicator")

        self.assertEqual(attributes["factor_weighting"], 0.0)
        self.assertEqual(attributes["result"], "Excluded from analysis")
        self.assertEqual(attributes["result_file"], "")

    def test_do_not_use_is_still_skipped_without_checking_is_enabled(self):
        """The pre-existing "Do Not Use" skip must keep working unchanged."""
        item = MagicMock()
        attributes = {"analysis_mode": "Do Not Use"}
        item.attributes.return_value = attributes
        item.is_enabled.return_value = True
        item.attribute.return_value = "Some_Indicator"

        panel = MagicMock()

        TreePanel.queue_workflow_task(panel, item, "indicator")

        self.assertEqual(attributes["factor_weighting"], 0.0)
        self.assertEqual(attributes["result"], "Excluded from analysis")


if __name__ == "__main__":
    unittest.main()

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

Also reproduces a second, related bug in the same function: "Do Not
Use" covers both an explicitly-disabled indicator AND one that was
simply never configured yet - zeroing factor_weighting/marking it
"Excluded from analysis" for both conflated the two, permanently
excluding a never-configured indicator (and, by extension, its parent
factor once every child's weighting summed to zero) just from
attempting a run, instead of leaving it as "Required and not
configured".
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

        panel.queue_manager.add_workflow.assert_not_called()

    def test_do_not_use_does_not_exclude_a_never_configured_indicator(self):
        """ "Do Not Use" is also the default for an indicator that was
        simply never configured yet (not one the user explicitly
        disabled) - running its parent factor/dimension used to zero its
        factor_weighting and mark it "Excluded from analysis" here,
        which getStatus() reads as permanently excluded rather than
        "Required and not configured" - the indicator stayed excluded
        even after the user went on to configure it (worldbank/GeoE3
        field report, 2026-11-24: running "Environmental Hazards" with
        its indicators merely unconfigured disabled all of them and the
        factor itself)."""
        item = MagicMock()
        attributes = {"analysis_mode": "Do Not Use", "factor_weighting": 1.0}
        item.attributes.return_value = attributes
        item.is_enabled.return_value = True
        item.attribute.return_value = "Fire_Hazards"

        panel = MagicMock()

        TreePanel.queue_workflow_task(panel, item, "indicator")

        self.assertEqual(attributes["factor_weighting"], 1.0)
        self.assertNotIn("result", attributes)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""TreePanel.on_analysis_report_completed(): AnalysisReportTask.run() is
now a deliberate no-op (the real report generation moved to finished(),
see that task's own docstring for why), so taskCompleted fires
unconditionally regardless of whether the real work succeeded - this
slot has to check the task's own "exception" attribute itself to tell
success from failure, rather than trusting which Qt signal fired.

TreePanel is a heavy QWidget that needs a loaded .ui file and a full
JsonTreeModel to construct, so this calls the unbound method against a
lightweight MagicMock stand-in instead of a real TreePanel, matching
the pattern in test_tree_panel_clear_item.py.
"""

import unittest
from unittest.mock import MagicMock

from geest.gui.panels.tree_panel import TreePanel


class _TaskWithNoExceptionAttribute:
    """A plain stand-in with no "exception" attribute at all."""


class TestOnAnalysisReportCompleted(unittest.TestCase):
    def setUp(self):
        self.panel = MagicMock()
        self.panel.analysis_report_task = MagicMock()
        self.panel.analysis_report_task.exception = None

    def test_no_exception_shows_success(self):
        TreePanel.on_analysis_report_completed(self.panel)

        self.panel.overall_progress_bar.setFormat.assert_called_with("Report generated successfully!")
        self.panel.item_info_panel.hide_progress.assert_called_once()
        self.panel.on_analysis_report_failed.assert_not_called()

    def test_an_exception_on_the_task_shows_failure_instead(self):
        self.panel.analysis_report_task.exception = RuntimeError("layout construction blew up")

        TreePanel.on_analysis_report_completed(self.panel)

        self.panel.on_analysis_report_failed.assert_called_once()
        self.panel.overall_progress_bar.setFormat.assert_not_called()

    def test_a_task_with_no_exception_attribute_at_all_is_treated_as_success(self):
        self.panel.analysis_report_task = _TaskWithNoExceptionAttribute()

        TreePanel.on_analysis_report_completed(self.panel)

        self.panel.overall_progress_bar.setFormat.assert_called_with("Report generated successfully!")
        self.panel.on_analysis_report_failed.assert_not_called()


if __name__ == "__main__":
    unittest.main()

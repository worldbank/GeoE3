# -*- coding: utf-8 -*-
"""Regression tests for the analysis/study-area report cache.

generate_analysis_report()/generate_study_area_report() used to
regenerate the PDF from scratch on every click, even when nothing in
the model had changed since the last time - and nothing ever
invalidated a stale PDF when an item was rerun, so adding a naive
cache would have silently served stale results forever.
_invalidate_analysis_report_cache() is called everywhere an item's
result changes (clear_item(), a config-changing aggregation dialog,
on_workflow_completed()) so the next "Show Analysis Report" click
rebuilds fresh instead of reusing a stale file.
"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from geest.gui.panels.tree_panel import TreePanel


class TestInvalidateAnalysisReportCache(unittest.TestCase):
    def setUp(self):
        self.working_dir = tempfile.mkdtemp(prefix="geoe3_report_cache_test_")
        self.panel = MagicMock()
        self.panel.working_directory = self.working_dir

    def tearDown(self):
        shutil.rmtree(self.working_dir, ignore_errors=True)

    def _touch(self, filename):
        path = os.path.join(self.working_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write("x")
        return path

    def test_deletes_both_the_pdf_and_the_qpt_if_present(self):
        pdf_path = self._touch("analysis_report.pdf")
        qpt_path = self._touch("analysis_report.qpt")

        TreePanel._invalidate_analysis_report_cache(self.panel)

        self.assertFalse(os.path.exists(pdf_path))
        self.assertFalse(os.path.exists(qpt_path))

    def test_is_a_no_op_when_neither_file_exists(self):
        TreePanel._invalidate_analysis_report_cache(self.panel)  # must not raise

    def test_is_a_no_op_when_there_is_no_working_directory(self):
        self.panel.working_directory = None
        self._touch("analysis_report.pdf")  # lives in a dir self.panel doesn't know about

        TreePanel._invalidate_analysis_report_cache(self.panel)  # must not raise


class TestGenerateAnalysisReportReusesCache(unittest.TestCase):
    def setUp(self):
        self.working_dir = tempfile.mkdtemp(prefix="geoe3_report_cache_test_")
        self.panel = MagicMock()
        self.panel.working_directory = self.working_dir

    def tearDown(self):
        shutil.rmtree(self.working_dir, ignore_errors=True)

    def test_opens_the_existing_pdf_instead_of_regenerating_it(self):
        pdf_path = os.path.join(self.working_dir, "analysis_report.pdf")
        with open(pdf_path, "w", encoding="utf-8") as f:
            f.write("x")

        with (
            patch("geest.gui.panels.tree_panel.open_with_system_handler") as mock_open,
            patch("geest.gui.panels.tree_panel.AnalysisReportTask") as mock_task,
        ):
            TreePanel.generate_analysis_report(self.panel)

        mock_open.assert_called_once_with(pdf_path)
        mock_task.assert_not_called()

    def test_regenerates_when_nothing_is_cached_yet(self):
        with (
            patch("geest.gui.panels.tree_panel.open_with_system_handler") as mock_open,
            patch("geest.gui.panels.tree_panel.AnalysisReportTask") as mock_task,
            patch("qgis.core.QgsApplication.taskManager"),
        ):
            TreePanel.generate_analysis_report(self.panel)

        mock_open.assert_not_called()
        mock_task.assert_called_once()


class TestGenerateStudyAreaReportReusesCache(unittest.TestCase):
    def setUp(self):
        self.working_dir = tempfile.mkdtemp(prefix="geoe3_report_cache_test_")
        self.panel = MagicMock()
        self.panel.working_directory = self.working_dir

    def tearDown(self):
        shutil.rmtree(self.working_dir, ignore_errors=True)

    def test_opens_the_existing_pdf_instead_of_regenerating_it(self):
        pdf_path = os.path.join(self.working_dir, "study_area_report.pdf")
        with open(pdf_path, "w", encoding="utf-8") as f:
            f.write("x")

        with (
            patch("geest.gui.panels.tree_panel.open_with_system_handler") as mock_open,
            patch("geest.gui.panels.tree_panel.StudyAreaReport") as mock_report,
        ):
            TreePanel.generate_study_area_report(self.panel)

        mock_open.assert_called_once_with(pdf_path)
        mock_report.assert_not_called()


if __name__ == "__main__":
    unittest.main()

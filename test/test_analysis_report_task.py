# -*- coding: utf-8 -*-
"""AnalysisReportTask: run() is a deliberate no-op, the real report
generation happens in finished() instead - the only point in the
task's lifecycle QgsTask guarantees runs on the main thread. See the
task's own docstring for the worker-thread QgsLayoutItem crash this
avoids.
"""

import unittest
from unittest.mock import MagicMock, patch

from geest.core.tasks.analysis_report_task import AnalysisReportTask


class TestAnalysisReportTaskRun(unittest.TestCase):
    def test_run_is_a_no_op_that_always_succeeds(self):
        task = AnalysisReportTask("/some/working/dir", "/some/model.json")
        with patch("geest.core.tasks.analysis_report_task.AnalysisReport") as mock_report_cls:
            self.assertTrue(task.run())
            mock_report_cls.assert_not_called()


class TestAnalysisReportTaskFinished(unittest.TestCase):
    def setUp(self):
        self.task = AnalysisReportTask("/some/working/dir", "/some/model.json")

    def _mock_report(self, mock_report_cls):
        mock_report = MagicMock()
        mock_report_cls.return_value.__enter__.return_value = mock_report
        return mock_report

    def test_cancelled_before_running_does_nothing(self):
        with patch("geest.core.tasks.analysis_report_task.AnalysisReport") as mock_report_cls:
            self.task.finished(False)
            mock_report_cls.assert_not_called()
        self.assertIsNone(self.task.exception)

    def test_successful_run_builds_and_exports_the_report_then_opens_it(self):
        with (
            patch("geest.core.tasks.analysis_report_task.AnalysisReport") as mock_report_cls,
            patch("geest.core.tasks.analysis_report_task.open_with_system_handler") as mock_open,
        ):
            mock_report = self._mock_report(mock_report_cls)

            self.task.finished(True)

            mock_report_cls.assert_called_once_with(
                model_path="/some/model.json",
                working_directory="/some/working/dir",
                report_name="GeoE3 Analysis Report",
            )
            mock_report.create_layout.assert_called_once()
            mock_report.export_pdf.assert_called_once_with(self.task.pdf_path)
            mock_report.export_qpt.assert_called_once_with(self.task.qpt_path)
            mock_open.assert_called_once_with(self.task.pdf_path)
            self.assertIsNone(self.task.exception)

    def test_an_exception_inside_finished_is_caught_not_propagated(self):
        # An exception escaping a Qt slot aborts the application outright
        # on PyQt6 (qFatal) - this must never happen, regardless of what
        # AnalysisReport itself raises.
        with patch("geest.core.tasks.analysis_report_task.AnalysisReport") as mock_report_cls:
            mock_report_cls.side_effect = RuntimeError("layout construction blew up")

            self.task.finished(True)  # must not raise

        self.assertIsInstance(self.task.exception, RuntimeError)
        self.assertEqual(str(self.task.exception), "layout construction blew up")

    def test_a_failure_does_not_open_the_pdf(self):
        with (
            patch("geest.core.tasks.analysis_report_task.AnalysisReport") as mock_report_cls,
            patch("geest.core.tasks.analysis_report_task.open_with_system_handler") as mock_open,
        ):
            mock_report = self._mock_report(mock_report_cls)
            mock_report.create_layout.side_effect = RuntimeError("boom")

            self.task.finished(True)

            mock_open.assert_not_called()
        self.assertIsNotNone(self.task.exception)


if __name__ == "__main__":
    unittest.main()

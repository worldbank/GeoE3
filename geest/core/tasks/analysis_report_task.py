# -*- coding: utf-8 -*-
"""Analysis Report Generation Task.

This module contains the QgsTask for generating analysis reports.
"""

import os

from qgis.core import Qgis, QgsTask

from geest.core.reports.analysis_report import AnalysisReport
from geest.utilities import log_message, open_with_system_handler


class AnalysisReportTask(QgsTask):
    """Background task for analysis report generation.

    run() is deliberately a no-op - see finished()'s docstring for why
    the real work moved there.
    """

    def __init__(self, working_dir: str, model_path: str):
        """Initialize the task.

        Args:
            working_dir: Working directory where report will be saved.
            model_path: Path to the model JSON file.
        """
        super().__init__("Generating Analysis Report", QgsTask.CanCancel)
        self.working_dir = working_dir
        self.model_path = model_path
        self.pdf_path = os.path.join(working_dir, "analysis_report.pdf")
        self.qpt_path = os.path.join(working_dir, "analysis_report.qpt")
        self.exception = None

    def run(self) -> bool:
        """Does nothing - the real work happens in finished() instead.

        QgsTask.run() always executes on a worker thread, and none of
        AnalysisReport's layout construction is safe there (see
        finished()'s docstring). Always returns True so finished()
        gets a chance to run, except when QGIS itself cancels the task
        before run() ever starts (QgsTask.CanCancel) - that still
        calls finished(False), handled there.

        Returns:
            bool: Always True.
        """
        return True

    def finished(self, result: bool) -> None:
        """Build and export the report here, on the main thread.

        QgsLayout/QgsLayoutItem* (QgsLayoutItemLabel, etc.) are not
        safe to construct off the main thread - confirmed live: doing
        so from run() (always a worker thread, by QgsTask's design)
        raised a Windows access violation - a fatal crash, not a
        catchable Python exception - while AnalysisReport built its
        detail pages. finished() is the first point in this task's
        lifecycle guaranteed to run on the main thread, so the real
        work moved here; run() above is a deliberate no-op. This
        sacrifices genuine background execution (the UI blocks for the
        duration of report generation, same as not using a QgsTask at
        all) - the alternative (a worker-thread crash) is worse.

        An exception escaping a Qt slot aborts the application outright
        on PyQt6 (qFatal), so this is wrapped in its own try/except
        rather than letting one propagate - geoe3_dock.py's
        _open_road_network_from_ors() hit the exact same hazard.
        Since run() always returns True, QgsTask's own taskCompleted
        signal fires regardless of whether the work below actually
        succeeded - callers must check self.exception themselves
        (see TreePanel.on_analysis_report_completed()).

        Args:
            result: True unless QGIS cancelled the task before run()
                started - run() itself never returns False.
        """
        if not result:
            log_message("Analysis report generation cancelled before it started.", tag="GeoE3", level=Qgis.Warning)
            return

        try:
            log_message("Starting analysis report generation...", tag="GeoE3", level=Qgis.Info)

            # Context manager guarantees cleanup: the report registers its
            # result rasters in the project registry (legend-less) while
            # rendering, and without cleanup every generation leaked ~20
            # orphaned layers into the session.
            with AnalysisReport(
                model_path=self.model_path,
                working_directory=self.working_dir,
                report_name="GeoE3 Analysis Report",
            ) as report:
                report.create_layout()
                report.export_pdf(self.pdf_path)
                report.export_qpt(self.qpt_path)

            log_message(
                f"Analysis report generated successfully: {self.pdf_path}",
                tag="GeoE3",
                level=Qgis.Info,
            )
            # Open the PDF using the system PDF viewer (detached - already
            # on the main thread here, so no extra marshalling needed).
            open_with_system_handler(self.pdf_path)

        except Exception as e:
            self.exception = e
            log_message(f"Error generating analysis report: {e}", tag="GeoE3", level=Qgis.Critical)

    def cancel(self) -> None:
        """Called when task is cancelled."""
        log_message("Analysis report generation cancelled.", tag="GeoE3", level=Qgis.Warning)
        super().cancel()

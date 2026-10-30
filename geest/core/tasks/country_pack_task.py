# -*- coding: utf-8 -*-
"""Country Pack Generation Task.

This module contains the QgsTask for bundling a project's configured
input data into a single GeoPackage in the background.
"""

import json
import os
from typing import Dict, Optional

from qgis.core import Qgis, QgsTask

from geest.core.country_pack import build_country_pack
from geest.utilities import log_message, open_with_system_handler


class CountryPackTask(QgsTask):
    """Background task for building a country pack GeoPackage."""

    def __init__(
        self,
        working_dir: str,
        model_path: str,
        output_path: str,
        style_xml_by_path: Optional[Dict[str, str]] = None,
    ):
        """Initialize the task.

        Args:
            working_dir: Project working directory (where study_area/
                study_area.gpkg lives).
            model_path: Path to the project's model.json.
            output_path: Path the pack GeoPackage should be written to.
            style_xml_by_path: Source path -> style XML for sources whose
                style should be embedded, resolved on the main thread
                before this task starts (see country_pack.py).
        """
        super().__init__("Building Country Pack", QgsTask.CanCancel)
        self.working_dir = working_dir
        self.model_path = model_path
        self.output_path = output_path
        self.style_xml_by_path = style_xml_by_path or {}
        self.exception = None
        self.summary: Dict[str, list] = {"written": [], "skipped": []}

    def run(self) -> bool:
        """Build the pack in the background thread.

        Returns:
            True if the pack was built (even if some sources were
            skipped - see self.summary["skipped"]), False on a hard
            failure (e.g. model.json unreadable).
        """
        try:
            log_message("Starting country pack generation...", tag="GeoE3", level=Qgis.Info)

            with open(self.model_path, "r", encoding="utf-8") as f:
                model = json.load(f)

            def _report_progress(done: int, total: int, layer_name: str) -> None:
                if total:
                    self.setProgress(int(100 * done / total))
                if layer_name:
                    log_message(f"Country pack: writing '{layer_name}'...", tag="GeoE3")

            self.summary = build_country_pack(
                working_directory=self.working_dir,
                model=model,
                output_path=self.output_path,
                style_xml_by_path=self.style_xml_by_path,
                progress_callback=_report_progress,
            )

            log_message(
                f"Country pack generated: {len(self.summary['written'])} layers written, "
                f"{len(self.summary['skipped'])} skipped -> {self.output_path}",
                tag="GeoE3",
                level=Qgis.Info,
            )
            return True

        except Exception as e:
            self.exception = e
            log_message(f"Error generating country pack: {e}", tag="GeoE3", level=Qgis.Critical)
            return False

    def finished(self, result: bool) -> None:
        """Called when the task finishes (main thread).

        Args:
            result: True if the task succeeded, False otherwise.
        """
        if result:
            log_message(
                f"Country pack ready: {self.output_path} "
                f"({len(self.summary['written'])} layers, {len(self.summary['skipped'])} skipped)",
                tag="GeoE3",
                level=Qgis.Info,
            )
            if os.path.exists(self.output_path):
                open_with_system_handler(os.path.dirname(self.output_path))
        else:
            log_message("Country pack generation failed.", tag="GeoE3", level=Qgis.Critical)

    def cancel(self) -> None:
        """Called when the task is cancelled."""
        log_message("Country pack generation cancelled.", tag="GeoE3", level=Qgis.Warning)
        super().cancel()

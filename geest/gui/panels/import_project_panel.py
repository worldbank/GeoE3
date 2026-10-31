# -*- coding: utf-8 -*-
"""📦 Import Project Panel module.

This module contains functionality for the import country pack panel.
"""

import os

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import QFileDialog, QWidget

from geest.core.tasks import ImportCountryPackTask
from geest.gui.panels.blank_project_guard import ensure_blank_qgis_project
from geest.gui.widgets import CustomBannerLabel
from geest.utilities import (
    get_ui_class,
    linear_interpolation,
    log_message,
    resources_path,
)

FORM_CLASS = get_ui_class("import_project_panel_base.ui")


class ImportProjectPanel(FORM_CLASS, QWidget):
    """🎯 Import Project Panel.

    Attributes:
        pack_path: Path to the chosen country pack GeoPackage.
        working_dir: Empty working directory to import into.
    """

    switch_to_next_tab = pyqtSignal()  # Signal to notify the parent to switch tabs
    switch_to_previous_tab = pyqtSignal()  # Signal to notify the parent to switch tabs
    set_working_directory = pyqtSignal(str)  # Signal to set the working directory
    project_loaded = pyqtSignal(str)  # Signal emitted after the project is fully imported

    def __init__(self):
        """🏗️ Initialize the instance."""
        super().__init__()
        self.setWindowTitle("GeoE3")
        self.pack_path = ""
        self.working_dir = ""
        self.import_task = None
        # Dynamically load the .ui file
        self.setupUi(self)
        log_message("Loading import project panel")
        self.initUI()

    def initUI(self):
        """⚙️ Initui."""
        self.custom_label = CustomBannerLabel(
            "The Geospatial Enabling Environments for Employment Spatial Tool",
            resources_path("resources", "geoe3-banner.png"),
        )
        parent_layout = self.banner_label.parent().layout()
        parent_layout.replaceWidget(self.banner_label, self.custom_label)
        self.banner_label.deleteLater()
        parent_layout.update()
        self.label_2.setText("GeoE3 Import Country Pack")

        self.pack_file_button.clicked.connect(self.select_pack_file)
        self.dir_button.clicked.connect(self.select_directory)
        self.previous_button.clicked.connect(self.on_previous_button_clicked)
        self.import_project_button.clicked.connect(self.import_project)
        self.set_font_size()

    def on_previous_button_clicked(self):
        """⚙️ On previous button clicked."""
        self.switch_to_previous_tab.emit()

    def select_pack_file(self):
        """⚙️ Browse for a country pack GeoPackage."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Country Pack GeoPackage", self.pack_path, "GeoPackage (*.gpkg)"
        )
        if path:
            self.pack_path = path
            self.pack_path_edit.setText(path)
            self.status_label.setText("")

    def select_directory(self):
        """⚙️ Browse for an empty working directory to import into."""
        directory = QFileDialog.getExistingDirectory(self, "Select Empty Working Directory", self.working_dir)
        if directory:
            self.working_dir = directory
            self.working_dir_edit.setText(directory)
            self.status_label.setText("")

    def import_project(self):
        """⚙️ Validate the chosen pack/directory and start the import task."""
        # Defensive backstop - SetupPanel's own button already prompts
        # to save and start fresh before switching to this panel, but
        # re-check here too in case the QGIS project changed in between.
        if not ensure_blank_qgis_project(self):
            return
        if not self.pack_path or not os.path.exists(self.pack_path):
            self.status_label.setText("Choose a country pack GeoPackage first.")
            return
        if not self.working_dir:
            self.status_label.setText("Choose a working directory first.")
            return
        if os.path.exists(os.path.join(self.working_dir, "model.json")):
            self.status_label.setText("That directory already has a GeoE3 project - choose an empty one.")
            return

        self.status_label.setText("Importing...")
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.disable_widgets()

        self.import_task = ImportCountryPackTask(self.pack_path, self.working_dir)
        # QgsTask.progressChanged emits a float; QProgressBar.setValue
        # wants an int - PyQt6/QGIS 4 enforces this strictly where
        # PyQt5/QGIS 3 silently coerced it.
        self.import_task.progressChanged.connect(lambda value: self.progress_bar.setValue(int(value)))
        self.import_task.taskCompleted.connect(self.on_import_completed)
        self.import_task.taskTerminated.connect(self.on_import_failed)
        QgsApplication.taskManager().addTask(self.import_task)

    def on_import_completed(self):
        """⚙️ Handle successful import - route into the Tree panel like Open Project does."""
        self.enable_widgets()
        self.progress_bar.setVisible(False)
        summary = self.import_task.summary
        self.status_label.setText(f"Imported {len(summary['imported'])} tables, {len(summary['skipped'])} skipped.")
        self.set_working_directory.emit(self.working_dir)
        self.project_loaded.emit(self.working_dir)
        self.switch_to_next_tab.emit()

    def on_import_failed(self):
        """⚙️ Handle a failed import."""
        self.enable_widgets()
        self.progress_bar.setVisible(False)
        reason = str(self.import_task.exception) if self.import_task and self.import_task.exception else "Unknown error"
        self.status_label.setText(f"Import failed: {reason}")
        log_message(f"Country pack import failed: {reason}", tag="GeoE3")

    def disable_widgets(self):
        """⚙️ Disable all child widgets while the import task runs."""
        for widget in self.findChildren(QWidget):
            widget.setEnabled(False)

    def enable_widgets(self):
        """⚙️ Re-enable all child widgets once the import task finishes."""
        for widget in self.findChildren(QWidget):
            widget.setEnabled(True)

    def resizeEvent(self, event):
        """⚙️ Resizeevent.

        Args:
            event: Event.
        """
        self.set_font_size()
        super().resizeEvent(event)

    def set_font_size(self):
        """⚙️ Set font size."""
        panel_width = self.label.rect().width()
        title_size = int(linear_interpolation(panel_width, 14, 18, 400, 800))
        content_size = int(linear_interpolation(panel_width, 12, 16, 400, 800))
        control_size = int(linear_interpolation(panel_width, 12, 16, 400, 800))

        title_font = QFont("Arial", title_size)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.label_2.setFont(title_font)
        self.label.setFont(QFont("Arial", content_size))
        self.pack_path_edit.setFont(QFont("Arial", control_size))
        self.working_dir_edit.setFont(QFont("Arial", control_size))

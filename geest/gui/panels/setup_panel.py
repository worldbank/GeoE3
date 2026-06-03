# -*- coding: utf-8 -*-
"""📦 Setup Panel module.

This module contains functionality for setup panel.
"""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import QWidget

from geest.gui.widgets import CustomBannerLabel
from geest.utilities import (
    get_ui_class,
    linear_interpolation,
    log_message,
    resources_path,
)

FORM_CLASS = get_ui_class("setup_panel_base.ui")


class SetupPanel(FORM_CLASS, QWidget):
    """🎯 Setup Panel."""

    switch_to_load_project_tab = pyqtSignal()  # Signal to notify the parent to switch tabs
    switch_to_create_project_tab = pyqtSignal()  # Signal to notify the parent to switch tabs
    switch_to_previous_tab = pyqtSignal()  # Signal to notify the parent to switch tabs

    def __init__(self):
        """🏗️ Initialize the instance."""
        super().__init__()
        self.setWindowTitle("GeoE3")
        # Dynamically load the .ui file
        self.setupUi(self)
        log_message("Loading setup panel")
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
        self.label_2.setText("GeoE3 Project Selection")

        self.open_existing_project_button.clicked.connect(self.load_project)
        self.create_new_project_button.clicked.connect(self.create_project)
        self.previous_button.clicked.connect(self.on_previous_button_clicked)

    def load_project(self):
        """⚙️ Load project."""
        self.switch_to_load_project_tab.emit()

    def create_project(self):
        """⚙️ Create project."""
        self.switch_to_create_project_tab.emit()

    def on_previous_button_clicked(self):
        """⚙️ On previous button clicked."""
        self.switch_to_previous_tab.emit()

    def resizeEvent(self, event):
        """⚙️ Resizeevent.

        Args:
            event: Event.
        """
        self.set_font_size()
        super().resizeEvent(event)

    def set_font_size(self):
        """⚙️ Set font size."""
        panel_width = self.description.rect().width()
        title_size = int(linear_interpolation(panel_width, 16, 20, 400, 800))
        content_size = int(linear_interpolation(panel_width, 11, 15, 400, 800))
        control_size = int(linear_interpolation(panel_width, 12, 16, 400, 800))

        title_font = QFont("Arial", title_size)
        title_font.setWeight(QFont.DemiBold)
        self.label_2.setFont(title_font)
        self.description.setFont(QFont("Arial", content_size))
        self.open_existing_project_button.setFont(QFont("Arial", control_size))
        self.create_new_project_button.setFont(QFont("Arial", control_size))

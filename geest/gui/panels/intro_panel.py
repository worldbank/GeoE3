# -*- coding: utf-8 -*-
"""📦 Intro Panel module.

This module contains functionality for intro panel.
"""

from qgis.core import Qgis  # noqa F401
from qgis.PyQt.QtWidgets import QWidget
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QFont

from geest.gui.widgets import CustomBannerLabel
from geest.utilities import (
    get_ui_class,
    linear_interpolation,
    log_message,
    resources_path,
)

FORM_CLASS = get_ui_class("intro_panel_base.ui")


class IntroPanel(FORM_CLASS, QWidget):
    """🎯 Intro Panel."""

    switch_to_next_tab = pyqtSignal()  # Signal to notify the parent to switch tabs

    def __init__(self):
        """🏗️ Initialize the instance."""
        super().__init__()
        self.setWindowTitle("GeoE3")
        # Dynamically load the .ui file
        self.setupUi(self)
        log_message("Loading intro panel")
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
        self.label_2.setText("Welcome to GeoE3")
        self.next_button.clicked.connect(self.on_next_button_clicked)
        self.set_font_size()

    def on_next_button_clicked(self):
        """⚙️ On next button clicked."""
        self.switch_to_next_tab.emit()

    def resizeEvent(self, event):
        """⚙️ Resizeevent.

        Args:
            event: Event.
        """
        self.set_font_size()
        super().resizeEvent(event)

    def set_font_size(self):
        """⚙️ Set font size."""
        panel_width = self.intro_label.rect().width()
        title_size = int(linear_interpolation(panel_width, 16, 20, 400, 800))
        content_size = int(linear_interpolation(panel_width, 11, 15, 400, 800))

        title_font = QFont("Arial", title_size)
        title_font.setWeight(QFont.DemiBold)
        self.label_2.setFont(title_font)
        self.intro_label.setFont(QFont("Arial", content_size))

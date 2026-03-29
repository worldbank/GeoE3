# -*- coding: utf-8 -*-
"""📦 Help Panel module.

This module contains functionality for help panel.
"""

from qgis.PyQt.QtCore import Qt, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView

    web_engine_available = True
except ImportError:
    web_engine_available = False


class HelpPanel(QWidget):
    """🎯 Help Panel.

    Attributes:
        label: Label.
        layout: Layout.
        web_view: Web view.
    """

    switch_to_previous_tab = pyqtSignal()

    def __init__(self):
        """🏗️ Initialize the instance."""
        super().__init__()

        # Set up the layout
        self.layout = QVBoxLayout(self)

        if web_engine_available:
            # If QWebEngineView is available, create it and load the URL
            self.web_view = QWebEngineView()
            self.web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.web_view.setUrl(QUrl("https://worldbank.github.io/GEOE3/README.html"))
            self.layout.addWidget(self.web_view)
        else:
            # Center the content both vertically and horizontally when QWebEngineView is unavailable

            # Add vertical spacers for vertical centering
            self.layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

            # Create label and button
            self.label = QLabel("WebEngine not available. Click below to open the help in your browser.")
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center the label horizontally
            self.layout.addWidget(self.label)

            open_browser_button = QPushButton("Open in Browser")
            open_browser_button.clicked.connect(self.open_in_browser)
            open_browser_button.setFixedSize(150, 40)  # Set fixed size for the button
            self.layout.addWidget(
                open_browser_button, alignment=Qt.AlignmentFlag.AlignCenter
            )  # Center button horizontally

            # Add vertical spacers for vertical centering
            self.layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Add back button (horizontally centered in both cases)
        back_button = QPushButton("Back")
        back_button.clicked.connect(self.switch_to_previous_tab)
        self.layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # Set the layout for the widget
        self.setLayout(self.layout)

    def open_in_browser(self):
        """⚙️ Open in browser."""
        # Open the URL in the default web browser
        QDesktopServices.openUrl(QUrl("https://worldbank.github.io/GEOE3/README.html"))

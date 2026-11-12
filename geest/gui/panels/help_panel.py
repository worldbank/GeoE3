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

#: GeoE3's published documentation site (mkdocs, GitHub Pages).
HELP_URL = "https://worldbank.github.io/GeoE3/"


class HelpPanel(QWidget):
    """🎯 Help Panel - opens the published docs in the user's browser.

    No longer tries to embed the docs in-app: the QtWebEngine attempt
    this used to make only ever imported from PyQt5.QtWebEngineWidgets,
    which can't succeed under this project's PyQt6/Qt6 stack, so every
    real run already fell through to this same open-in-browser button
    regardless.

    Attributes:
        label: Label.
        layout: Layout.
    """

    switch_to_previous_tab = pyqtSignal()

    def __init__(self):
        """🏗️ Initialize the instance."""
        super().__init__()

        # Set up the layout
        self.layout = QVBoxLayout(self)

        # Add vertical spacers for vertical centering
        self.layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Create label and button
        self.label = QLabel("Click below to open the GeoE3 documentation in your browser.")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center the label horizontally
        self.layout.addWidget(self.label)

        open_browser_button = QPushButton("Open in Browser")
        open_browser_button.clicked.connect(self.open_in_browser)
        open_browser_button.setFixedSize(150, 40)  # Set fixed size for the button
        self.layout.addWidget(open_browser_button, alignment=Qt.AlignmentFlag.AlignCenter)  # Center button horizontally

        # Add vertical spacers for vertical centering
        self.layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Add back button (horizontally centered)
        back_button = QPushButton("Back")
        back_button.clicked.connect(self.switch_to_previous_tab)
        self.layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignCenter)

        # Set the layout for the widget
        self.setLayout(self.layout)

    def open_in_browser(self):
        """⚙️ Open the published GeoE3 documentation in the default browser."""
        QDesktopServices.openUrl(QUrl(HELP_URL))

# -*- coding: utf-8 -*-
"""📦 Raster Datasource Widget module.

This module contains functionality for raster datasource widget.
"""

import os
from urllib.parse import quote, unquote

from qgis.core import Qgis, QgsMapLayerProxyModel, QgsProject
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtGui import QFontMetrics, QIcon
from qgis.PyQt.QtWidgets import QFileDialog, QLabel, QLineEdit, QSizePolicy, QStyle, QToolButton

from geest.utilities import log_message, resources_path

from .base_datasource_widget import BaseDataSourceWidget


class RasterDataSourceWidget(BaseDataSourceWidget):
    """

    A widget for selecting a raster (area) layer with options for inputs.

    This widget provides one `QgsMapLayerComboBox` components for selecting raster layers,
    as well as `QLineEdit` and `QToolButton` components to allow the user to specify paths for
    each layer. The user can choose layers either from the QGIS project or provide externals.

    Attributes:
        widget_key (str): The key identifier for this widget.
        raster_layer_combo (QgsMapLayerComboBox): A combo box for selecting the raster layer.
        raster_line_edit (QLineEdit): Line edit for entering/selecting a raster layer.
    """

    def add_internal_widgets(self) -> None:
        """
        Adds the internal widgets required for selecting raster layers and their correspondings.
        This method is called during the widget initialization and sets up the layout for the UI components.
        """
        try:
            self.settings = QSettings()

            # Raster Layer Section
            self._add_raster_layer_widgets()
            # Connect signals to update the data when user changes selections
            self.raster_layer_combo.currentIndexChanged.connect(self.update_attributes)
            self.raster_line_edit.textChanged.connect(self.update_attributes)

        except Exception as e:
            log_message(f"Error in add_internal_widgets: {e}", level=Qgis.Critical)
            import traceback

            log_message(traceback.format_exc(), level=Qgis.Critical)

    def _add_raster_layer_widgets(self) -> None:
        """
        Adds the widgets for selecting the raster layer, including a `QgsMapLayerComboBox` and input.
        """
        # Raster Layer ComboBox (Filtered to raster layers)
        self.raster_layer_combo = QgsMapLayerComboBox()
        self.raster_layer_combo.setFilters(QgsMapLayerProxyModel.Filter.RasterLayer)
        self.raster_layer_combo.setAllowEmptyLayer(True)
        self.raster_layer_combo.setMaximumWidth(420)
        # Insert placeholder text at the top (only visually, not as a selectable item)
        self.raster_layer_combo.setCurrentIndex(-1)  # Ensure no selection initially
        self.raster_layer_combo.setEditable(True)  # Make editable temporarily for placeholder
        self.raster_layer_combo.lineEdit().setPlaceholderText("Select item")  # Add placeholder text

        # Disable editing after setting placeholder (ensures only layer names are selectable)
        self.raster_layer_combo.lineEdit().setReadOnly(True)
        self.raster_layer_combo.setEditable(False)  # Lock back to non-editable after setting placeholder

        self.raster_layer_combo.setToolTip("Raster chosen from file system will have preference")
        self.layout.addWidget(self.raster_layer_combo)

        # Restore previously selected raster layer
        raster_layer_id = self.attributes.get(f"{self.widget_key}_layer_id", None)
        if raster_layer_id:
            raster_layer = QgsProject.instance().mapLayer(raster_layer_id)
            if raster_layer:
                self.raster_layer_combo.setLayer(raster_layer)

        # Input for Raster Layer
        self.raster_line_edit = QLineEdit()
        self.raster_line_edit.setVisible(False)  # Hide initially

        # Add clear button inside the line edit
        self.clear_button = QToolButton(self.raster_line_edit)
        clear_icon = QIcon(resources_path("resources", "icons", "clear.svg"))
        self.clear_button.setIcon(clear_icon)
        self.clear_button.setToolTip("Clear")
        self.clear_button.setCursor(Qt.CursorShape.ArrowCursor)
        self.clear_button.setStyleSheet("border: 0px; padding: 0px;")
        self.clear_button.clicked.connect(self.clear_raster)
        self.clear_button.setVisible(False)

        self.raster_line_edit.textChanged.connect(lambda text: self.clear_button.setVisible(bool(text)))
        self.raster_line_edit.textChanged.connect(self.resize_clear_button)

        # File chooser button for Raster Layer
        self.raster_button = QToolButton()
        self.raster_button.setText("...")
        self.raster_button.clicked.connect(self.select_raster)

        if self.attributes.get(f"{self.widget_key}_raster", False):
            self.raster_line_edit.setText(unquote(self.attributes[f"{self.widget_key}_raster"]))
            self.raster_line_edit.setVisible(True)
            self.raster_layer_combo.setVisible(False)
        else:
            self.raster_layer_combo.setVisible(True)
        self.layout.addWidget(self.raster_line_edit)
        self.resize_clear_button()

        self.layout.addWidget(self.raster_button)
        self.raster_button.setToolTip("Raster chosen from file system will have preference")

    def _add_source_link(self, url: str, label: str) -> None:
        """Add a clickable hyperlink that opens the source dataset in a browser.

        The link is laid out with a ``Preferred`` horizontal size policy and a
        minimum width, so it reserves its text width and sits immediately after
        the other controls without creating a large empty gap or widening the
        table rows.

        Args:
            url: The URL to open when the link is clicked.
            label: The link text shown to the user.
        """
        if not url:
            return
        self._source_link_url = url
        self._source_link_text = label
        self._source_link_label = QLabel(f'<a href="{url}">{label}</a>')
        self._source_link_label.setOpenExternalLinks(True)
        self._source_link_label.setWordWrap(False)
        self._source_link_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._source_link_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._source_link_label.setMinimumWidth(160)
        self._source_link_label.setStyleSheet("color: #2d5a75; font-size: 11px; padding: 0px;")
        self._source_link_label.setToolTip(
            f"Download {label} from the World Bank Data Catalog"
            if label
            else "Download source data from the World Bank Data Catalog"
        )
        self.layout.addWidget(self._source_link_label)

    def _elide_source_link(self) -> None:
        """Render the source link text ellipsized to fit the available width."""
        if not getattr(self, "_source_link_label", None):
            return
        width = max(20, self._source_link_label.width() - 4)
        elided = QFontMetrics(self._source_link_label.font()).elidedText(
            self._source_link_text,
            Qt.TextElideMode.ElideRight,
            width,
        )
        self._source_link_label.setText(f'<a href="{self._source_link_url}">{elided}</a>')

    def resizeEvent(self, event):
        """
        Handle resize events for the parent container.

        Args:
            event: The resize event.
        """
        super().resizeEvent(event)
        self.resize_clear_button()
        self._elide_source_link()

    def resize_clear_button(self):
        """Reposition the clear button when the line edit is resized."""
        log_message("Resizing clear button")
        # Position the clear button inside the line edit
        frame_width = self.raster_line_edit.style().pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth)
        self.raster_line_edit.setStyleSheet(
            f"QLineEdit {{ padding-right: {self.clear_button.sizeHint().width() + frame_width}px; }}"  # noqa E702,E202,E201
        )
        sz = self.clear_button.sizeHint()
        self.clear_button.move(self.raster_line_edit.width() - sz.width() - frame_width - 5, 6)

    def select_raster(self) -> None:
        """
        Opens a file dialog to select a for the raster (paths) layer and updates the QLineEdit with the file path.
        """
        try:
            last_dir = self.settings.value("GeoE3/lastRasterDir", "")

            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Raster Layer", last_dir, "Rasters (*.vrt *.tif *.asc)"
            )
            if file_path:
                # Update the line edit with the selected file path
                # ⚠️ Be careful about changing the order of the following lines
                #   It could cause the clear button to render in the incorrect place
                self.raster_layer_combo.setVisible(False)
                self.raster_line_edit.setVisible(True)
                self.raster_line_edit.setText(file_path)
                # Trigger resize event explicitly
                self.resizeEvent(None)
                # Save the directory of the selected file to QSettings
                self.settings.setValue("GeoE3/lastRasterDir", os.path.dirname(file_path))

        except Exception as e:
            log_message(f"Error selecting raster: {e}", level=Qgis.Critical)

    def clear_raster(self):
        """
        Clears the raster line edit and hides it along with the clear button.
        """
        self.raster_line_edit.clear()
        self.raster_line_edit.setVisible(False)
        self.raster_layer_combo.setVisible(True)
        self.raster_layer_combo.setFocus()
        self.update_attributes()

    def update_attributes(self):
        """
        Updates the attributes dict to match the current state of the widget.

        The attributes dict is a reference so any tree item attributes will be updated directly.

        Returns:
            None
        """

        # Collect data for the raster layer
        raster_layer = self.raster_layer_combo.currentLayer()
        if not raster_layer:
            # Clear every key the layer combo ever wrote, not just the
            # (unused) "_layer" one - see vector_datasource_widget.py's
            # matching fix for why (worldbank/GeoE3 field report,
            # 2026-11-25).
            self.attributes[f"{self.widget_key}_layer"] = None
            self.attributes[f"{self.widget_key}_layer_name"] = ""
            self.attributes[f"{self.widget_key}_layer_source"] = ""
            self.attributes[f"{self.widget_key}_layer_provider_type"] = ""
            self.attributes[f"{self.widget_key}_layer_crs"] = ""
            self.attributes[f"{self.widget_key}_layer_id"] = ""
        if raster_layer:
            self.attributes[f"{self.widget_key}_layer_name"] = raster_layer.name()
            self.attributes[f"{self.widget_key}_layer_source"] = raster_layer.source()
            self.attributes[f"{self.widget_key}_layer_provider_type"] = raster_layer.providerType()
            self.attributes[f"{self.widget_key}_layer_crs"] = raster_layer.crs().authid()
            self.attributes[f"{self.widget_key}_layer_id"] = raster_layer.id()
        self.attributes[f"{self.widget_key}_raster"] = quote(self.raster_line_edit.text())

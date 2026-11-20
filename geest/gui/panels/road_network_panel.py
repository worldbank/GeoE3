# -*- coding: utf-8 -*-
"""📦 Road Network Panel module.

This module contains functionality for road network panel.
"""

import json
import os
import traceback

from qgis import processing
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeedback,
    QgsMapLayerProxyModel,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QSettings, Qt, QUrl, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QDesktopServices, QFont, QPixmap
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

from geest.core import WorkflowQueueManager
from geest.core.osm_downloaders.osm_download_type import OSMDownloadType
from geest.core.tasks import OSMDownloaderTask
from geest.gui.widgets import CustomBannerLabel
from geest.utilities import (
    get_ui_class,
    linear_interpolation,
    log_message,
    resources_path,
)

FORM_CLASS = get_ui_class("road_network_panel_base.ui")


class RoadNetworkPanel(FORM_CLASS, QWidget):
    """🎯 Road Network Panel.

    Attributes:
        queue_manager: Queue manager.
        settings: Settings.
        working_directory: Working directory.
    """

    switch_to_next_tab = pyqtSignal()  # Signal to notify the parent to switch tabs
    switch_to_previous_tab = pyqtSignal()  # Signal to notify the parent to switch tabs

    road_network_layer_path_changed = pyqtSignal(str)

    def __init__(self):
        """🏗️ Initialize the instance."""
        super().__init__()
        self.setWindowTitle("GeoE3")
        # For running study area processing in a separate thread
        self.queue_manager = WorkflowQueueManager(pool_size=1)

        # Connect the error_occurred signal to show error message
        self.queue_manager.processing_error.connect(self.show_error_message)

        self.working_directory = ""
        self.settings = QSettings()  # Initialize QSettings to store and retrieve settings
        # Dynamically load the .ui file
        self._reference_layer = None
        self._crs = None  # Study area CRS
        self._message_bar = None  # Will be set by parent dock
        self._current_layer_path = ""  # What's actually saved in model.json
        self.setupUi(self)
        log_message("Loading setup panel")
        self.initUI()

    def show_error_message(self, message, details=None):
        """Show an error message box when workflow queue manager reports an error.

        Args:
            message: The error message to display.
            details: Optional detailed error information.
        """
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Error")
        msg_box.setText(message)
        if details:
            msg_box.setDetailedText(details)
        msg_box.exec()
        self.progress_bar.setVisible(False)
        self.child_progress_bar.setVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("OSM download failed")
        self.enable_widgets()  # Re-enable widgets in case they were disabled

    @pyqtSlot(str)
    def working_directory_changed(self, new_directory):
        """Change the working directory and load the model.json if available.

        Args:
            new_directory: The new working directory path.
        """
        log_message(f"Working directory changed to {new_directory}")
        self.working_directory = new_directory

    def set_working_directory(self, working_directory):
        """Set the working directory for the task.

        Args:
            working_directory: The working directory path.

        Raises:
            Exception: If the working directory is invalid.
        """
        log_message(f"Setting the working directory to {working_directory}")
        if working_directory is None or working_directory == "":
            raise Exception("Invalid working directory: None or empty string")
        if not os.path.exists(working_directory):
            raise Exception(f"Invalid working directory: {working_directory}")
        if not os.path.isdir(working_directory):
            raise Exception(f"Invalid working directory: {working_directory}")
        self.working_directory = working_directory
        # Restore reference layer from model.json if available
        self.restore_reference_layer_from_model()

    def restore_reference_layer_from_model(self):
        """Restore reference layer from saved path in model.json."""
        if not self.working_directory:
            return
        model_path = os.path.join(self.working_directory, "model.json")
        if not os.path.exists(model_path):
            return
        try:
            with open(model_path, "r") as f:
                model = json.load(f)
            admin_source = model.get("admin_boundary_layer_source")
            if admin_source and os.path.exists(admin_source):
                base_path = admin_source.split("|")[0] if "|" in admin_source else admin_source
                layer_name = os.path.splitext(os.path.basename(base_path))[0]
                layer = QgsVectorLayer(admin_source, layer_name, "ogr")
                if layer.isValid():
                    self._reference_layer = layer
                    log_message(f"Restored reference layer from: {admin_source}", level=Qgis.Info)
                else:
                    log_message(f"Cannot restore reference layer - invalid: {admin_source}", level=Qgis.Warning)
            else:
                log_message("No reference layer path found in model.json", level=Qgis.Info)
        except Exception as e:
            log_message(f"Error restoring reference layer: {e}", level=Qgis.Warning)

    def set_reference_layer(self, layer):
        """⚙️ Set reference layer.

        Args:
            layer: Layer.
        """
        self._reference_layer = layer

    def set_crs(self, crs):
        """⚙️ Set study area CRS and re-validate current layer.

        Args:
            crs: Study area CRS (from study_area.gpkg, not QGIS project CRS).
        """
        self._crs = crs
        self._refresh_status_label()  # Re-validate with new CRS

    def set_message_bar(self, message_bar):
        """⚙️ Set message bar reference.

        Args:
            message_bar: QgsMessageBar instance from parent dock.
        """
        self._message_bar = message_bar

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

        # self.folder_status_label.setPixmap(
        #     QPixmap(resources_path("resources", "icons", "failed.svg"))
        # )
        self.network_layer_combo.setFilters(QgsMapLayerProxyModel.Filter.LineLayer)
        self.change_network_layer_button.clicked.connect(self.on_change_network_layer_clicked)
        self.browse_network_layer_button.clicked.connect(self._browse_for_network_layer_file)
        self.ok_network_layer_button.clicked.connect(self.on_network_layer_ok_clicked)
        self.cancel_network_layer_button.clicked.connect(self.on_network_layer_cancel_clicked)
        self.download_active_transport_button.clicked.connect(self.download_active_transport_button_clicked)
        self.description.setTextFormat(Qt.TextFormat.RichText)
        self.description.linkActivated.connect(self.open_link_in_browser)
        self.description6.setTextFormat(Qt.TextFormat.RichText)
        self.description6.setText(
            "Download a unified active transport network (roads + cycleways combined). "
            "Please note that the OpenStreetMap servers can be busy at times. If your download fails, "
            "either wait a little bit, then try to download again. Alternatively, you can get the data "
            "manually from <a href='https://www.geofabrik.de/'>https://www.geofabrik.de/</a>."
        )
        self.description6.linkActivated.connect(self.open_link_in_browser)

        self.next_button.clicked.connect(self.on_next_button_clicked)
        self.previous_button.clicked.connect(self.on_previous_button_clicked)

        self.progress_bar.setVisible(False)
        self.child_progress_bar.setVisible(False)

        self._refresh_status_label()

        # Start with next button disabled until a valid road layer is selected
        self._update_next_button_state()

    def open_link_in_browser(self, url: str):
        """Open the given URL in the user's default web browser using QDesktopServices."""
        QDesktopServices.openUrl(QUrl(url))

    def on_change_network_layer_clicked(self):
        """Swap the read-only label/button for the inline picker row.

        network_layer_combo has no signal connected to it anywhere (its
        currentLayer() is only ever read once, on Ok) - sitting there
        hidden the rest of the time is harmless, nothing is listening to
        it that could write to the model on its own.
        """
        if not self.working_directory:
            QMessageBox.critical(self, "Error", "Open or create a GeoE3 project first.")
            return
        self._enter_edit_mode()

    def _enter_edit_mode(self):
        """Show the combo/browse/Ok/Cancel row, hide the read-only label/button."""
        self.current_layer_label.setVisible(False)
        self.change_network_layer_button.setVisible(False)
        self.network_layer_combo.setVisible(True)
        self.browse_network_layer_button.setVisible(True)
        self.ok_network_layer_button.setVisible(True)
        self.cancel_network_layer_button.setVisible(True)

    def _exit_edit_mode(self):
        """Hide the combo/browse/Ok/Cancel row, show the read-only label/button again."""
        self.network_layer_combo.setVisible(False)
        self.browse_network_layer_button.setVisible(False)
        self.ok_network_layer_button.setVisible(False)
        self.cancel_network_layer_button.setVisible(False)
        self.current_layer_label.setVisible(True)
        self.change_network_layer_button.setVisible(True)

    def _browse_for_network_layer_file(self):
        """Load a layer from disk and select it in the inline combo."""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Shapefile (*.shp);;GeoPackage (*.gpkg)")
        if not file_dialog.exec():
            return

        file_path = file_dialog.selectedFiles()[0]
        layer_name = os.path.splitext(os.path.basename(file_path))[0]
        layer = QgsVectorLayer(file_path, layer_name, "ogr")
        if not layer.isValid():
            QMessageBox.critical(self, "Error", "Could not load the selected file as a layer.")
            return

        QgsProject.instance().addMapLayer(layer)
        self.network_layer_combo.setLayer(layer)

    def on_network_layer_ok_clicked(self):
        """Commit whatever the inline combo currently shows, then exit edit mode."""
        layer = self.network_layer_combo.currentLayer()
        if layer is not None:
            self._finalize_road_layer_selection(layer)
        self._exit_edit_mode()

    def on_network_layer_cancel_clicked(self):
        """Discard the in-progress pick and exit edit mode without committing anything."""
        self._exit_edit_mode()

    def _finalize_road_layer_selection(self, layer):
        """Validate, reproject if needed, and commit a user-chosen road network layer.

        This is the only place that emits road_network_layer_path_changed -
        always from one explicit, synchronous action (a file pick, an OSM
        download finishing, or the picker dialog's Ok), never from a
        combo reacting to ambient QGIS/project signals.

        Args:
            layer: The QgsVectorLayer the user chose.
        """
        if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.GeometryType.LineGeometry:
            geometry_name = QgsWkbTypes.displayString(layer.wkbType())
            QMessageBox.critical(
                self,
                "Error",
                "Road network layer must be a line (polyline) layer.\n"
                f"Selected file contains: {geometry_name} geometry.\n"
                "Please select a line/polyline layer.",
            )
            return

        final_layer, final_path = self._reproject_if_needed(layer)
        if final_layer is None:
            self.layer_status_label.setPixmap(QPixmap(resources_path("resources", "icons", "failed.svg")))
            self.layer_status_label.setToolTip("Failed to reproject the selected layer.")
            return

        self._current_layer_path = final_path
        self._refresh_status_label()
        self.road_network_layer_path_changed.emit(final_path)

    def _reproject_if_needed(self, layer):
        """Reproject layer to the study area CRS if needed, reusing an existing file if present.

        Args:
            layer: Source QgsVectorLayer.

        Returns:
            tuple: (final_layer, final_path) - (None, None) on failure.
        """
        if not self._crs or layer.crs() == self._crs:
            return layer, layer.source()

        output_name = self._generate_reprojected_filename(layer, self._crs)
        expected_path = os.path.join(self.working_directory, "study_area", f"{output_name}.gpkg")
        if os.path.exists(expected_path):
            existing = QgsVectorLayer(expected_path, output_name, "ogr")
            if existing.isValid() and existing.crs() == self._crs:
                log_message(f"Reusing existing reprojected layer: {expected_path}", level=Qgis.Info)
                QgsProject.instance().addMapLayer(existing)
                return existing, existing.source()

        log_message(
            f"Road network CRS ({layer.crs().authid()}) doesn't match study area CRS "
            f"({self._crs.authid()}). Reprojecting...",
            level=Qgis.Info,
        )
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            success, reprojected_path, reprojected_layer = self._reproject_layer_to_file(layer, output_name=output_name)
        finally:
            QApplication.restoreOverrideCursor()

        if not success:
            log_message("Failed to reproject road network layer", level=Qgis.Critical)
            return None, None
        return reprojected_layer, reprojected_path

    def _refresh_status_label(self):
        """Reflect self._current_layer_path in the label, icon and Next button."""
        if not self._current_layer_path:
            self.current_layer_label.setText("Not set")
            self.layer_status_label.setPixmap(QPixmap(resources_path("resources", "icons", "failed.svg")))
            self.layer_status_label.setToolTip("No road network layer selected")
        else:
            base_path = (
                self._current_layer_path.split("|")[0] if "|" in self._current_layer_path else self._current_layer_path
            )
            self.current_layer_label.setText(os.path.basename(base_path))
            self.current_layer_label.setToolTip(self._current_layer_path)
            self.layer_status_label.setPixmap(QPixmap(resources_path("resources", "icons", "completed-success.svg")))
            self.layer_status_label.setToolTip(f"✓ {self._current_layer_path}")
        self._update_next_button_state()

    def _update_next_button_state(self):
        """Enable or disable next button based on whether a road layer is set."""
        self.next_button.setEnabled(bool(self._current_layer_path))

    def _generate_reprojected_filename(self, source_layer, target_crs):
        """Generate unique filename based on original layer name and target CRS.

        Args:
            source_layer: The original QgsVectorLayer to reproject.
            target_crs: The target QgsCoordinateReferenceSystem.

        Returns:
            str: A unique filename prefix (without extension).
        """
        import re

        # Get base name from layer source (without extension)
        source = source_layer.source()
        base_name = os.path.splitext(os.path.basename(source))[0]
        # Sanitize for filesystem
        safe_name = re.sub(r"[^\w\-]", "_", base_name).strip("_")
        # Include target CRS to distinguish different reprojections
        crs_suffix = target_crs.authid().replace(":", "_")
        return f"{safe_name}_reprojected_{crs_suffix}"

    def on_next_button_clicked(self):
        """⚙️ On next button clicked."""
        self.switch_to_next_tab.emit()

    def on_previous_button_clicked(self):
        """⚙️ On previous button clicked."""
        self.switch_to_previous_tab.emit()

    def road_network_layer_path(self):
        """⚙️ Road network layer path.

        Returns:
            The result of the operation.
        """
        return self._current_layer_path or None

    def _reproject_layer_to_file(self, source_layer, output_name="road_network_reprojected"):
        """Reproject a layer to study area CRS and save to study_area directory.

        Low-level helper used by _reproject_if_needed().

        Args:
            source_layer: QgsVectorLayer to reproject
            output_name: Base name for output file (without extension)

        Returns:
            Tuple of (success: bool, output_path: str or None, layer: QgsVectorLayer or None)
        """
        # Validate working directory
        if not self.working_directory:
            QMessageBox.critical(
                self,
                "Error",
                "Working directory not set. Cannot reproject layer.",
            )
            return False, None, None

        try:
            reprojected_path = os.path.join(
                self.working_directory,
                "study_area",
                f"{output_name}.gpkg",
            )

            # Ensure output directory exists
            os.makedirs(os.path.dirname(reprojected_path), exist_ok=True)

            log_message(
                f"Reprojecting {source_layer.name()} from {source_layer.crs().authid()} " f"to {self._crs.authid()}",
                level=Qgis.Info,
            )

            # Run reprojection
            result = processing.run(
                "native:reprojectlayer",
                {"INPUT": source_layer, "TARGET_CRS": self._crs, "OUTPUT": reprojected_path},
            )

            if not (result and "OUTPUT" in result):
                QMessageBox.critical(self, "Error", f"Failed to reproject layer to {self._crs.authid()}")
                return False, None, None

            # Load reprojected layer - use original layer name with "(reprojected)" suffix
            reprojected_layer = QgsVectorLayer(reprojected_path, f"{source_layer.name()} (reprojected)", "ogr")

            if not reprojected_layer.isValid():
                QMessageBox.critical(self, "Error", "Reprojected layer is invalid")
                return False, None, None

            # Add to QGIS project for user visibility
            QgsProject.instance().addMapLayer(reprojected_layer)

            log_message(
                f"Layer successfully reprojected and saved to {reprojected_path}",
                level=Qgis.Info,
            )

            return True, reprojected_path, reprojected_layer

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error during reprojection: {str(e)}")
            log_message(f"Reprojection error: {str(e)}", level=Qgis.Critical)
            return False, None, None

    def _warn_road_network_broken(self, message: str) -> None:
        """Log and surface a user-visible warning about a broken road network reference.

        Args:
            message: Description of what is wrong with the stored layer.
        """
        log_message(message, level=Qgis.Warning)
        if self._message_bar:
            self._message_bar.pushMessage(
                "GEOE3",
                f"{message} Please select or download a road network layer again.",
                level=Qgis.Warning,
                duration=10,
            )

    def restore_layer_from_path(self, layer_path):
        """Reflect a path already saved in model.json in the read-only label.

        This only ever updates the label/icon - it never touches QGIS's
        layer registry and never emits road_network_layer_path_changed, so
        calling it (when switching to this panel, opening a project, or
        after a project switch) can never write anything back.

        Args:
            layer_path (str): Path to road network layer (may include |layername=)
        """
        if not layer_path:
            self._current_layer_path = ""
            self._refresh_status_label()
            return

        already_loaded = any(
            hasattr(layer, "source") and layer.source() == layer_path
            for layer in QgsProject.instance().mapLayers().values()
        )
        base_path = layer_path.split("|")[0] if "|" in layer_path else layer_path
        if not already_loaded and not os.path.exists(base_path):
            self._warn_road_network_broken(f"Road network layer file not found: {base_path}")
            self._current_layer_path = ""
            self._refresh_status_label()
            return

        self._current_layer_path = layer_path
        self._refresh_status_label()
        log_message(f"Restored road network display from path: {layer_path}", level=Qgis.Info)

    def load_reference_layer(self):
        """Load reference (admin boundary) layer from file."""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Shapefile (*.shp);;GeoPackage (*.gpkg)")

        if not file_dialog.exec():
            return

        file_path = file_dialog.selectedFiles()[0]
        layer_name = os.path.splitext(os.path.basename(file_path))[0]
        layer = QgsVectorLayer(file_path, layer_name, "ogr")

        if not layer.isValid():
            QMessageBox.critical(self, "Error", "Could not load the boundary layer.")
            return

        self._reference_layer = layer
        log_message(f"Loaded reference layer: {file_path}", level=Qgis.Info)

        # Save to model.json
        if self.working_directory:
            model_path = os.path.join(self.working_directory, "model.json")
            if os.path.exists(model_path):
                try:
                    with open(model_path, "r") as f:
                        model = json.load(f)
                    model["admin_boundary_layer_source"] = layer.source()
                    with open(model_path, "w") as f:
                        json.dump(model, f, indent=2)
                    log_message("Saved reference layer path to model.json", level=Qgis.Info)
                except Exception as e:
                    log_message(f"Error saving reference layer to model.json: {e}", level=Qgis.Warning)

    def disable_widgets(self):
        """Disable all widgets in the panel."""
        for widget in self.findChildren(QWidget):
            widget.setEnabled(False)

    def enable_widgets(self):
        """Enable all widgets in the panel."""
        for widget in self.findChildren(QWidget):
            widget.setEnabled(True)
        # Keep Next button gated by layer validity after any state reset.
        self._update_next_button_state()

    def _get_bbox_from_study_area(self):
        """Get bounding box from existing study_area.gpkg.

        Returns:
            tuple: (xmin, ymin, xmax, ymax) in EPSG:4326, or None if not found
        """
        if not self.working_directory:
            return None

        study_area_gpkg = os.path.join(self.working_directory, "study_area", "study_area.gpkg")
        if not os.path.exists(study_area_gpkg):
            log_message(f"Study area gpkg not found: {study_area_gpkg}", level=Qgis.Warning)
            return None

        try:
            # Read the study area layer to get bbox
            layer = QgsVectorLayer(f"{study_area_gpkg}|layername=study_area_polygons", "study_area", "ogr")
            if not layer.isValid():
                log_message("Study area layer is invalid", level=Qgis.Warning)
                return None

            # Get the bounding box in EPSG:4326
            extent = layer.extent()
            crs = layer.crs()

            # Transform to WGS84 if needed
            if crs.authid() != "EPSG:4326":
                dest_crs = QgsCoordinateReferenceSystem()
                dest_crs.createFromString("EPSG:4326")
                transform = QgsCoordinateTransform(crs, dest_crs, QgsProject.instance())
                extent = transform.transformBoundingBox(extent)

            log_message(
                f"Got bbox from study area: {extent.toString()}",
                level=Qgis.Info,
            )
            return extent
        except Exception as e:
            log_message(f"Error getting bbox from study area: {e}", level=Qgis.Warning)
            return None

    def download_active_transport_button_clicked(self):
        """Triggered when the Download Active Transport button is pressed."""
        if self._crs is None:
            QMessageBox.critical(self, "Error", "No CRS is set, unable to continue.")
            return
        if self.working_directory is None or self.working_directory == "":
            QMessageBox.critical(self, "Error", "Working directory is not set")
            return

        # Check if the layer already exists
        network_layer_path = os.path.join(self.working_directory, "study_area", "active_transport_network.gpkg")
        if os.path.exists(network_layer_path):
            # Layer already downloaded - just load it
            log_message(
                "Active transport network already exists, loading from cache",
                tag="GeoE3",
                level=Qgis.Info,
            )
            network_layer_path_with_layer = f"{network_layer_path}|layername=active_transport_network"
            layer_name = os.path.splitext(os.path.basename(network_layer_path))[0]
            layer = QgsVectorLayer(network_layer_path_with_layer, layer_name, "ogr")
            if layer.isValid():
                # Load the layer in QGIS and commit it as the road network
                QgsProject.instance().addMapLayer(layer)
                self._finalize_road_layer_selection(layer)
                if self._message_bar:
                    self._message_bar.pushMessage(
                        "GEOE3",
                        "Active transport network loaded from cache (already downloaded)",
                        level=Qgis.Info,
                        duration=5,
                    )
                return
            else:
                # File exists but is invalid - remove it and re-download
                log_message(
                    "Existing active transport network file is invalid, will re-download",
                    tag="GeoE3",
                    level=Qgis.Warning,
                )
                os.remove(network_layer_path)

        # Create the processor instance and process the features
        debug_env = int(os.getenv("GEOE3_DEBUG") or os.getenv("GEEST_DEBUG", 0))
        feedback = QgsFeedback()  # Used to cancel tasks and measure subtask progress

        # Determine what to use: reference_layer or extents from study_area
        reference_layer = self._reference_layer
        extents = None

        if reference_layer is None:
            # Try to get bbox from study_area.gpkg automatically
            extents = self._get_bbox_from_study_area()
            if extents is None:
                QMessageBox.critical(
                    self,
                    "Error",
                    "No boundary layer and no study area found. Please create a project first.",
                )
                return
            log_message("Using bbox from study area for OSM download", level=Qgis.Info)

        try:
            log_message("Creating OSM Active Transport Downloader Task")
            processor = OSMDownloaderTask(
                reference_layer=reference_layer,
                extents=extents,
                osm_download_type=OSMDownloadType.ACTIVE_TRANSPORT,
                crs=self._crs,
                working_dir=self.working_directory,
                filename="active_transport_network",
                use_cache=True,
                delete_gpkg=True,
                feedback=feedback,
            )
            log_message("OSM Active Transport Downloader Task created, setting up call backs")
            # Hook up the QTask feedback signal to the progress bar
            # Measure overall task progress from the task object itself
            processor.progressChanged.connect(self.osm_download_progress_updated)
            processor.taskCompleted.connect(self.active_transport_download_done)
            processor.taskTerminated.connect(self.active_transport_download_terminated)
            # Measure subtask progress from the feedback object
            feedback.progressChanged.connect(self.osm_extract_progress_updated)
            self.disable_widgets()
            if debug_env:
                processor.run()
            else:
                log_message("Adding task to queue manager")
                self.queue_manager.add_task(processor)
                self.queue_manager.start_processing()
                log_message("Processing started")
        except Exception as e:
            trace = traceback.format_exc()
            QMessageBox.critical(
                self, "Error", f"Error downloading active transport network for study area: {e}\n{trace}"
            )
            self.enable_widgets()
            return

    # Slot that listens for changes in the study_area task object which is used to measure overall task progress
    def osm_download_progress_updated(self, progress: float):
        """Slot to be called when the download task progress is updated.

        Args:
            progress: The download progress value.
        """
        log_message(f"\n\n\n\n\n\nProgress: {progress}\n\n\n\n\n\n\n\n")
        self.progress_bar.setVisible(True)
        self.progress_bar.setEnabled(True)
        self.progress_bar.setValue(int(progress))
        if progress == 0:
            self.progress_bar.setFormat("Fetching OSM data...")
            self.progress_bar.setMinimum(0)  # makes it bounce indefinitely
            self.progress_bar.setMaximum(0)
        else:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)

            # This is a sneaky hack to show the exact progress in the label
            # since QProgressBar only takes ints. See Qt docs for more info.
            # Use the 'setFormat' method to display the exact float:
            float_value_as_string = f"OSM download progress: {progress}%"
            self.progress_bar.setFormat(float_value_as_string)

    # Slot that listens for changes in the progress object which is used to measure subtask progress
    def osm_extract_progress_updated(self, progress: float):
        """⚙️ Osm extract progress updated.

        Args:
            progress: Progress.
        """
        self.child_progress_bar.setVisible(True)
        self.child_progress_bar.setEnabled(True)
        if progress == 0:
            self.progress_bar.setFormat("Extracting OSM data...")
            self.progress_bar.setMinimum(0)  # makes it bounce indefinitely
            self.progress_bar.setMaximum(0)
        else:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
            self.child_progress_bar.setValue(int(progress))
            # This is a sneaky hack to show the exact progress in the label
            # since QProgressBar only takes ints. See Qt docs for more info.
            # Use the 'setFormat' method to display the exact float:
            float_value_as_string = f"OSM extract progress: {progress}%"
            self.child_progress_bar.setFormat(float_value_as_string)

    def active_transport_download_done(self):
        """⚙️ Active transport download done."""
        log_message(
            "*** OSM Active Transport download completed successfully. ***",
            tag="GeoE3",
            level=Qgis.Info,
        )
        network_layer_path = os.path.join(self.working_directory, "study_area", "active_transport_network.gpkg")
        network_layer_path = f"{network_layer_path}|layername=active_transport_network"
        log_message(f"Loading active transport network layer from {network_layer_path}")
        layer_name = os.path.splitext(os.path.basename(network_layer_path.split("|")[0]))[0]
        layer = QgsVectorLayer(network_layer_path, layer_name, "ogr")
        if not layer.isValid():
            QMessageBox.critical(self, "Error", "Could not load the active transport network layer.")
            return
        # Load the layer in QGIS and commit it as the road network
        QgsProject.instance().addMapLayer(layer)
        self._finalize_road_layer_selection(layer)
        self.progress_bar.setVisible(False)
        self.child_progress_bar.setVisible(False)
        self.enable_widgets()

    def active_transport_download_terminated(self):
        """Handle OSM task termination and keep navigation state safe."""
        log_message(
            "OSM Active Transport download task terminated.",
            tag="GeoE3",
            level=Qgis.Warning,
        )
        self.progress_bar.setVisible(False)
        self.child_progress_bar.setVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("OSM download failed")
        self.enable_widgets()

    def resizeEvent(self, event):
        """⚙️ Resizeevent.

        Args:
            event: Event.
        """
        self.set_font_size()
        super().resizeEvent(event)

    def set_font_size(self):
        """⚙️ Set font size."""
        # Scale the font size to fit the text in the available space
        # log_message(f"Description Label Width: {self.description.rect().width()}")
        # scale the font size linearly from 16 pt to 8 ps as the width of the panel decreases
        font_size = int(linear_interpolation(self.description.rect().width(), 12, 16, 400, 800))

        # log_message(f"Description Label Font Size: {font_size}")
        self.description.setFont(QFont("Arial", font_size))
        self.description6.setFont(QFont("Arial", font_size))
        self.current_layer_label.setFont(QFont("Arial", font_size))
        self.change_network_layer_button.setFont(QFont("Arial", font_size))
        self.network_layer_combo.setFont(QFont("Arial", font_size))
        self.browse_network_layer_button.setFont(QFont("Arial", font_size))
        self.ok_network_layer_button.setFont(QFont("Arial", font_size))
        self.cancel_network_layer_button.setFont(QFont("Arial", font_size))
        self.download_active_transport_button.setFont(QFont("Arial", font_size))

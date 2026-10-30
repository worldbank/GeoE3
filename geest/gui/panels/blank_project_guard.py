# -*- coding: utf-8 -*-
"""📦 Blank project guard module.

This module contains functionality for making sure a blank QGIS
project is open before an action - importing a country pack - that
would otherwise silently mix a different project's data into whatever
is already open.
"""

from qgis.core import QgsProject
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox, QWidget

from geest.utilities import log_message


def is_qgis_project_blank() -> bool:
    """Whether the currently open QGIS project is blank.

    Returns:
        True if QgsProject.instance() has no filename and no layers.
    """
    project = QgsProject.instance()
    return not project.fileName() and not project.mapLayers()


def ensure_blank_qgis_project(parent: QWidget) -> bool:
    """Make sure a blank QGIS project is open, prompting to save first if needed.

    Args:
        parent: Widget to parent the save/cancel dialogs to.

    Returns:
        True once a blank project is open and it's safe to proceed,
        False if the user cancelled, or a save attempt failed.
    """
    if is_qgis_project_blank():
        return True

    project = QgsProject.instance()
    reply = QMessageBox.question(
        parent,
        "Save current project?",
        "This starts a new, blank QGIS project. Save your current project first?",
        QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Save,
    )
    if reply == QMessageBox.StandardButton.Cancel:
        return False

    if reply == QMessageBox.StandardButton.Save:
        path = project.fileName()
        if not path:
            path, _ = QFileDialog.getSaveFileName(parent, "Save Project As", "", "QGIS Project (*.qgz *.qgs)")
            if not path:
                return False
        if not project.write(path):
            QMessageBox.critical(parent, "Save failed", f"Could not save the current project to '{path}'.")
            return False

    project.clear()
    log_message("Started a new, blank QGIS project.", tag="GeoE3")
    return True

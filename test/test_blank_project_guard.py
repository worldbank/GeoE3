# -*- coding: utf-8 -*-
"""Blank-project guard: save-prompt-then-clear flow, exercised without a real modal.

QMessageBox.question()/QFileDialog.getSaveFileName() are monkeypatched
per test - a real modal would block forever with no user present.
"""

import os
import shutil
import tempfile
import unittest

from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox, QWidget

from geest.gui.panels.blank_project_guard import ensure_blank_qgis_project, is_qgis_project_blank

QGIS_APP = QgsApplication([], False)
QGIS_APP.initQgis()
PARENT = QWidget()


class TestBlankProjectGuard(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self._orig_question = QMessageBox.question
        self._orig_save_dialog = QFileDialog.getSaveFileName
        self._tmp_dirs = []

    def tearDown(self):
        QMessageBox.question = self._orig_question
        QFileDialog.getSaveFileName = self._orig_save_dialog
        QgsProject.instance().clear()
        for path in self._tmp_dirs:
            shutil.rmtree(path, ignore_errors=True)

    def _add_layer(self):
        QgsProject.instance().addMapLayer(QgsVectorLayer("Point?crs=EPSG:4326", "test", "memory"))

    def test_blank_project_proceeds_with_no_prompt(self):
        self.assertTrue(is_qgis_project_blank())
        self.assertTrue(ensure_blank_qgis_project(PARENT))

    def test_discard_clears_the_project_and_proceeds(self):
        self._add_layer()
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Discard)
        self.assertTrue(ensure_blank_qgis_project(PARENT))
        self.assertTrue(is_qgis_project_blank())

    def test_cancel_leaves_the_project_untouched(self):
        self._add_layer()
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel)
        self.assertFalse(ensure_blank_qgis_project(PARENT))
        self.assertFalse(is_qgis_project_blank())

    def test_save_with_no_filename_prompts_save_as_and_cancelling_that_aborts(self):
        self._add_layer()
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Save)
        QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
        self.assertFalse(ensure_blank_qgis_project(PARENT))
        self.assertFalse(is_qgis_project_blank())

    def test_save_with_a_chosen_path_writes_then_clears(self):
        self._add_layer()
        tmp_dir = tempfile.mkdtemp()
        self._tmp_dirs.append(tmp_dir)
        save_path = os.path.join(tmp_dir, "saved_project.qgz")
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Save)
        QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (save_path, ""))

        self.assertTrue(ensure_blank_qgis_project(PARENT))

        self.assertTrue(os.path.exists(save_path))
        self.assertTrue(is_qgis_project_blank())


if __name__ == "__main__":
    unittest.main()

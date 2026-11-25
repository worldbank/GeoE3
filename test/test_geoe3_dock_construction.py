# -*- coding: utf-8 -*-
"""Construct the full GeoE3 dock (all panels) headless.

Every QGIS 4 / PyQt6 startup crash so far lived in panel constructor code
(unscoped enums, int-to-enum coercion). Building the complete dock in the
suite executes all of those paths on both the PyQt5 and PyQt6 images, so
the next porting regression fails a test instead of failing plugin load.
"""

import unittest

from utilities_for_testing import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()

from qgis.PyQt.QtCore import Qt  # noqa: E402

from geest import _dock_area_to_int, _to_dock_widget_area  # noqa: E402
from geest.gui.geoe3_dock import CREDITS_PANEL, SETUP_PANEL, TREE_PANEL, GeoE3Dock  # noqa: E402
from geest.utilities import resources_path  # noqa: E402


class TestGeoE3DockConstruction(unittest.TestCase):
    def test_dock_constructs_with_all_panels(self):
        """The dock (and thereby every panel constructor) builds cleanly."""
        dock = GeoE3Dock(parent=PARENT, json_file=resources_path("resources", "model.json"))
        self.assertGreater(dock.stacked_widget.count(), 0)

    def test_ors_next_with_stale_working_directory_is_survivable(self):
        """Next on the ORS panel with a vanished project folder must not raise.

        This slot runs from a Qt signal: on PyQt6 an exception escaping it
        aborts QGIS (qFatal), so a stale working directory (moved/renamed
        project folder) has to end in a message-bar warning instead.
        """
        dock = GeoE3Dock(parent=PARENT, json_file=resources_path("resources", "model.json"))
        for stale in ("/no/such/folder", "", None):
            dock.create_project_widget.working_dir = stale
            dock.tree_widget.working_directory = ""
            before = dock.stacked_widget.currentIndex()
            dock._open_road_network_from_ors()  # must not raise
            self.assertEqual(
                dock.stacked_widget.currentIndex(),
                before,
                f"panel switched despite invalid working directory {stale!r}",
            )

    def test_setup_panel_back_button_returns_to_tree_when_a_project_is_open(self):
        """Clicking "Project" on an open project, then "<-" on Setup, must
        return to the tree - it used to always go to Credits regardless,
        stranding the user with no way back (worldbank/GeoE3 field
        report, 2026-11-25)."""
        dock = GeoE3Dock(parent=PARENT, json_file=resources_path("resources", "model.json"))
        dock.tree_widget.working_directory = "/some/open/project"
        dock.stacked_widget.setCurrentIndex(SETUP_PANEL)

        dock._open_previous_panel_before_setup()

        self.assertEqual(dock.stacked_widget.currentIndex(), TREE_PANEL)

    def test_setup_panel_back_button_returns_to_credits_when_no_project_is_open(self):
        """The original onboarding flow (Credits -> Setup -> ...) is unchanged."""
        dock = GeoE3Dock(parent=PARENT, json_file=resources_path("resources", "model.json"))
        dock.tree_widget.working_directory = None
        dock.stacked_widget.setCurrentIndex(SETUP_PANEL)

        dock._open_previous_panel_before_setup()

        self.assertEqual(dock.stacked_widget.currentIndex(), CREDITS_PANEL)

    def test_dock_area_to_int_portable(self):
        """Enum → int works on PyQt5 sip enums and PyQt6 pure Flags alike."""
        self.assertEqual(_dock_area_to_int(Qt.DockWidgetArea.LeftDockWidgetArea), 1)
        self.assertEqual(_dock_area_to_int(Qt.DockWidgetArea.RightDockWidgetArea), 2)

    def test_dock_widget_area_coercion(self):
        """QSettings ints (and junk) coerce to a valid Qt.DockWidgetArea."""
        right = Qt.DockWidgetArea.RightDockWidgetArea
        left = Qt.DockWidgetArea.LeftDockWidgetArea
        self.assertEqual(_to_dock_widget_area(1), left)
        self.assertEqual(_to_dock_widget_area(2), right)
        self.assertEqual(_to_dock_widget_area(0), right)  # NoDockWidgetArea
        self.assertEqual(_to_dock_widget_area(999), right)
        self.assertEqual(_to_dock_widget_area(None), right)
        self.assertEqual(_to_dock_widget_area("2"), right)
        self.assertEqual(_to_dock_widget_area("junk"), right)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Regression test for TreePanel.disable_item()/enable_item().

TreePanel is a heavy QWidget that needs a loaded .ui file and a full
JsonTreeModel to construct, so this test calls the unbound methods
against a lightweight MagicMock stand-in instead of a real TreePanel,
matching the pattern in test_tree_panel_clear_item.py.

Guards against a real production bug: item.disable()/item.enable()
mutate the attributes dict directly, not through the model's own edit
flow, so neither the tree view's repaint nor the save-on-change hookup
(self.model.dataChanged -> save_json_to_working_directory()) fired on
its own - the context menu's "Disable"/"Enable" changed the item's
analysis_mode in memory, but nothing told the view to repaint or the
project to save, so the change looked like a no-op and was lost on the
next reload (worldbank/GeoE3 field report, 2026-11-25).
"""
import unittest
from unittest.mock import MagicMock

from geest.core.json_tree_item import JsonTreeItem
from geest.gui.panels.tree_panel import TreePanel


def _make_item(name, role, parent=None):
    data = [name, "Configured", 1.0, {"id": name, "analysis_mode": "use_point_per_cell"}]
    item = JsonTreeItem(data, role=role, parent=parent)
    if parent is not None:
        parent.appendChild(item)
    return item


class TestDisableItemPersistsAndRefreshes(unittest.TestCase):
    def setUp(self):
        self.indicator = _make_item("Some Indicator", "indicator")
        self.panel = MagicMock()

    def test_disable_marks_the_item_do_not_use(self):
        TreePanel.disable_item(self.panel, self.indicator)

        self.assertEqual(self.indicator.attributes()["analysis_mode"], "Do Not Use")

    def test_disable_saves_the_model(self):
        TreePanel.disable_item(self.panel, self.indicator)

        self.panel.save_json_to_working_directory.assert_called_once()

    def test_disable_refreshes_the_tree_view(self):
        TreePanel.disable_item(self.panel, self.indicator)

        self.panel._refresh_tree_view.assert_called_once()

    def test_disable_updates_the_run_all_button_state(self):
        TreePanel.disable_item(self.panel, self.indicator)

        self.panel._update_run_all_button_state.assert_called_once()


class TestEnableItemPersistsAndRefreshes(unittest.TestCase):
    def setUp(self):
        self.indicator = _make_item("Some Indicator", "indicator")
        self.indicator.attributes()["analysis_mode"] = "Do Not Use"
        self.panel = MagicMock()

    def test_enable_clears_the_do_not_use_mode(self):
        TreePanel.enable_item(self.panel, self.indicator)

        self.assertNotEqual(self.indicator.attributes()["analysis_mode"], "Do Not Use")

    def test_enable_saves_the_model(self):
        TreePanel.enable_item(self.panel, self.indicator)

        self.panel.save_json_to_working_directory.assert_called_once()

    def test_enable_refreshes_the_tree_view(self):
        TreePanel.enable_item(self.panel, self.indicator)

        self.panel._refresh_tree_view.assert_called_once()


if __name__ == "__main__":
    unittest.main()

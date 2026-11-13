# -*- coding: utf-8 -*-
"""Unit tests for TreePanel's result-invalidation on config edits.

Changing a setting that actually affects what gets computed - a
datasource, an analysis_mode, an aggregation type, a mask layer - must
clear the previously computed result (on-disk outputs, grid column,
and the "result"/"result_file" attributes) for the item edited AND
every ancestor whose cached aggregate was computed including it.
Changing ONLY a weighting must not - weighting is applied during
aggregation, after an indicator's own result already exists, and
changing a factor/dimension weighting doesn't make the dimension/
analysis's own PREVIOUSLY COMPUTED aggregate value wrong in a way this
project already treats as invalidating (see
TreePanel._WEIGHTING_AND_BOOKKEEPING_KEYS).

TreePanel is a heavy QWidget that needs a loaded .ui file to construct,
so these tests call the unbound methods against a lightweight MagicMock
stand-in, following the established pattern elsewhere in this suite.
"""
import types
import unittest
from unittest.mock import MagicMock, patch

from geest.core.json_tree_item import JsonTreeItem
from geest.gui.panels.tree_panel import TreePanel


def _bind(panel, *names):
    """Bind real TreePanel methods onto a MagicMock stand-in, instance or static alike.

    Needed for any method under test that itself calls another real
    TreePanel method on self - unbound, that call would resolve against
    the mock's own auto-generated (and semantically meaningless)
    attribute instead.
    """
    for name in names:
        raw = TreePanel.__dict__.get(name)
        if isinstance(raw, staticmethod):
            setattr(panel, name, raw.__func__)
        else:
            setattr(panel, name, types.MethodType(getattr(TreePanel, name), panel))


class TestConfigFingerprint(unittest.TestCase):
    def test_weighting_and_bookkeeping_keys_are_excluded(self):
        attrs = {
            "analysis_mode": "use_nighttime_lights",
            "factor_weighting": 1.0,
            "result": "Workflow Completed",
            "result_file": "/some/output.vrt",
        }

        self.assertEqual(TreePanel._config_fingerprint(attrs), {"analysis_mode": "use_nighttime_lights"})

    def test_a_key_absent_fingerprints_the_same_as_present_with_an_empty_value(self):
        absent = {"analysis_mode": "use_nighttime_lights"}
        present_but_empty = {"analysis_mode": "use_nighttime_lights", "mask_mode": "None"}

        self.assertEqual(TreePanel._config_fingerprint(absent), TreePanel._config_fingerprint(present_but_empty))

    def test_a_real_value_change_is_not_masked(self):
        before = {"analysis_mode": "use_nighttime_lights", "mask_mode": "None"}
        after = {"analysis_mode": "use_nighttime_lights", "mask_mode": "point"}

        self.assertNotEqual(TreePanel._config_fingerprint(before), TreePanel._config_fingerprint(after))


class TestInvalidateIfConfigChanged(unittest.TestCase):
    def setUp(self):
        self.panel = MagicMock()
        _bind(self.panel, "_invalidate_if_config_changed", "_config_fingerprint")
        self.item = JsonTreeItem(
            ["Analysis", "Configured", 1.0, {"analysis_mode": "use_nighttime_lights", "mask_mode": "None"}],
            role="analysis",
        )

    def test_no_change_does_not_clear_or_invalidate(self):
        previous = {"analysis_mode": "use_nighttime_lights", "mask_mode": "None"}

        TreePanel._invalidate_if_config_changed(self.panel, self.item, previous)

        self.panel._clear_single_item_outputs.assert_not_called()

    def test_a_changed_field_clears_and_invalidates_ancestors(self):
        previous = {"analysis_mode": "use_nighttime_lights", "mask_mode": "None"}
        self.item.attributes()["mask_mode"] = "point"

        TreePanel._invalidate_if_config_changed(self.panel, self.item, previous)

        self.panel._clear_single_item_outputs.assert_called_once_with(self.item)


class TestEditAggregationDialogsInvalidateOnChange(unittest.TestCase):
    def setUp(self):
        self.panel = MagicMock()
        _bind(
            self.panel,
            "edit_analysis_aggregation",
            "edit_dimension_aggregation",
            "edit_factor_aggregation",
            "_invalidate_if_config_changed",
            "_config_fingerprint",
        )

    def test_analysis_dialog_changing_mask_mode_invalidates(self):
        analysis_item = JsonTreeItem(
            ["Analysis", "Configured", 1.0, {"mask_mode": "None"}],
            role="analysis",
        )
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = True
        mock_dialog.saveWeightingsToModel.side_effect = lambda: analysis_item.attributes().update(
            {"mask_mode": "point"}
        )

        with patch("geest.gui.panels.tree_panel.AnalysisAggregationDialog", return_value=mock_dialog):
            TreePanel.edit_analysis_aggregation(self.panel, analysis_item)

        self.panel._clear_single_item_outputs.assert_called_once_with(analysis_item)

    def test_analysis_dialog_with_no_real_change_does_not_invalidate(self):
        analysis_item = JsonTreeItem(
            ["Analysis", "Configured", 1.0, {"mask_mode": "None"}],
            role="analysis",
        )
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = True
        # Simulates a dialog that unconditionally rewrites the same value
        # on every OK click (e.g. a radio button that was already checked).
        mock_dialog.saveWeightingsToModel.side_effect = lambda: analysis_item.attributes().update({"mask_mode": "None"})

        with patch("geest.gui.panels.tree_panel.AnalysisAggregationDialog", return_value=mock_dialog):
            TreePanel.edit_analysis_aggregation(self.panel, analysis_item)

        self.panel._clear_single_item_outputs.assert_not_called()

    def test_dimension_dialog_weighting_only_change_does_not_invalidate(self):
        dimension_item = JsonTreeItem(
            ["Dim", "Configured", 1.0, {"id": "dim", "analysis_weighting": 1.0}],
            role="dimension",
        )
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = True
        # A weighting-only dialog still touches factor_weighting/
        # dimension_weighting on its children, never on the dimension's
        # own attributes - nothing here should ever look "changed".
        mock_dialog.saveWeightingsToModel.side_effect = lambda: None

        with patch("geest.gui.panels.tree_panel.DimensionAggregationDialog", return_value=mock_dialog):
            TreePanel.edit_dimension_aggregation(self.panel, dimension_item)

        self.panel._clear_single_item_outputs.assert_not_called()

    def test_factor_dialog_clears_and_invalidates_each_changed_indicator(self):
        factor_item = JsonTreeItem(["Factor", "Configured", 1.0, {"id": "fac"}], role="factor")
        indicator = JsonTreeItem(
            ["Indicator", "Configured", 1.0, {"id": "ind", "analysis_mode": "use_nighttime_lights"}],
            role="indicator",
            parent=factor_item,
        )
        factor_item.appendChild(indicator)
        factor_item.getItemByGuid = MagicMock(return_value=indicator)
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = True
        mock_dialog.changed_indicator_guids = [indicator.guid]

        with patch("geest.gui.panels.tree_panel.FactorAggregationDialog", return_value=mock_dialog):
            TreePanel.edit_factor_aggregation(self.panel, factor_item)

        self.panel._clear_single_item_outputs.assert_called_once_with(indicator)

    def test_factor_dialog_with_no_changed_indicators_invalidates_nothing(self):
        factor_item = JsonTreeItem(["Factor", "Configured", 1.0, {"id": "fac"}], role="factor")
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = True
        mock_dialog.changed_indicator_guids = []

        with patch("geest.gui.panels.tree_panel.FactorAggregationDialog", return_value=mock_dialog):
            TreePanel.edit_factor_aggregation(self.panel, factor_item)

        self.panel._clear_single_item_outputs.assert_not_called()


if __name__ == "__main__":
    unittest.main()

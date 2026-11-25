# -*- coding: utf-8 -*-
"""End-to-end reproduction of a real-world field report (worldbank/GeoE3,
2026-11-25): a Nigeria Regional analysis run left one indicator
("Location of primary schools") in "Workflow failed" status because no
point layer was set for it - but its parent factor ("Women's Travel
Patterns"), grandparent dimension ("Accessibility") and the top-level
analysis all showed "Completed successfully" regardless, with the
factor's own `error` attribute carrying a diagnostic message nobody
would ever see since the status icon next to it looked exactly like
every other successfully-completed row.

Drives the real production code (WorkflowQueueManager, real
ContextualIndexScoreWorkflow/FactorAggregationWorkflow classes) against
a real study_area.gpkg, following the same pattern as
test_contextual_dimension_clear_edit_run_e2e.py.
"""
import os
import shutil
import tempfile
import types
import unittest
from unittest.mock import MagicMock

from qgis.PyQt.QtCore import QSettings

from geest.core import JsonTreeItem
from geest.core.workflow_queue_manager import WorkflowQueueManager
from geest.gui.panels.tree_panel import TreePanel

FIXTURE_STUDY_AREA = os.path.join(os.path.dirname(__file__), "test_data", "wee_score", "study_area")


def build_tree_with_one_broken_sibling():
    """analysis -> dimension -> one factor -> [broken indicator, healthy indicator]."""
    analysis = JsonTreeItem(
        ["Analysis", "Configured", 1.0, {"id": "analysis_1", "analysis_scale": "regional"}],
        role="analysis",
        parent=None,
    )
    dimension = JsonTreeItem(
        [
            "Accessibility",
            "Configured",
            1.0,
            {"id": "accessibility", "analysis_weighting": 1.0, "default_analysis_weighting": 1.0},
        ],
        role="dimension",
        parent=analysis,
    )
    analysis.appendChild(dimension)
    factor = JsonTreeItem(
        [
            "Women's Travel Patterns",
            "Configured",
            1.0,
            {
                "id": "womens_travel_patterns",
                "dimension_weighting": 1.0,
                "default_dimension_weighting": 1.0,
            },
        ],
        role="factor",
        parent=dimension,
    )
    dimension.appendChild(factor)

    broken = JsonTreeItem(
        [
            "Location of primary schools",
            "Configured",
            1.0,
            {
                "id": "Primary_School_Location",
                "analysis_mode": "use_multi_buffer_point",
                "factor_weighting": 0.5,
                "default_factor_weighting": 0.5,
                "result": "Not Run",
                # Deliberately no multi_buffer_point_shapefile/_layer_source -
                # the exact real-world misconfiguration.
            },
        ],
        role="indicator",
        parent=factor,
    )
    factor.appendChild(broken)

    healthy = JsonTreeItem(
        [
            "Location of groceries",
            "Configured",
            1.0,
            {
                "id": "Groceries_Location",
                "analysis_mode": "use_contextual_index_score",
                "factor_weighting": 0.5,
                "default_factor_weighting": 0.5,
                "result": "Not Run",
                "index_score": 80,
            },
        ],
        role="indicator",
        parent=factor,
    )
    factor.appendChild(healthy)

    return analysis, dimension, factor, broken, healthy


class TestFactorAggregationErrorCascade(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_factor_error_cascade_")
        self.working_directory = os.path.join(self.temp_dir, "project")
        shutil.copytree(FIXTURE_STUDY_AREA, os.path.join(self.working_directory, "study_area"))
        QSettings().setValue("last_working_directory", self.working_directory)

        self.analysis, self.dimension, self.factor, self.broken, self.healthy = build_tree_with_one_broken_sibling()

        try:
            from processing.core.Processing import Processing

            Processing.initialize()
        except Exception:  # nosec B110 — already initialized or unavailable
            pass

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_panel(self):
        panel = MagicMock()
        panel.model.get_analysis_item.return_value = self.analysis
        panel.model.rootItem = self.analysis
        panel.working_directory = self.working_directory
        panel.run_only_incomplete = False
        panel.queue_manager = WorkflowQueueManager(pool_size=1)
        panel.road_network_layer_path = MagicMock(return_value="")
        panel.ghsl_layer_path = MagicMock(return_value="")
        panel.cell_size_m = MagicMock(return_value=1000.0)
        panel.analysis_scale = MagicMock(return_value="regional")
        panel.queue_workflow_task = types.MethodType(TreePanel.queue_workflow_task, panel)
        return panel

    def _run_stage(self, panel, workflow_type):
        TreePanel.start_workflows(panel, workflow_type=workflow_type)
        panel.queue_manager.start_processing_in_foreground()
        panel.queue_manager.workflow_queue.job_queue.clear()

    def test_a_failed_indicator_is_not_reported_as_completed_by_its_ancestors(self):
        panel = self._make_panel()
        panel.workflow_scope_item = self.dimension
        self._run_stage(panel, "indicators")
        self._run_stage(panel, "factors")
        self._run_stage(panel, "dimensions")

        self.assertEqual(self.broken.getStatus(), "Workflow failed")
        self.assertEqual(self.healthy.getStatus(), "Completed successfully")

        for ancestor, label in (
            (self.factor, "factor"),
            (self.dimension, "dimension"),
            (self.analysis, "analysis"),
        ):
            self.assertNotEqual(
                ancestor.getStatus(),
                "Completed successfully",
                f"the {label} has a failed descendant but reported itself as fully completed",
            )


if __name__ == "__main__":
    unittest.main()

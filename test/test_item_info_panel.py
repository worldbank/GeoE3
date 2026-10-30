# -*- coding: utf-8 -*-
"""Tests for ItemInfoPanel - the collapsible "what is this tree item"
panel shown above the tree panel's button row, with a slide-over to
the methodology behind an indicator's score. Replaces the old
map-canvas overlay (LayerDescriptionItem, removed).
"""
import unittest
from unittest.mock import MagicMock

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QLabel, QProgressBar, QTextEdit

from geest.core.reports.methodology import TECHNIQUES
from geest.gui.widgets.item_info_panel import ItemInfoPanel
from geest.utilities import resources_path


def make_fake_item(
    role,
    name,
    description="",
    analysis_mode="",
    tooltip="",
    item_id="",
    parent=None,
    women_considerations_enabled=True,
):
    """A duck-typed stand-in for JsonTreeItem carrying only what
    ItemInfoPanel.show_item() actually reads.
    """
    item = MagicMock()
    item.role = role
    item.data.return_value = name
    item.getIcon.return_value = QIcon()
    item.getItemTooltip.return_value = tooltip
    item.parentItem = parent
    attrs = {
        "description": description,
        "analysis_mode": analysis_mode,
        "id": item_id,
        "women_considerations_enabled": women_considerations_enabled,
    }
    item.attribute.side_effect = lambda key, default="": attrs.get(key, default)
    return item


class TestItemInfoPanelShowItem(unittest.TestCase):
    def setUp(self):
        self.panel = ItemInfoPanel()
        # isVisible() reflects the whole ancestor chain, not just this
        # widget's own setVisible() flag - without an actual show(), every
        # child reports isVisible() == False regardless of its own state.
        self.panel.show()

    def test_clear_shows_placeholder(self):
        self.panel.clear()

        self.assertEqual(self.panel.item_heading_label.text(), "No item selected")
        self.assertFalse(self.panel.more_link.isVisible())
        self.assertEqual(self.panel.stack.currentIndex(), 0)

    def test_show_item_sets_heading_and_combined_meta_line(self):
        item = make_fake_item("dimension", "Accessibility", description="How easy it is to reach services.")

        self.panel.show_item(item)

        self.assertEqual(self.panel.item_heading_label.text(), "Accessibility")
        self.assertEqual(self.panel.item_meta_label.toPlainText(), "Dimension · How easy it is to reach services.")

    def test_indicator_with_no_description_borrows_its_parent_factors(self):
        # model.json leaves almost every indicator's own "description"
        # blank, while the parent factor's is always populated with real
        # prose - that's a far more useful fallback than the bare word
        # "Indicator" or a transient run warning/error.
        factor = make_fake_item("factor", "Women's Travel Patterns", description="Multi-stop caregiving trips.")
        item = make_fake_item("indicator", "Location of Kindergartens/Childcare", description="", parent=factor)

        self.panel.show_item(item)

        self.assertEqual(self.panel.item_meta_label.toPlainText(), "Indicator · Multi-stop caregiving trips.")

    def test_long_borrowed_description_is_shown_in_full_not_truncated(self):
        # Character-count truncation always left a reader hanging mid-
        # sentence with no way to see the rest. The full description goes
        # in regardless of length - item_meta_label is a scrollable text
        # area (see test_meta_label_is_a_scrollable_read_only_text_area),
        # so whatever doesn't fit the card's fixed height is a scroll
        # away rather than cut off with an ellipsis.
        long_description = (
            "Women's Travel Patterns (WTP) refer to the unique travel behaviors of "
            "women, often involving multiple stops for household or caregiving "
            "tasks, making proximity to essential services like markets, "
            "supermarkets, childcare centers, primary schools, pharmacies, and "
            "green spaces crucial. It also accounts for safety perceptions, "
            "time-of-day constraints, and the extra planning burden these "
            "combined trips place on women's daily schedules and available "
            "leisure or rest time."
        )
        factor = make_fake_item("factor", "Women's Travel Patterns", description=long_description)
        item = make_fake_item("indicator", "Location of Groceries", description="", parent=factor)

        self.panel.show_item(item)

        self.assertEqual(self.panel.item_meta_label.toPlainText(), f"Indicator · {long_description}")

    def test_meta_label_is_a_scrollable_read_only_text_area(self):
        self.assertIsInstance(self.panel.item_meta_label, QTextEdit)
        self.assertTrue(self.panel.item_meta_label.isReadOnly())
        self.assertEqual(
            self.panel.item_meta_label.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.assertEqual(
            self.panel.item_meta_label.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )

    def test_item_with_no_description_and_no_parent_description_shows_bare_role(self):
        item = make_fake_item("dimension", "Accessibility", description="", parent=None)

        self.panel.show_item(item)

        self.assertEqual(self.panel.item_meta_label.toPlainText(), "Dimension")

    def test_analysis_item_with_no_description_gets_the_womens_empowerment_default(self):
        # model.json never carries a real "description" for the Analysis
        # item itself - treeview.py used to default it to the literal
        # string "No Description", which then got persisted to disk and
        # displayed verbatim ("Analysis · No Description"). It should
        # show real, context-aware copy instead.
        item = make_fake_item("analysis", "Analysis", description="", women_considerations_enabled=True)

        self.panel.show_item(item)

        self.assertEqual(
            self.panel.item_meta_label.toPlainText(),
            "Analysis · The overall GeoE3 score combines the Contextual, Accessibility, and Place "
            "Characterization dimensions into a single measure of how enabling the "
            "environment is for women's economic empowerment in this study area.",
        )

    def test_analysis_item_uses_the_generic_default_when_womens_considerations_disabled(self):
        item = make_fake_item("analysis", "Analysis", description="", women_considerations_enabled=False)

        self.panel.show_item(item)

        self.assertEqual(
            self.panel.item_meta_label.toPlainText(),
            "Analysis · The overall GeoE3 score combines the Contextual, Accessibility, and Place "
            "Characterization dimensions into a single measure of how enabling the "
            "environment is for employment and entrepreneurship in this study area.",
        )

    def test_analysis_item_with_a_real_description_keeps_it(self):
        item = make_fake_item("analysis", "Analysis", description="A custom description someone typed in.")

        self.panel.show_item(item)

        self.assertEqual(self.panel.item_meta_label.toPlainText(), "Analysis · A custom description someone typed in.")

    def test_analysis_item_with_the_legacy_persisted_placeholder_gets_the_default_too(self):
        # Every project saved before the "No Description" default was
        # fixed in treeview.py has that literal string baked into its
        # model.json on disk - confirmed live against StLuciaH3 and
        # every other real project in data/GeestWorkingDirectory. It
        # must be treated the same as a genuinely empty description,
        # not displayed verbatim.
        item = make_fake_item("analysis", "Analysis", description="No Description", women_considerations_enabled=True)

        self.panel.show_item(item)

        self.assertEqual(
            self.panel.item_meta_label.toPlainText(),
            "Analysis · The overall GeoE3 score combines the Contextual, Accessibility, and Place "
            "Characterization dimensions into a single measure of how enabling the "
            "environment is for women's economic empowerment in this study area.",
        )

    def test_run_warning_text_is_never_shown_as_the_description(self):
        # getItemTooltip() can surface a transient run warning/error (e.g.
        # "No service areas could be computed...") - that belongs on the
        # tree row's own hover tooltip (treeview.py), not in this panel,
        # where it would be mistaken for a description of the indicator.
        item = make_fake_item(
            "indicator",
            "Location of Pharmacies",
            description="",
            tooltip="Warning: No service areas could be computed for this indicator.",
        )

        self.panel.show_item(item)

        self.assertNotIn("Warning", self.panel.item_meta_label.toPlainText())
        self.assertEqual(self.panel.item_meta_label.toPlainText(), "Indicator")

    def test_methodology_link_hidden_for_items_without_a_technique(self):
        item = make_fake_item("dimension", "Accessibility")

        self.panel.show_item(item)

        self.assertFalse(self.panel.more_link.isVisible())

    def test_methodology_link_shown_for_indicator_with_a_known_technique(self):
        item = make_fake_item("indicator", "Clinics nearby", analysis_mode="use_point_per_cell")

        self.panel.show_item(item)

        self.assertTrue(self.panel.more_link.isVisible())

    def test_methodology_link_hidden_for_unmapped_analysis_mode(self):
        item = make_fake_item("indicator", "Total score", analysis_mode="factor_aggregation")

        self.panel.show_item(item)

        self.assertFalse(self.panel.more_link.isVisible())

    def test_icon_label_is_a_square_tile(self):
        self.assertEqual(self.panel.item_icon_label.objectName(), "iconTile")
        self.assertEqual(self.panel.item_icon_label.size().width(), 36)
        self.assertEqual(self.panel.item_icon_label.size().height(), 36)

    def test_mapped_id_uses_the_topic_icon_not_the_generic_role_glyph(self):
        item = make_fake_item("factor", "EPLEX Score", item_id="eplex")

        self.panel.show_item(item)

        self.assertFalse(self.panel.item_icon_label.pixmap().isNull())

    def test_unmapped_id_falls_back_to_the_generic_role_icon(self):
        generic_icon = QIcon(resources_path("resources", "icons", "factor.svg"))
        item = make_fake_item("factor", "Mystery Factor", item_id="not_a_real_id")
        item.getIcon.return_value = generic_icon

        self.panel.show_item(item)

        item.getIcon.assert_called()

    def test_showing_a_new_item_resets_to_the_item_page(self):
        item = make_fake_item("indicator", "Clinics nearby", analysis_mode="use_point_per_cell")
        self.panel.show_item(item)
        self.panel._show_methodology_page()
        self.assertEqual(self.panel.stack.currentIndex(), 1)

        self.panel.show_item(item)

        self.assertEqual(self.panel.stack.currentIndex(), 0)


class TestItemInfoPanelMethodologySlideOver(unittest.TestCase):
    def setUp(self):
        self.panel = ItemInfoPanel()
        # isVisible() reflects the whole ancestor chain, not just this
        # widget's own setVisible() flag - without an actual show(), every
        # child reports isVisible() == False regardless of its own state.
        self.panel.show()
        self.item = make_fake_item("indicator", "Clinics nearby", analysis_mode="use_point_per_cell")
        self.panel.show_item(self.item)

    def test_more_link_switches_to_methodology_page(self):
        self.panel.more_link.click()

        self.assertEqual(self.panel.stack.currentIndex(), 1)
        self.assertEqual(self.panel.methodology_heading_label.text(), "Counting What's Nearby")

    def test_header_label_returns_to_item_page(self):
        self.panel.more_link.click()

        self.panel.header_label.click()

        self.assertEqual(self.panel.stack.currentIndex(), 0)

    def test_header_label_becomes_a_back_link_on_the_methodology_page(self):
        # A single carousel-style nav slot rather than a separate in-card
        # back_link row: "Selected item" (inert) on the item page becomes
        # a clickable "← Selected item" on the methodology page.
        self.assertEqual(self.panel.header_label.text(), "Selected item")

        self.panel.more_link.click()

        self.assertEqual(self.panel.header_label.text(), "←  Selected item")

        self.panel.header_label.click()

        self.assertEqual(self.panel.header_label.text(), "Selected item")

    def test_more_link_lives_in_the_header_not_the_card(self):
        # Moved out of the card's text column so the card's fixed height
        # is spent entirely on the description, not shared with a link.
        self.assertIsNot(self.panel.more_link.parentWidget(), self.panel.card)
        self.assertFalse(self.panel.card.isAncestorOf(self.panel.more_link))

    def test_more_link_hides_while_on_the_methodology_page(self):
        self.assertTrue(self.panel.more_link.isVisible())

        self.panel.more_link.click()

        self.assertFalse(self.panel.more_link.isVisible())

    def test_more_link_reappears_after_returning_to_the_item_page(self):
        self.panel.more_link.click()

        self.panel.header_label.click()

        self.assertTrue(self.panel.more_link.isVisible())

    def test_methodology_icon_label_is_also_a_square_tile(self):
        self.assertEqual(self.panel.methodology_icon_label.objectName(), "iconTile")
        self.assertEqual(self.panel.methodology_icon_label.size().width(), 36)

    def test_methodology_body_shows_the_complete_technique_description(self):
        self.panel.more_link.click()

        expected = TECHNIQUES[self.panel._current_technique_key]["description"]
        self.assertEqual(self.panel.methodology_body_label.toPlainText(), expected)

    def test_methodology_body_is_a_scrollable_read_only_text_area(self):
        self.assertIsInstance(self.panel.methodology_body_label, QTextEdit)
        self.assertTrue(self.panel.methodology_body_label.isReadOnly())
        self.assertEqual(
            self.panel.methodology_body_label.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )


class TestItemInfoPanelScaleAwareMethodology(unittest.TestCase):
    """National-scale Active Transport scores a cell with a score-weighted
    average instead of the single-best-feature technique used everywhere
    else - the technique shown in the methodology slide-over has to track
    that, reading the project's analysis_scale off the root "analysis"
    tree item rather than the indicator's own analysis_mode alone.
    worldbank/GeoE3#397.
    """

    def setUp(self):
        self.panel = ItemInfoPanel()
        self.panel.show()

    def _make_analysis_parent(self, analysis_scale):
        analysis = make_fake_item("analysis", "Tunisia")
        attrs = {"description": "", "analysis_mode": "", "id": "", "analysis_scale": analysis_scale}
        analysis.attribute.side_effect = lambda key, default="": attrs.get(key, default)
        return analysis

    def test_national_scale_active_transport_uses_the_weighted_technique(self):
        analysis = self._make_analysis_parent("national")
        item = make_fake_item(
            "indicator",
            "Cycle network",
            analysis_mode="use_osm_transport_polyline_per_cell",
            parent=analysis,
        )

        self.panel.show_item(item)

        self.assertEqual(self.panel._current_technique_key, "weighted_feature_average")

    def test_regional_scale_active_transport_keeps_the_feature_count_technique(self):
        analysis = self._make_analysis_parent("regional")
        item = make_fake_item(
            "indicator",
            "Cycle network",
            analysis_mode="use_osm_transport_polyline_per_cell",
            parent=analysis,
        )

        self.panel.show_item(item)

        self.assertEqual(self.panel._current_technique_key, "feature_count")

    def test_no_analysis_ancestor_defaults_to_national_and_the_weighted_technique(self):
        # Mirrors TreePanel.analysis_scale()'s own "national" default.
        item = make_fake_item(
            "indicator",
            "Cycle network",
            analysis_mode="use_osm_transport_polyline_per_cell",
        )

        self.panel.show_item(item)

        self.assertEqual(self.panel._current_technique_key, "weighted_feature_average")

    def test_methodology_slide_over_shows_the_weighted_technique_name(self):
        analysis = self._make_analysis_parent("national")
        item = make_fake_item(
            "indicator",
            "Cycle network",
            analysis_mode="use_osm_transport_polyline_per_cell",
            parent=analysis,
        )
        self.panel.show_item(item)

        self.panel.more_link.click()

        self.assertEqual(self.panel.methodology_heading_label.text(), "A Score Weighted Toward the Best Infrastructure")
        self.assertEqual(
            self.panel.methodology_body_label.toPlainText(),
            TECHNIQUES["weighted_feature_average"]["description"],
        )


class TestItemInfoPanelCollapse(unittest.TestCase):
    def setUp(self):
        self.panel = ItemInfoPanel()
        # isVisible() reflects the whole ancestor chain, not just this
        # widget's own setVisible() flag - without an actual show(), every
        # child reports isVisible() == False regardless of its own state.
        self.panel.show()

    def test_starts_expanded(self):
        self.assertTrue(self.panel.card.isVisible())

    def test_card_has_room_for_more_than_a_couple_lines_of_description(self):
        # Grown from the original 112px cap so a borrowed factor
        # description has somewhere to go instead of being truncated
        # down to almost nothing.
        self.assertGreaterEqual(self.panel.card.maximumHeight(), 130)

    def test_toggle_collapses_the_card(self):
        self.panel.toggle_expanded()

        self.assertFalse(self.panel.card.isVisible())

    def test_toggle_twice_re_expands(self):
        self.panel.toggle_expanded()
        self.panel.toggle_expanded()

        self.assertTrue(self.panel.card.isVisible())

    def test_clicking_header_label_while_collapsed_re_expands(self):
        self.panel.toggle_expanded()

        self.panel.header_label.click()

        self.assertTrue(self.panel.card.isVisible())

    def test_clicking_more_link_while_collapsed_re_expands(self):
        item = make_fake_item("indicator", "Clinics nearby", analysis_mode="use_point_per_cell")
        self.panel.show_item(item)
        self.panel.toggle_expanded()

        self.panel.more_link.click()

        self.assertTrue(self.panel.card.isVisible())
        self.assertEqual(self.panel.stack.currentIndex(), 1)

    def test_clicking_the_header_bar_itself_while_collapsed_re_expands(self):
        self.panel.toggle_expanded()

        self.panel._expand_on_header_bar_click(None)

        self.assertTrue(self.panel.card.isVisible())

    def test_toggled_signal_emits_current_state(self):
        received = []
        self.panel.toggled.connect(received.append)

        self.panel.toggle_expanded()

        self.assertEqual(received, [False])


class TestItemInfoPanelProgress(unittest.TestCase):
    """show_progress()/hide_progress() - the panel takes over the same
    card space it uses for "what is this item" while a run (analysis,
    resource download, report export) is under way, since the two are
    mutually exclusive. tree_panel.py aliases its own
    overall_progress_bar/workflow_progress_bar/status_label onto the
    panel's (geest/gui/panels/tree_panel.py), so the ~30 existing
    setValue()/setFormat()/setVisible() call sites there keep working
    unchanged against the widgets built here.
    """

    def setUp(self):
        self.panel = ItemInfoPanel()
        # isVisible() reflects the whole ancestor chain, not just this
        # widget's own setVisible() flag - without an actual show(), every
        # child reports isVisible() == False regardless of its own state.
        self.panel.show()

    def test_show_progress_switches_to_the_progress_page(self):
        self.panel.show_progress()

        self.assertEqual(self.panel.stack.currentIndex(), 2)

    def test_show_progress_sets_the_header_title(self):
        self.panel.show_progress("Downloading resources...")

        self.assertEqual(self.panel.header_label.text(), "Downloading resources...")

    def test_show_progress_defaults_to_analysis_in_progress(self):
        self.panel.show_progress()

        self.assertEqual(self.panel.header_label.text(), "Analysis in progress...")

    def test_show_progress_hides_the_methodology_link(self):
        item = make_fake_item("indicator", "Clinics nearby", analysis_mode="use_point_per_cell")
        self.panel.show_item(item)
        self.assertTrue(self.panel.more_link.isVisible())

        self.panel.show_progress()

        self.assertFalse(self.panel.more_link.isVisible())

    def test_show_progress_re_expands_a_collapsed_panel(self):
        self.panel.toggle_expanded()
        self.assertFalse(self.panel.card.isVisible())

        self.panel.show_progress()

        self.assertTrue(self.panel.card.isVisible())

    def test_hide_progress_returns_to_the_item_page(self):
        self.panel.show_progress()

        self.panel.hide_progress()

        self.assertEqual(self.panel.stack.currentIndex(), 0)

    def test_progress_bars_and_status_label_are_the_same_widgets_tree_panel_updates(self):
        # tree_panel.py updates these via plain attribute access
        # (self.overall_progress_bar.setValue(...) etc.) after aliasing
        # them onto itself - this just confirms they exist with the
        # expected types on the panel for that aliasing to find.
        self.assertIsInstance(self.panel.overall_progress_bar, QProgressBar)
        self.assertIsInstance(self.panel.workflow_progress_bar, QProgressBar)
        self.assertIsInstance(self.panel.status_label, QLabel)

    def test_progress_values_reflect_on_the_bars(self):
        self.panel.show_progress()
        self.panel.overall_progress_bar.setMaximum(16)
        self.panel.overall_progress_bar.setValue(11)
        self.panel.status_label.setText("Processing area 11/16")

        self.assertEqual(self.panel.overall_progress_bar.value(), 11)
        self.assertEqual(self.panel.status_label.text(), "Processing area 11/16")

    def test_collapsing_and_re_expanding_during_a_run_returns_to_the_progress_page(self):
        self.panel.show_progress("Analysis in progress...")

        self.panel.toggle_expanded()
        self.panel.toggle_expanded()

        self.assertEqual(self.panel.stack.currentIndex(), 2)
        self.assertEqual(self.panel.header_label.text(), "Analysis in progress...")

    def test_collapsing_after_a_run_finishes_returns_to_the_item_page(self):
        self.panel.show_progress("Analysis in progress...")
        self.panel.hide_progress()

        self.panel.toggle_expanded()
        self.panel.toggle_expanded()

        self.assertEqual(self.panel.stack.currentIndex(), 0)

    def test_selecting_a_tree_item_mid_run_does_not_interrupt_the_progress_page(self):
        self.panel.show_progress("Analysis in progress...")
        item = make_fake_item("indicator", "Clinics nearby", analysis_mode="use_point_per_cell")

        self.panel.show_item(item)

        self.assertEqual(self.panel.stack.currentIndex(), 2)
        self.assertEqual(self.panel.header_label.text(), "Analysis in progress...")

    def test_clearing_the_selection_mid_run_does_not_interrupt_the_progress_page(self):
        self.panel.show_progress("Analysis in progress...")

        self.panel.clear()

        self.assertEqual(self.panel.stack.currentIndex(), 2)

    def test_header_label_click_does_nothing_while_a_run_is_active(self):
        self.panel.show_progress("Analysis in progress...")

        self.panel.header_label.click()

        self.assertEqual(self.panel.stack.currentIndex(), 2)
        self.assertEqual(self.panel.header_label.text(), "Analysis in progress...")

    def test_selected_item_before_the_run_is_shown_once_it_finishes(self):
        item = make_fake_item("indicator", "Clinics nearby", analysis_mode="use_point_per_cell")
        self.panel.show_item(item)
        self.panel.show_progress("Analysis in progress...")
        # Selecting something else mid-run still updates the content
        # underneath, ready for when the run finishes.
        other_item = make_fake_item("dimension", "Accessibility")
        self.panel.show_item(other_item)

        self.panel.hide_progress()

        self.assertEqual(self.panel.stack.currentIndex(), 0)
        self.assertEqual(self.panel.item_heading_label.text(), "Accessibility")


if __name__ == "__main__":
    unittest.main()

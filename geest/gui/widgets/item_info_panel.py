# -*- coding: utf-8 -*-
"""📦 Item info panel module.

A collapsible panel shown above the tree panel's button row, explaining
whatever tree item is currently selected: a heading, a scrollable
description and an icon. For an indicator, a "Methodology" link slides
over to a second page showing the real-world technique behind its
score - the same name, description and icon used on the analysis
report's own Methodology pages (geest/core/reports/methodology.py) -
so the explanation stays in sync with what gets published. A third
page takes over the same space while an analysis run, resource
download, or report export is under way (show_progress()/
hide_progress()), with the status text and the two progress bars that
used to live in the host panel's own button row.

Replaces the old `LayerDescriptionItem` map-canvas overlay, which had
been disabled since May 2026 and, per user feedback, wasn't the right
pattern anyway: a dock panel next to the controls the user is already
looking at beats a floating label on the map.
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from geest.core.reports.methodology import TECHNIQUES, technique_for_indicator
from geest.core.topic_icons import topic_icon_filename
from geest.gui.widgets.sparkline_chart import SparklineChart
from geest.utilities import resources_path

NAVY = "#002244"
CYAN = "#009FDA"
CHARCOAL = "#333333"
GREY = "#6E7B85"
MIST = "#EEF4F8"
RULE = "#D6DEE4"
ICON_TILE_BG = "#E3F3FB"


def _scrollable_text(object_name: str) -> QTextEdit:
    """A read-only text area that scrolls instead of eliding.

    Character-count truncation always leaves a reader hanging mid-
    sentence with no way to see the rest - this shows the complete text
    and lets the card's fixed height clip it behind a scrollbar instead,
    exactly like any other "more content than fits" panel.

    Args:
        object_name: QSS object name for styling (see the panel's
            stylesheet for the matching ``QTextEdit#<object_name>`` rule).

    Returns:
        A configured, empty QTextEdit ready to receive plain text.
    """
    widget = QTextEdit("")
    widget.setObjectName(object_name)
    widget.setReadOnly(True)
    widget.setFrameShape(QFrame.Shape.NoFrame)
    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    widget.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return widget


_ROLE_LABELS = {
    "dimension": "Dimension",
    "factor": "Factor",
    "indicator": "Indicator",
    "analysis": "Analysis",
}

#: treeview.py used to default a missing Analysis description to this
#: literal string and persist it to model.json - every project saved
#: before that was fixed still carries it on disk, so it's treated the
#: same as an empty description here rather than displayed verbatim.
_LEGACY_NO_DESCRIPTION_PLACEHOLDER = "No Description"


class ItemInfoPanel(QWidget):
    """Collapsible "what is this item" panel with a methodology slide-over."""

    #: Emitted whenever the user's expand/collapse choice changes, so the
    #: host layout can be told whether this widget just changed its own
    #: preferred height (there is nothing else to resize for).
    toggled = pyqtSignal(bool)

    #: Emitted with a stop's "key" (see geest.core.analysis_outputs) when
    #: the carousel lands on an available output the host should load into
    #: the canvas - never emitted for a stop marked unavailable, since
    #: there's nothing to load.
    outputChanged = pyqtSignal(str)

    #: Emitted when the user navigates onto the Sparkline page - the
    #: host responds with set_sparkline_data()/set_sparkline_unavailable().
    #: Carries the active carousel stop's "key" (see
    #: geest.core.analysis_outputs) for an "analysis" item, or "" for
    #: every other role (indicator/factor/dimension each have exactly
    #: one column, no stop to name). Not computed eagerly on every tree
    #: click: the underlying read (see geest.core.sparkline_data) is a
    #: real full-column SQLite scan, not an in-memory lookup, so it's
    #: only worth paying for when the page is actually opened.
    sparklineRequested = pyqtSignal(str)

    def __init__(self, parent=None):
        """🏗️ Initialize the instance.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self._expanded = True
        self._current_technique_key = None
        # Tracks whether a run is currently showing, independent of which
        # stack page happens to be visible right now - set_expanded(True)
        # consults this to re-force the progress page if a collapse/expand
        # (or anything else) slipped the stack back to the item page while
        # processing was still under way.
        self._progress_active = False
        self._progress_title = "Analysis in progress..."
        # The analysis-level output carousel (GeoE3 Score / by Population /
        # Aggregate / Masked / Job Opportunities Mask / GHSL Settlements) -
        # see set_analysis_outputs(). Empty for every other role.
        self._output_stops = []
        self._current_output_index = 0
        self._score_heading_text = ""
        self._score_meta_text = ""
        # Whether "next" from the current Item/Methodology page leads to a
        # Sparkline page - True for any indicator/factor/dimension (see
        # show_item()), or per-stop for "analysis" (see
        # _render_current_output(), ANALYSIS_OUTPUT_STOPS' "sparkline" key).
        self._sparkline_eligible = False
        # Which of Item(0)/Methodology(1)/Sparkline(3) the user last
        # explicitly navigated to, for indicator/factor/dimension items -
        # show_item() consults this so switching to another indicator
        # while viewing its Methodology/Sparkline page lands on the SAME
        # kind of page for the new one, instead of always resetting to
        # Item (confirmed live: expected to behave like a tab that stays
        # selected across rows, not a per-item default). Not consulted
        # for "analysis" items - set_analysis_outputs() always starts a
        # freshly-selected analysis node's own carousel at stop 0's Item
        # view by design, regardless of this.
        self._active_page = 0
        self._build_ui()
        self.clear()

    def _build_ui(self):
        """⚙️ Build the static widget structure (header + two stacked pages)."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.setStyleSheet(
            f"""
            QFrame#itemInfoCard {{
                background-color: {MIST};
                border: 1px solid {RULE};
                border-radius: 6px;
            }}
            QToolButton#collapseToggle {{
                border: none;
                color: {GREY};
                font-weight: bold;
            }}
            QLabel#headingLabel {{
                color: {NAVY};
                font-weight: bold;
                font-size: 11pt;
            }}
            QTextEdit#bodyLabel {{
                color: {CHARCOAL};
                font-size: 9pt;
                background: transparent;
                border: none;
            }}
            QTextEdit#metaLabel {{
                color: {GREY};
                font-size: 8.5pt;
                background: transparent;
                border: none;
            }}
            QToolButton#moreLink {{
                border: none;
                color: {CYAN};
                font-weight: bold;
                font-size: 9pt;
            }}
            QToolButton#headerNav {{
                border: none;
                background: transparent;
                font-weight: bold;
                font-size: 8pt;
            }}
            QLabel#iconTile {{
                background-color: {ICON_TILE_BG};
                border: 1px solid {RULE};
                border-radius: 8px;
            }}
            QLabel#statusLabel {{
                color: {GREY};
                font-style: italic;
                font-size: 9pt;
            }}
            """
        )

        header = QWidget()
        # Clicking anywhere on the bar itself (not a child button, which
        # handles its own clicks) re-expands a collapsed panel, same as
        # clicking the chevron would - a collapsed title bar shouldn't be
        # a dead end just because the click landed between the label and
        # the chevron rather than on either of them.
        header.mousePressEvent = self._expand_on_header_bar_click
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(6, 2, 6, 2)
        # A single carousel-style nav slot rather than a static label: it
        # reads "Selected item" on the item page, and becomes a clickable
        # "← Selected item" back-link on the methodology page - replacing
        # what used to be a separate back_link row inside the card, which
        # freed another line of the card's fixed height for content.
        self.header_label = QToolButton()
        self.header_label.setObjectName("headerNav")
        self.header_label.clicked.connect(self._on_header_label_clicked)
        header_layout.addWidget(self.header_label)
        header_layout.addStretch(1)
        # Lives in the header rather than inside the card's text column -
        # freeing up a whole line of the card's fixed height for the
        # description, which was otherwise the first thing truncated.
        self.more_link = QToolButton()
        self.more_link.setObjectName("moreLink")
        self.more_link.setText("Methodology  →")
        self.more_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_link.clicked.connect(self._on_more_link_clicked)
        self.more_link.setVisible(False)
        header_layout.addWidget(self.more_link)
        self.collapse_button = QToolButton()
        self.collapse_button.setObjectName("collapseToggle")
        self.collapse_button.setText("▾")
        self.collapse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.collapse_button.clicked.connect(self.toggle_expanded)
        header_layout.addWidget(self.collapse_button)
        outer.addWidget(header)

        self.card = QFrame()
        self.card.setObjectName("itemInfoCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(8, 6, 8, 8)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_item_page())
        self.stack.addWidget(self._build_methodology_page())
        self.stack.addWidget(self._build_progress_page())
        self.stack.addWidget(self._build_sparkline_page())
        card_layout.addWidget(self.stack)

        outer.addWidget(self.card)
        self.card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # A fixed cap, not just a Fixed size policy: without this the card
        # still happily grows to fill whatever room the host layout hands
        # it (Fixed only stops it growing to match its OWN size hint, not
        # the hint of an empty/short-content hint being stretched by a
        # parent that has nothing else competing for that space).
        self.card.setMaximumHeight(140)

    def _build_item_page(self) -> QWidget:
        """⚙️ Build the "currently selected item" page.

        Returns:
            The page widget.
        """
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)

        self.item_icon_label = QLabel()
        self.item_icon_label.setObjectName("iconTile")
        self.item_icon_label.setFixedSize(36, 36)
        self.item_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.item_icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        self.item_heading_label = QLabel("")
        self.item_heading_label.setObjectName("headingLabel")
        self.item_heading_label.setWordWrap(True)
        text_col.addWidget(self.item_heading_label)

        # One combined "Role · description" line instead of two separate
        # labels - a bare item with no custom description has nothing to
        # say beyond its own role, so showing the role twice (once as a
        # badge, once as getItemTooltip()'s "Indicator"/"Factor"/...
        # fallback body text) was pure redundant clutter. Scrollable
        # rather than truncated: fills whatever space is left under the
        # heading and scrolls for the rest, instead of eliding text the
        # reader has no way to finish reading.
        self.item_meta_label = _scrollable_text("metaLabel")
        text_col.addWidget(self.item_meta_label, 1)

        row.addLayout(text_col, 1)
        return page

    def _build_methodology_page(self) -> QWidget:
        """⚙️ Build the methodology slide-over page.

        Returns:
            The page widget.
        """
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        row = QHBoxLayout()
        self.methodology_icon_label = QLabel()
        self.methodology_icon_label.setObjectName("iconTile")
        self.methodology_icon_label.setFixedSize(36, 36)
        self.methodology_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.methodology_icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        self.methodology_heading_label = QLabel("")
        self.methodology_heading_label.setObjectName("headingLabel")
        self.methodology_heading_label.setWordWrap(True)
        text_col.addWidget(self.methodology_heading_label)

        self.methodology_body_label = _scrollable_text("bodyLabel")
        text_col.addWidget(self.methodology_body_label, 1)

        row.addLayout(text_col, 1)
        outer.addLayout(row, 1)
        return page

    def _build_sparkline_page(self) -> QWidget:
        """⚙️ Build the score-distribution Sparkline page.

        Returns:
            The page widget.
        """
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self.sparkline_heading_label = QLabel("Score Distribution")
        self.sparkline_heading_label.setObjectName("headingLabel")
        outer.addWidget(self.sparkline_heading_label)

        self.sparkline_chart = SparklineChart()
        outer.addWidget(self.sparkline_chart)

        self.sparkline_caption_label = QLabel("")
        self.sparkline_caption_label.setObjectName("statusLabel")
        self.sparkline_caption_label.setWordWrap(True)
        outer.addWidget(self.sparkline_caption_label)

        outer.addStretch(1)
        return page

    def _build_progress_page(self) -> QWidget:
        """⚙️ Build the "a run is in progress" page: status text and
        the two progress bars (overall item count, current task) shown
        while an analysis run, resource download, or report export is
        under way. Lives here rather than in the host panel's own
        layout so it can share the card's space with "what is this
        item" - the two are mutually exclusive, never shown at once.

        Returns:
            The page widget.
        """
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setFormat("Overall Progress: %p%")
        self.overall_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overall_progress_bar.setFixedHeight(20)
        outer.addWidget(self.overall_progress_bar)

        self.workflow_progress_bar = QProgressBar()
        self.workflow_progress_bar.setRange(0, 100)
        self.workflow_progress_bar.setValue(0)
        self.workflow_progress_bar.setFormat("Task Progress: %p%")
        self.workflow_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.workflow_progress_bar.setFixedHeight(20)
        outer.addWidget(self.workflow_progress_bar)

        outer.addStretch(1)
        return page

    def toggle_expanded(self):
        """⚙️ Toggle between expanded and collapsed."""
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool):
        """⚙️ Show or hide the card, keeping only the slim header visible when collapsed.

        Re-expanding while a run is in progress always lands back on the
        progress page, regardless of what the stack happened to be
        showing - minimising the panel mid-run and expanding it again
        should return to "what's running", not silently drop back to
        "what's selected" just because the panel was collapsed for a
        moment.

        Args:
            expanded: Whether the card should be visible.
        """
        self._expanded = expanded
        if expanded and self._progress_active:
            self._set_header_as_progress(self._progress_title)
            self.stack.setCurrentIndex(2)
        self.card.setVisible(expanded)
        self.collapse_button.setText("▾" if expanded else "▸")
        self.toggled.emit(expanded)

    def _expand_on_header_bar_click(self, _event):
        """⚙️ Re-expand a collapsed panel when the header bar itself is clicked.

        Args:
            _event: The QMouseEvent (unused - any click on the bar's own
                background, as opposed to a child button, counts).
        """
        if not self._expanded:
            self.set_expanded(True)

    def _on_header_label_clicked(self):
        """⚙️ "Previous" control: expand first, then step back.

        Doubles as the analysis-output carousel's "previous" button
        whenever one is active (see set_analysis_outputs()) - otherwise
        it's the indicator/methodology/Sparkline "go back" link, a no-op
        while a run is in progress (the header reads a status title
        then, not "← Selected item", so there's nothing to navigate
        back to until the run finishes).
        """
        if not self._expanded:
            self.set_expanded(True)
        if self._output_stops:
            if self.stack.currentIndex() == 3:
                # Back from this stop's Sparkline page returns to the
                # SAME stop's Item view, not the previous stop - one
                # step back undoes one step forward (see
                # _on_more_link_clicked()'s matching branch).
                self._render_current_output()
            else:
                self._advance_output(-1)
            return
        if self._progress_active:
            return
        if self.stack.currentIndex() == 3 and self._current_technique_key is not None:
            # Back from Sparkline is one step, same as everywhere else
            # in this chain - to Methodology when there is one, not a
            # skip straight to Item (confirmed live: it's a carousel,
            # "←" should undo the last "→", not jump home).
            self._show_methodology_page()
            return
        self._show_item_page()

    def _on_more_link_clicked(self):
        """⚙️ "Next" control: expand first, then step forward.

        Doubles as the analysis-output carousel's "next" button whenever
        one is active (see set_analysis_outputs()) - otherwise it's the
        indicator/methodology "Methodology →" link, then (for any role)
        the "Sparkline →" link once there's nothing more specific left
        to show.
        """
        if not self._expanded:
            self.set_expanded(True)
        if self._output_stops:
            if self.stack.currentIndex() != 3 and self._sparkline_eligible:
                # "Next" from a stop's Item view shows THAT stop's own
                # Sparkline first, not the next stop - see
                # _render_current_output()'s docstring for why this
                # satisfies "the sparkline is for the active sub item".
                self._show_sparkline_page()
            else:
                self._advance_output(1)
            return
        current = self.stack.currentIndex()
        if current == 0 and self._current_technique_key is not None:
            self._show_methodology_page()
        elif current in (0, 1) and self._sparkline_eligible:
            self._show_sparkline_page()
        elif current == 3:
            # Sparkline is the last page in this chain - "next" wraps
            # the carousel back around to the Item page rather than
            # dead-ending (confirmed live: it's a carousel, there
            # should always be a "→" somewhere to go, even from the
            # last stop).
            self._show_item_page()

    def set_analysis_outputs(self, stops, current_index: int = 0) -> None:
        """⚙️ Show (or hide) the analysis-output carousel.

        Repurposes the header's existing "← Selected item"/"Methodology →"
        controls as the carousel's previous/next buttons - those are
        otherwise unused for an "analysis" role item (it never has a
        methodology technique of its own), so this never conflicts with
        the indicator/methodology navigation they normally drive.

        Args:
            stops: A list of stop dicts (see geest.core.analysis_outputs.
                ANALYSIS_OUTPUT_STOPS), each with an added "available"
                bool, or None/empty to hide the carousel - the caller is
                expected to pass this every time it calls show_item(),
                not just for "analysis" items, so a carousel left over
                from a previously selected item never lingers.
            current_index: Which stop to land on first.
        """
        self._output_stops = list(stops) if stops else []
        if not self._output_stops:
            self._current_output_index = 0
            # No more_link/header_label reset needed here: the caller
            # (TreePanel.on_item_clicked()) always calls show_item()
            # before this, and _show_item_page() already fully repaints
            # both controls (text, cursor, style, visibility) from
            # scratch every time it runs - carousel or not - so there's
            # nothing left over from a previous analysis-item visit to
            # undo. An unconditional re-paint here used to stomp back
            # over whatever show_item() had JUST correctly set for a
            # factor/dimension (e.g. "Sparkline  →"), always forcing it
            # to "Methodology  →" instead (confirmed live).
            return
        # Snapshot the text show_item() just painted for the real item, so
        # stop 0 ("score") can be restored to it later - including after
        # cycling away and back, when nothing else still has these
        # values lying around (see _render_current_output()). Text only,
        # not a QPixmap snapshot of the icon - a QLabel.pixmap() snapshot
        # segfaulted on the second visit to stop 0, once setPixmap() had
        # since been called again for other stops (confirmed live; same
        # class of bug as a GDAL Dataset being garbage-collected out from
        # under a Band it issued). Unlike the heading/description, the
        # icon never needs restoring anyway - an "analysis" item's icon
        # is always topics/geoe3_score.svg regardless of item id (see
        # topic_icons.py's ANALYSIS_ICON), the exact same file stop 0
        # already names, so just re-rendering it fresh like every other
        # stop (below) already reproduces it exactly.
        self._score_heading_text = self.item_heading_label.text()
        self._score_meta_text = self.item_meta_label.toPlainText()
        self._current_output_index = current_index % len(self._output_stops)
        self._render_current_output()

    def _advance_output(self, delta: int) -> None:
        """⚙️ Step the carousel by delta stops, wrapping at either end.

        Args:
            delta: +1 for "next", -1 for "previous".
        """
        self._current_output_index = (self._current_output_index + delta) % len(self._output_stops)
        self._render_current_output()
        stop = self._output_stops[self._current_output_index]
        if stop.get("available"):
            self.outputChanged.emit(stop["key"])

    def _render_current_output(self) -> None:
        """⚙️ Paint the item page + header for the carousel's current stop.

        Also returns the stack to this (Item) page - the one caller that
        needs that is "back" from this stop's own Sparkline page (see
        _on_header_label_clicked()); every other caller is already on
        this page, so it's a no-op for them.
        """
        self.stack.setCurrentIndex(0)
        self._active_page = 0
        stop = self._output_stops[self._current_output_index]
        self._sparkline_eligible = stop.get("sparkline", True)
        icon = QIcon(resources_path("resources", "icons", "topics", stop["icon"]))
        if not icon.isNull():
            self.item_icon_label.setPixmap(icon.pixmap(24, 24))
        else:
            self.item_icon_label.clear()

        # Stop 0 ("score") restores exactly what show_item() painted for
        # this analysis item when the carousel started - its real heading
        # (the item's own tree name, not a hardcoded "GeoE3 Score") and
        # its real description (a custom model.json one, or
        # _analysis_default_description()'s women's-empowerment-aware
        # copy) - rather than this stop's generic placeholder text, which
        # lost that real description (confirmed live). The snapshot (see
        # set_analysis_outputs()) is what makes this survive cycling away
        # to another stop and back, not just the very first render.
        if self._current_output_index == 0:
            self.item_heading_label.setText(self._score_heading_text)
            self.item_meta_label.setPlainText(self._score_meta_text)
        else:
            self.item_heading_label.setText(stop["label"])
            description = stop["description"]
            if not stop.get("available", True):
                description = f"{description}  —  not yet computed"
            self.item_meta_label.setPlainText(description)

        # Name the actual destination stop rather than a generic
        # "Previous"/"Next" - every other back/forward label in this
        # panel already names where it's going ("← Methodology",
        # "Selected item →", "← GeoE3 Score"), these two were the only
        # ones left that didn't (confirmed live, caught alongside the
        # Sparkline-page label bug this was investigated next to).
        previous_stop = self._output_stops[(self._current_output_index - 1) % len(self._output_stops)]
        self.header_label.setText(f"←  {previous_stop['label']}")
        self.header_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_label.setStyleSheet(f"color: {CYAN};")
        if self._sparkline_eligible:
            self.more_link.setText("Sparkline  →")
        else:
            next_stop = self._output_stops[(self._current_output_index + 1) % len(self._output_stops)]
            self.more_link.setText(f"{next_stop['label']}  →")
        self.more_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_link.setStyleSheet(f"color: {CYAN};")
        self.more_link.setVisible(True)

    def clear(self):
        """⚙️ Show a neutral placeholder when nothing is selected."""
        self._current_technique_key = None
        # Reset directly rather than via set_analysis_outputs(None) - this
        # is called from several places that don't also pair it with a
        # set_analysis_outputs() call, and a stale non-empty _output_stops
        # would make the next header_label/more_link click silently resume
        # carousel navigation instead of the (now-active) placeholder/
        # methodology behaviour those controls should have.
        self._output_stops = []
        self._current_output_index = 0
        self._sparkline_eligible = False
        self._active_page = 0
        self.item_icon_label.clear()
        self.item_heading_label.setText("No item selected")
        self.item_meta_label.setPlainText("Click a dimension, factor or indicator in the tree to see details here.")
        self.more_link.setVisible(False)
        # Same reasoning as show_item(): the tree's selection clearing
        # (e.g. the user clicking empty space) shouldn't interrupt a
        # progress display that's still showing a run in progress.
        if self._progress_active:
            return
        self._show_item_page()

    def _set_header_as_label(self):
        """⚙️ Passive carousel state: nothing to navigate back from."""
        self.header_label.setText("Selected item")
        self.header_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.header_label.setStyleSheet(f"color: {GREY};")

    def _set_header_as_back_link(self):
        """⚙️ Active carousel state: the "previous" control, back to the item page."""
        self.header_label.setText("←  Selected item")
        self.header_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_label.setStyleSheet(f"color: {CYAN};")

    def _set_header_as_sparkline_back_link(self, label: str):
        """⚙️ Active carousel state while on a stop's own Sparkline page: "back" names that stop, not a generic "Selected item".

        Args:
            label: The current carousel stop's own label (e.g. "GeoE3 Score").
        """
        self.header_label.setText(f"←  {label}")
        self.header_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_label.setStyleSheet(f"color: {CYAN};")

    def _set_header_as_progress(self, title: str):
        """⚙️ Non-interactive carousel state: a run is under way.

        Args:
            title: Header text while running.
        """
        self.header_label.setText(title)
        self.header_label.setCursor(Qt.CursorShape.ArrowCursor)
        self.header_label.setStyleSheet(f"color: {NAVY};")

    def show_progress(self, title: str = "Analysis in progress...") -> None:
        """⚙️ Switch to the progress page and make sure it's visible.

        Called when a run (analysis, resource download, report export)
        starts - the panel takes over the space it normally uses for
        "what is this item", since the two are mutually exclusive:
        there's nothing useful to explain about a selection while a
        run's progress is the more urgent thing on screen. Auto-expands
        a collapsed panel rather than updating progress somewhere the
        user can't see.

        Args:
            title: Header text while running - lets different run kinds
                (an analysis, a resource download) say what's actually
                happening instead of a generic "in progress".
        """
        self._progress_active = True
        self._progress_title = title
        self.more_link.setVisible(False)
        self._set_header_as_progress(title)
        self.set_expanded(True)
        self.stack.setCurrentIndex(2)

    def hide_progress(self) -> None:
        """⚙️ Return to the normal "selected item" page once a run finishes."""
        self._progress_active = False
        self._show_item_page()

    def _topic_icon(self, role: str, item_id: str):
        """⚙️ Load the topic-relevant icon for a role/id, or None if unmapped.

        Args:
            role: "analysis", "dimension", "factor" or "indicator".
            item_id: the item's ``id`` attribute.

        Returns:
            A QIcon, or None when no topic icon is mapped for this item.
        """
        filename = topic_icon_filename(role, item_id)
        if not filename:
            return None
        icon = QIcon(resources_path("resources", "icons", "topics", filename))
        return icon if not icon.isNull() else None

    def _analysis_default_description(self, item) -> str:
        """⚙️ Context-aware default description for the top-level Analysis node.

        model.json never carries a real "description" for the Analysis
        item itself (only dimensions/factors/indicators do), and the
        root item has no parent to borrow one from via
        _inherited_description() - so this fills in generic copy
        instead, chosen by women_considerations_enabled so it always
        matches the project's current mode rather than freezing in
        whatever was true the first time the project was loaded.

        Args:
            item: The JsonTreeItem the user just clicked.

        Returns:
            Women's-empowerment- or generic-mode description text.
        """
        women_considerations_enabled = (
            item.attribute("women_considerations_enabled", True) if hasattr(item, "attribute") else True
        )
        if women_considerations_enabled:
            return (
                "The overall GeoE3 score combines the Contextual, Accessibility, and Place "
                "Characterization dimensions into a single measure of how enabling the "
                "environment is for women's economic empowerment in this study area."
            )
        return (
            "The overall GeoE3 score combines the Contextual, Accessibility, and Place "
            "Characterization dimensions into a single measure of how enabling the "
            "environment is for employment and entrepreneurship in this study area."
        )

    def _inherited_description(self, item) -> str:
        """⚙️ Borrow a parent's description when the item has none of its own.

        model.json leaves most indicators' own "description" attribute
        blank, while their parent factor almost always carries a real,
        policy-reader-friendly sentence or two - that's a far more useful
        thing to show here than `getItemTooltip()`'s fallbacks, which can
        surface a transient run warning/error (not a description of what
        the indicator measures) or just the bare role name a second time.
        The tree row's own hover tooltip (treeview.py) still shows those
        warnings/errors - nothing is lost by leaving them out of this panel.

        Args:
            item: The JsonTreeItem the user just clicked.

        Returns:
            The nearest ancestor's description, or "" if none has one.
        """
        parent = getattr(item, "parentItem", None)
        if parent is not None and hasattr(parent, "attribute"):
            parent_description = parent.attribute("description", "")
            if parent_description:
                return parent_description
        return ""

    def _analysis_scale_for_item(self, item) -> str:
        """⚙️ Walk up to the root "analysis" item and read its analysis_scale.

        A handful of techniques (national-scale Active Transport) depend
        on the project's analysis_scale, not just the indicator's own
        analysis_mode - see geest.core.reports.methodology.
        technique_for_indicator(). Mirrors TreePanel.analysis_scale()'s
        own default.

        Args:
            item: Any JsonTreeItem in the tree.

        Returns:
            The project's analysis_scale ("national" if unset).
        """
        current = item
        seen = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if getattr(current, "role", "") == "analysis" and hasattr(current, "attribute"):
                return current.attribute("analysis_scale", "national")
            current = getattr(current, "parentItem", None)
        return "national"

    def show_item(self, item) -> None:
        """⚙️ Update the panel for the given tree item.

        Args:
            item: The JsonTreeItem the user just clicked.
        """
        role = getattr(item, "role", "")
        item_id = item.attribute("id", "") if hasattr(item, "attribute") else ""
        icon = self._topic_icon(role, item_id)
        if icon is None and hasattr(item, "getIcon"):
            icon = item.getIcon()
        if isinstance(icon, QIcon) and not icon.isNull():
            self.item_icon_label.setPixmap(icon.pixmap(24, 24))
        else:
            self.item_icon_label.clear()

        name = item.data(0) if hasattr(item, "data") else str(item)
        self.item_heading_label.setText(name or "")

        role_label = _ROLE_LABELS.get(role, role.title() if role else "")
        description = item.attribute("description", "") if hasattr(item, "attribute") else ""
        if description == _LEGACY_NO_DESCRIPTION_PLACEHOLDER:
            description = ""
        if not description and role == "analysis":
            description = self._analysis_default_description(item)
        if not description:
            description = self._inherited_description(item)
        # No truncation: a borrowed factor description can run well past
        # what the card's fixed height shows at once, but cutting it off
        # mid-sentence just leaves the reader hanging with no way to
        # finish it. The full text always goes in; item_meta_label is a
        # scrollable text area (see _scrollable_text()), so whatever
        # doesn't fit is a scroll away rather than lost.
        self.item_meta_label.setPlainText(f"{role_label} · {description}" if description else role_label)

        analysis_mode = item.attribute("analysis_mode", "") if hasattr(item, "attribute") else ""
        technique_key = (
            technique_for_indicator(analysis_mode, self._analysis_scale_for_item(item)) if analysis_mode else None
        )
        self._current_technique_key = technique_key
        # Every indicator/factor/dimension has an "id" and so a
        # study_area_grid column to build a Sparkline from (even if that
        # column turns out to have no scored cells yet - that's an empty
        # chart with a caption, not a missing page). "analysis" is
        # handled entirely through set_analysis_outputs()/
        # _render_current_output() instead, per-carousel-stop - not set
        # here, since this method runs before that one for an analysis
        # item (see TreePanel.on_item_clicked()).
        self._sparkline_eligible = role in ("indicator", "factor", "dimension")
        # Content above is still updated (ready for when hide_progress()
        # eventually calls _show_item_page()) but the stack itself stays
        # on the progress page while a run is active - selecting a
        # different tree item mid-run shouldn't silently replace the
        # progress display the user is actually watching.
        if self._progress_active:
            return
        # Land on the same KIND of page the user was already viewing for
        # the previous item - switching between indicators/factors/
        # dimensions while reading a Methodology or Sparkline page
        # should carry that choice over to the newly-selected item, not
        # silently reset to the plain Item page every time (confirmed
        # live - expected to behave like a tab that stays selected
        # across tree rows). Falls back gracefully when the new item
        # doesn't support the remembered page (e.g. was on Methodology,
        # new item is a factor/dimension with no technique of its own).
        # Not consulted for "analysis" - set_analysis_outputs() (called
        # right after this, see TreePanel.on_item_clicked()) always
        # starts a freshly-selected analysis node's own carousel at
        # stop 0's Item view by design, overriding whatever this picks.
        if self._active_page == 1 and technique_key is not None:
            self._show_methodology_page()
        elif self._active_page in (1, 3) and self._sparkline_eligible:
            self._show_sparkline_page()
        else:
            self._show_item_page()

    def _show_item_page(self):
        """⚙️ Switch the stack to the "selected item" page."""
        if self._current_technique_key is not None:
            self.more_link.setText("Methodology  →")
            self.more_link.setVisible(True)
        elif self._sparkline_eligible:
            self.more_link.setText("Sparkline  →")
            self.more_link.setVisible(True)
        else:
            self.more_link.setVisible(False)
        self.more_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_link.setStyleSheet(f"color: {CYAN};")
        self._set_header_as_label()
        self.stack.setCurrentIndex(0)
        self._active_page = 0

    def _show_methodology_page(self):
        """⚙️ Switch the stack to the methodology page for the current item."""
        if self._current_technique_key is None:
            return
        technique = TECHNIQUES[self._current_technique_key]
        icon = QIcon(resources_path("resources", "methodology", technique["svg"]))
        if not icon.isNull():
            self.methodology_icon_label.setPixmap(icon.pixmap(24, 24))
        self.methodology_heading_label.setText(technique["name"])
        # Full text, no truncation - see item_meta_label's own comment in
        # show_item(); methodology_body_label is the same kind of
        # scrollable text area (_scrollable_text()).
        self.methodology_body_label.setPlainText(technique["description"])
        # The header's Methodology link was for navigating TO this page -
        # replace it with "Sparkline →" (every indicator is sparkline-
        # eligible, see show_item()) now that we're here; the header
        # itself becomes the "go back" control instead (see
        # _set_header_as_back_link()).
        self.more_link.setText("Sparkline  →")
        self.more_link.setVisible(self._sparkline_eligible)
        self._set_header_as_back_link()
        self.stack.setCurrentIndex(1)
        self._active_page = 1

    def _show_sparkline_page(self) -> None:
        """⚙️ Switch to the Sparkline page and ask the host for its data.

        Emits sparklineRequested every time this page is entered rather
        than caching the last result - the host (TreePanel) is the one
        that knows whether the underlying data could have changed since
        the last visit (a re-run, a different carousel stop), and the
        read itself (geest.core.sparkline_data) is cheap enough for a
        single explicit "I just navigated here" trigger, unlike doing it
        on every tree click.
        """
        stop_key = ""
        if self._output_stops:
            # "Back" returns to this SAME stop's Item view; "next"
            # continues the outer carousel to the following stop
            # (_on_more_link_clicked()'s carousel branch already does
            # this once more_link is visible again) - a true circular
            # carousel, not a dead end.
            stop = self._output_stops[self._current_output_index]
            stop_key = stop["key"]
            self._set_header_as_sparkline_back_link(stop["label"])
            self.more_link.setText("Next  →")
        elif self._current_technique_key is not None:
            # "Back" undoes the last "→" (to Methodology, one step),
            # same one-step convention as everywhere else in this
            # chain; "next" wraps back around to Item.
            self._set_header_as_sparkline_back_link("Methodology")
            self.more_link.setText("Selected item  →")
        else:
            self._set_header_as_back_link()
            self.more_link.setText("Selected item  →")
        self.more_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_link.setStyleSheet(f"color: {CYAN};")
        self.more_link.setVisible(True)
        self.stack.setCurrentIndex(3)
        self._active_page = 3
        self.sparklineRequested.emit(stop_key)

    def set_sparkline_data(self, counts, colors, caption: str) -> None:
        """⚙️ Feed the Sparkline page's chart - called by the host in response to sparklineRequested.

        Args:
            counts: Bar heights, one per class (see geest.core.sparkline_data).
            colors: One hex colour per bar, same length/order as counts.
            caption: One-line caption shown under the chart (e.g. "61,616 grid cells scored").
        """
        self.sparkline_chart.set_data(counts, colors)
        self.sparkline_caption_label.setText(caption)

    def set_sparkline_unavailable(self, message: str) -> None:
        """⚙️ Show a message instead of a chart on the Sparkline page.

        Args:
            message: Why no chart is available (e.g. "No scored cells yet").
        """
        self.sparkline_chart.set_unavailable(message)
        self.sparkline_caption_label.setText("")

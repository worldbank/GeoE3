# -*- coding: utf-8 -*-
"""📦 Sparkline chart widget module.

Qt-native port of geest.core.reports.base_report.BaseReport.
_draw_sparkline() - same proportions (bottom-aligned bars, each bar's
height proportional to the tallest, a percentage label under each
non-empty bar) drawn with QPainter in a widget instead of
QgsLayoutItemShape/QgsLayoutItemLabel on a print-layout page. The
report and this widget both read/bin via geest.core.sparkline_data, so
the numbers themselves never differ between the two - only how they're
drawn.
"""

from typing import List, Optional

from qgis.PyQt.QtCore import QRectF, QSize, Qt
from qgis.PyQt.QtGui import QColor, QPainter
from qgis.PyQt.QtWidgets import QSizePolicy, QWidget

#: Matches item_info_panel.py's own GREY constant - percentage labels
#: and the "unavailable" message use the same secondary-text colour the
#: rest of this panel already uses for that purpose.
GREY = "#6E7B85"


class SparklineChart(QWidget):
    """A tiny bar chart: one flat-filled bar per class, bottom-aligned, sized relative to the tallest bar."""

    def __init__(self, parent=None):
        """🏗️ Initialize the instance.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self._counts: List[int] = []
        self._colors: List[str] = []
        self._show_percentages = True
        self._message: Optional[str] = None
        self.setMinimumSize(200, 48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, counts: List[int], colors: List[str], show_percentages: bool = True) -> None:
        """⚙️ Show one bar per (count, color) pair.

        Mirrors _draw_sparkline()'s own proportions exactly: bar height
        is each count's share of the tallest count (not of the total),
        and bars with a 0% share (rounds to zero, not literally empty)
        are left unlabelled to avoid a row of meaningless "0%"s on a
        long by-population chart, where most of the 15 classes are
        usually empty.

        Args:
            counts: Bar heights (e.g. value counts) - any non-negative
                numbers, same length/order as colors.
            colors: One hex colour per bar.
            show_percentages: Reserve a thin strip under the bars for
                each bar's share of the total, as "N%".
        """
        self._counts = list(counts)
        self._colors = list(colors)
        self._show_percentages = show_percentages
        self._message = None
        self.update()

    def set_unavailable(self, message: str) -> None:
        """⚙️ Show a centered message instead of bars.

        Args:
            message: Text to show in place of the chart (e.g. "Not
                available for this product").
        """
        self._counts = []
        self._colors = []
        self._message = message
        self.update()

    def sizeHint(self) -> QSize:
        """⚙️ Preferred size, sized for the item info panel's own 140px card-height cap.

        Returns:
            The preferred widget size.
        """
        return QSize(240, 60)

    def paintEvent(self, _event) -> None:
        """⚙️ Paint the bars (or the unavailable message) via QPainter.

        Args:
            _event: The QPaintEvent (unused - always repaints the whole widget).
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            rect = self.rect()

            if self._message:
                painter.setPen(QColor(GREY))
                painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap), self._message)
                return

            n = len(self._counts)
            if n == 0:
                return
            peak = max(self._counts)
            total = sum(self._counts)
            if peak <= 0:
                return

            gap = 3.0
            label_h = 14.0 if self._show_percentages else 0.0
            bar_area_h = rect.height() - label_h
            bar_w = (rect.width() - (n - 1) * gap) / n

            font = painter.font()
            font.setPointSizeF(7.5)
            painter.setFont(font)

            for index, (value, color) in enumerate(zip(self._counts, self._colors)):
                bar_x = rect.x() + index * (bar_w + gap)
                if value > 0:
                    bar_h = bar_area_h * (value / peak)
                    bar_y = rect.y() + (bar_area_h - bar_h)
                    painter.fillRect(QRectF(bar_x, bar_y, bar_w, bar_h), QColor(color))
                if self._show_percentages and total > 0:
                    percentage = round(value / total * 100)
                    if percentage > 0:
                        painter.setPen(QColor(GREY))
                        painter.drawText(
                            QRectF(bar_x - gap, rect.y() + bar_area_h, bar_w + 2 * gap, label_h),
                            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                            f"{percentage}%",
                        )
        finally:
            painter.end()

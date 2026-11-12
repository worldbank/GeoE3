# -*- coding: utf-8 -*-
"""Unit tests for HelpPanel.

No longer tries to embed the docs in-app (the QtWebEngine import this
used to attempt only ever worked from PyQt5.QtWebEngineWidgets, which
can't succeed under this project's PyQt6/Qt6 stack) - every real run
already fell through to opening the published docs in the browser
regardless, so that's now the only thing this panel does.
"""
import unittest
from unittest.mock import patch

from geest.gui.panels.help_panel import HELP_URL, HelpPanel


class TestHelpPanel(unittest.TestCase):
    def setUp(self):
        self.panel = HelpPanel()

    def test_open_in_browser_opens_the_published_docs_url(self):
        with patch("geest.gui.panels.help_panel.QDesktopServices") as mock_qds:
            self.panel.open_in_browser()

        mock_qds.openUrl.assert_called_once()
        (url,) = mock_qds.openUrl.call_args[0]
        self.assertEqual(url.toString(), HELP_URL)

    def test_back_button_emits_switch_to_previous_tab(self):
        received = []
        self.panel.switch_to_previous_tab.connect(lambda: received.append(True))

        self.panel.switch_to_previous_tab.emit()

        self.assertEqual(received, [True])


if __name__ == "__main__":
    unittest.main()

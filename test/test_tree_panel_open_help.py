# -*- coding: utf-8 -*-
"""Regression test for TreePanel.open_help().

The Help panel/tab was removed entirely - clicking "Help" now opens the
published docs directly in the user's browser instead of switching to an
in-app panel.
"""
import unittest
from unittest.mock import MagicMock, patch

from geest.gui.panels.tree_panel import HELP_URL, TreePanel


class TestOpenHelp(unittest.TestCase):
    def test_open_help_opens_the_published_docs_url(self):
        panel = MagicMock()

        with patch("geest.gui.panels.tree_panel.QDesktopServices") as mock_qds:
            TreePanel.open_help(panel)

        mock_qds.openUrl.assert_called_once()
        (url,) = mock_qds.openUrl.call_args[0]
        self.assertEqual(url.toString(), HELP_URL)


if __name__ == "__main__":
    unittest.main()

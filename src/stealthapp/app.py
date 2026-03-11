"""Application bootstrap."""

import sys
import os

# Allow running from repo root without install
_src = os.path.join(os.path.dirname(__file__), "..", "..")
if _src not in sys.path:
    sys.path.insert(0, _src)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from stealthapp.core.config import Config
from stealthapp.core.overlay_window import OverlayWindow


def run():
    # Work from the directory that holds config.json / stats.json
    # so relative paths in config resolve correctly.
    launch_dir = os.environ.get("STEALTHAPP_DIR", os.getcwd())
    os.chdir(launch_dir)

    app = QApplication(sys.argv)
    app.setApplicationName("StealthApp")
    app.setQuitOnLastWindowClosed(True)

    config = Config("config.json")
    window = OverlayWindow(config)
    window.show()

    sys.exit(app.exec())

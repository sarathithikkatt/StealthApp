"""
OverlayWindow — The main transparent, always-on-top, capture-excluded window.

ALT key fix
───────────
Qt's WindowTransparentForInput flag can only be changed *before* the window
is shown — toggling it at runtime and calling show() causes flicker and
sometimes loses the HWND capture exclusion.

The correct Windows approach for a "press to interact" overlay is:
  • Keep the window NON-transparent for input at all times.
  • When in pass-through mode, make the window a "layered window" with a
    transparent hit-test region (WS_EX_LAYERED + WS_EX_TRANSPARENT).
  • When ALT is pressed, remove WS_EX_TRANSPARENT so the window receives
    mouse events normally.
  • This is done via SetWindowLongPtr on the extended window style — no
    Qt flag toggle, no window re-show required.
"""

from __future__ import annotations
import ctypes, platform
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSlot
from PyQt6.QtGui import QKeySequence, QShortcut

from stealthapp.core import capture_exclusion
from stealthapp.core.config import Config
from stealthapp.core.stat_watcher import StatWatcher
from stealthapp.widgets.header_bar import HeaderBar
from stealthapp.widgets.stat_panel import StatPanel
from stealthapp.widgets.chat_widget import ChatWidget
from stealthapp.widgets.audio_widget import AudioWidget
from stealthapp.widgets.ollama_widget import OllamaWidget


# ── Windows hit-test pass-through helpers ─────────────────────────────────────

_GWL_EXSTYLE   = -20
_WS_EX_LAYERED     = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020


def _win_set_passthrough(hwnd: int, enabled: bool):
    """Toggle WS_EX_TRANSPARENT on Windows (zero-flicker click-through)."""
    if platform.system() != "Windows":
        return
    try:
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongPtrW(hwnd, _GWL_EXSTYLE)
        if enabled:
            style |= (_WS_EX_LAYERED | _WS_EX_TRANSPARENT)
        else:
            style &= ~_WS_EX_TRANSPARENT        # keep LAYERED, remove TRANSPARENT
            style |= _WS_EX_LAYERED
        user32.SetWindowLongPtrW(hwnd, _GWL_EXSTYLE, style)
    except Exception as e:
        print(f"[Overlay] SetWindowLongPtr error: {e}")


# ── Main window ───────────────────────────────────────────────────────────────

class OverlayWindow(QMainWindow):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self._hwnd: int | None = None
        self._drag_pos: QPoint | None = None
        self._alt_held = False

        self._init_window()
        self._build_ui()
        self._setup_shortcuts()
        self._start_services()

        # Apply capture exclusion + initial pass-through after window is shown
        QTimer.singleShot(250, self._post_show_setup)

    # ── Window initialisation ─────────────────────────────────────────────────

    def _init_window(self):
        self.setWindowTitle("StealthApp")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool            # no taskbar entry
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(
            self.config.get("overlay_x"),
            self.config.get("overlay_y"),
            self.config.get("overlay_width"),
            self.config.get("overlay_height"),
        )
        self.setWindowOpacity(self.config.get("opacity"))

    def _post_show_setup(self):
        self._hwnd = int(self.winId())
        capture_exclusion.apply(self._hwnd)
        _win_set_passthrough(self._hwnd, True)   # start in pass-through

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        root.setStyleSheet("""
            #root {
                background: rgba(8, 10, 16, 0.90);
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.06);
            }
        """)
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = HeaderBar(self.config)
        self.header.close_clicked.connect(self.close)
        self.header.minimize_clicked.connect(self.showMinimized)
        layout.addWidget(self.header)

        self.stat_panel = StatPanel(self.config)
        layout.addWidget(self.stat_panel)

        layout.addWidget(_divider())

        self.chat_widget = ChatWidget(self.config)
        layout.addWidget(self.chat_widget)

        layout.addWidget(_divider())

        self.audio_widget = AudioWidget(self.config)
        layout.addWidget(self.audio_widget)

        layout.addWidget(_divider())

        self.ollama_widget = OllamaWidget(self.config)
        layout.addWidget(self.ollama_widget)

        self._hint = QLabel("Hold  ALT  to interact   ·   Ctrl+H  hide   ·   Ctrl+drag  move")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(_hint_style(False))
        layout.addWidget(self._hint)

    # ── Shortcuts ─────────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(self._toggle_visibility)

    def _toggle_visibility(self):
        self.setVisible(not self.isVisible())

    # ── Services ──────────────────────────────────────────────────────────────

    def _start_services(self):
        watcher = StatWatcher(self.config.get("stats_file"))
        watcher.stats_updated.connect(self.stat_panel.update_stats)
        watcher.start()
        self._stat_watcher = watcher

    # ── ALT = interactive mode ────────────────────────────────────────────────
    #
    # We intercept keyPress/keyRelease on the QMainWindow level.
    # Because the window is in pass-through mode (WS_EX_TRANSPARENT) when ALT
    # is not held, Windows never delivers mouse events to it — which is exactly
    # what we want so the game gets all inputs.
    # When the user presses ALT, we remove WS_EX_TRANSPARENT so Qt starts
    # receiving mouse events again.  No Qt flag toggling, no re-show.

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Alt and not self._alt_held:
            self._alt_held = True
            if self._hwnd:
                _win_set_passthrough(self._hwnd, False)
            self._hint.setText("🟢  Interactive — release ALT to return input to game")
            self._hint.setStyleSheet(_hint_style(True))
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Alt and self._alt_held:
            self._alt_held = False
            if self._hwnd:
                _win_set_passthrough(self._hwnd, True)
            self._hint.setText("Hold  ALT  to interact   ·   Ctrl+H  hide   ·   Ctrl+drag  move")
            self._hint.setStyleSheet(_hint_style(False))
        super().keyReleaseEvent(event)

    # ── Ctrl+drag to reposition ───────────────────────────────────────────────

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._drag_pos is not None
                and event.buttons() & Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_pos is not None:
            self._drag_pos = None
            pos = self.pos()
            self.config.set("overlay_x", pos.x())
            self.config.set("overlay_y", pos.y())
        super().mouseReleaseEvent(event)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _divider() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet("background: rgba(255,255,255,0.07);")
    return w


def _hint_style(active: bool) -> str:
    color = "rgba(100,255,150,0.75)" if active else "rgba(255,255,255,0.18)"
    return f"""
        color: {color};
        font-size: 10px;
        font-family: 'Consolas', monospace;
        padding: 7px;
        background: transparent;
    """

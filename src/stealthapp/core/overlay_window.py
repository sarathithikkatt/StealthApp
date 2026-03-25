"""
OverlayWindow — Transparent, always-on-top, capture-excluded overlay.

ALT key strategy (Windows)
──────────────────────────
Rather than toggling Qt's WindowTransparentForInput flag (which requires
re-showing the window and causes flicker), we use the Windows layered-window
approach:

  • The window is always visible and never re-shown after startup.
  • Pass-through mode  → WS_EX_LAYERED | WS_EX_TRANSPARENT
    (mouse events fall through to whatever is underneath)
  • Interactive mode   → WS_EX_LAYERED only  (remove TRANSPARENT)
    (normal Qt mouse delivery resumes)

SetWindowLongPtr on the extended style is the only Win32 call needed —
no Qt flag toggling, zero flicker.
"""

from __future__ import annotations

import ctypes
import os
import platform
import sys
import threading

from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

from stealthapp.core import capture_exclusion
from stealthapp.core.config import Config
from stealthapp.core.stat_watcher import StatWatcher
from stealthapp.widgets.audio_widget import AudioWidget
from stealthapp.widgets.header_bar import HeaderBar
from stealthapp.widgets.ollama_widget import OllamaWidget
from stealthapp.core.logger import get_logger

logger = get_logger(__name__)

# ── Windows constants ─────────────────────────────────────────────────────────

_GWL_EXSTYLE       = -20
_WS_EX_LAYERED     = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020

_VK_MENU     = 0x12          # ALT key virtual-key code
_VK_H        = 0x48
_MOD_CONTROL = 0x0002
_HOTKEY_ID   = 1
_WM_HOTKEY   = 0x0312


# ── Win32 helpers ─────────────────────────────────────────────────────────────

def _is_windows() -> bool:
    return platform.system() == "Windows"


def _win_set_passthrough(hwnd: int, enabled: bool) -> None:
    """Toggle WS_EX_TRANSPARENT on the overlay window (zero-flicker)."""
    if not _is_windows():
        return
    try:
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongPtrW(hwnd, _GWL_EXSTYLE)
        if enabled:
            style |= _WS_EX_LAYERED | _WS_EX_TRANSPARENT
        else:
            style = (style | _WS_EX_LAYERED) & ~_WS_EX_TRANSPARENT
        user32.SetWindowLongPtrW(hwnd, _GWL_EXSTYLE, style)
    except Exception as exc:
        logger.error(f"SetWindowLongPtr error: {exc}")


class _WinMSG(ctypes.Structure):
    """Minimal MSG struct for the hotkey message loop."""
    _fields_ = [
        ("hwnd",    ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam",  ctypes.c_void_p),
        ("lParam",  ctypes.c_void_p),
        ("time",    ctypes.c_uint),
        ("pt_x",    ctypes.c_long),
        ("pt_y",    ctypes.c_long),
    ]


# ── Main window ───────────────────────────────────────────────────────────────

class OverlayWindow(QMainWindow):
    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config    = config
        self._hwnd: int | None    = None
        self._drag_pos: QPoint | None = None
        self._alt_held = False

        logger.info("__init__ start")
        self._init_window()
        logger.info("init_window done")
        self._build_ui()
        logger.info("build_ui done")
        self._setup_shortcuts()
        logger.info("setup_shortcuts done")
        self._start_services()
        logger.info("start_services done")

        # Deferred post-show setup (capture exclusion, pass-through, hotkey).
        QTimer.singleShot(250, self._post_show_setup)

    # ── Window flags & geometry ───────────────────────────────────────────────

    def _init_window(self) -> None:
        self.setWindowTitle("StealthApp")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool           # hides from taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(
            self.config.get("overlay_x"),
            self.config.get("overlay_y"),
            self.config.get("overlay_width"),
            self.config.get("overlay_height"),
        )
        self.setWindowOpacity(self.config.get("opacity"))

    # ── Post-show initialisation (Win32 side) ─────────────────────────────────

    def _post_show_setup(self) -> None:
        logger.info("post_show_setup start")
        self._hwnd = int(self.winId())
        capture_exclusion.apply(self._hwnd)
        _win_set_passthrough(self._hwnd, True)   # start in pass-through

        if not _is_windows():
            return

        # Poll ALT state so we can toggle interactive mode even when a game
        # owns keyboard focus.
        self._alt_timer = QTimer(self)
        self._alt_timer.setInterval(50)
        self._alt_timer.timeout.connect(self._poll_alt_state)
        self._alt_timer.start()

        # Global Ctrl+H hotkey handled in a dedicated background thread.
        try:
            if ctypes.windll.user32.RegisterHotKey(None, _HOTKEY_ID, _MOD_CONTROL, _VK_H):
                threading.Thread(
                    target=self._hotkey_message_loop,
                    daemon=True,
                    name="hotkey-loop",
                ).start()
            else:
                logger.warning("RegisterHotKey failed — Ctrl+H unavailable")
        except Exception as exc:
            logger.error(f"hotkey setup error: {exc}")
        logger.info("post_show_setup done")

    # ── UI layout ─────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        root.setStyleSheet("""
            #root {
                background: rgba(8, 10, 16, 0.90);
                border-radius: 14px;
                border: 1px solid rgba(255, 255, 255, 0.06);
            }
        """)
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = HeaderBar(self.config)
        self.header.close_clicked.connect(self._quit)
        self.header.minimize_clicked.connect(self._toggle_visibility)
        layout.addWidget(self.header)

        layout.addWidget(_Divider())

        self.audio_widget = AudioWidget(self.config)
        layout.addWidget(self.audio_widget)

        layout.addWidget(_Divider())

        self.ollama_widget = OllamaWidget(self.config)
        layout.addWidget(self.ollama_widget)

        self._hint = QLabel(
            "Hold  ALT  to interact   ·   Ctrl+H  hide   ·   Ctrl+drag  move"
        )
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(_hint_css(active=False))
        layout.addWidget(self._hint)

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def _setup_shortcuts(self) -> None:
        sc = QShortcut(QKeySequence("Ctrl+H"), self)
        sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
        sc.activated.connect(self._toggle_visibility)

    def _toggle_visibility(self) -> None:
        self.setVisible(not self.isVisible())

    # ── Background services ───────────────────────────────────────────────────

    def _start_services(self) -> None:
        pass

    # ── ALT  →  interactive mode ──────────────────────────────────────────────

    def _enter_interactive(self) -> None:
        self._alt_held = True
        if self._hwnd:
            _win_set_passthrough(self._hwnd, False)
        self.activateWindow()
        self.setFocus()
        self._hint.setText("🟢  Interactive — release ALT to return input to desktop")
        self._hint.setStyleSheet(_hint_css(active=True))

    def _exit_interactive(self) -> None:
        self._alt_held = False
        if self._hwnd:
            _win_set_passthrough(self._hwnd, True)
        self._hint.setText(
            "Hold  ALT  to interact   ·   Ctrl+H  hide   ·   Ctrl+drag  move"
        )
        self._hint.setStyleSheet(_hint_css(active=False))

    # Qt key events (used when the overlay already has focus)
    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Alt and not self._alt_held:
            self._enter_interactive()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Alt and self._alt_held:
            self._exit_interactive()
        super().keyReleaseEvent(event)

    def _poll_alt_state(self) -> None:
        """Poll the system ALT key state (Windows) to synthesise press/release.

        Necessary because a fullscreen game typically owns keyboard focus while
        the overlay is in pass-through mode, so Qt never delivers key events.
        """
        try:
            is_down = bool(ctypes.windll.user32.GetAsyncKeyState(_VK_MENU) & 0x8000)
            if is_down and not self._alt_held:
                self._enter_interactive()
            elif not is_down and self._alt_held:
                self._exit_interactive()
        except Exception:
            pass   # polling must never crash the UI thread

    # ── Global Ctrl+H hotkey (background thread) ──────────────────────────────

    def _hotkey_message_loop(self) -> None:
        """Receive WM_HOTKEY and forward toggle to the main thread."""
        user32 = ctypes.windll.user32
        msg = _WinMSG()
        try:
            while True:
                if user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) == 0:
                    break
                if msg.message == _WM_HOTKEY and int(msg.wParam) == _HOTKEY_ID:
                    QTimer.singleShot(0, self._toggle_visibility)
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            pass

    def _unregister_hotkey(self) -> None:
        if _is_windows():
            try:
                ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)
            except Exception:
                pass

    # ── Ctrl+drag to reposition ───────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        mods = event.modifiers() | QApplication.keyboardModifiers()
        if (
            event.button() == Qt.MouseButton.LeftButton
            and mods & Qt.KeyboardModifier.ControlModifier
        ):
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        mods = event.modifiers() | QApplication.keyboardModifiers()
        if (
            self._drag_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and mods & Qt.KeyboardModifier.ControlModifier
        ):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_pos is not None:
            self._drag_pos = None
            pos = self.pos()
            self.config.set("overlay_x", pos.x())
            self.config.set("overlay_y", pos.y())
        super().mouseReleaseEvent(event)

    # ── Shutdown ──────────────────────────────────────────────────────────────

    def _quit(self) -> None:
        """Cleanly shut down: unregister hotkey, then terminate the process."""
        self._unregister_hotkey()
        QApplication.instance().quit()   # graceful Qt teardown
        os._exit(0)                      # hard-kill the Python process

    def closeEvent(self, event) -> None:
        self._unregister_hotkey()
        super().closeEvent(event)


# ── Small helpers ─────────────────────────────────────────────────────────────

class _Divider(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(1)
        self.setStyleSheet("background: rgba(255, 255, 255, 0.07);")


def _hint_css(*, active: bool) -> str:
    color = "rgba(100, 255, 150, 0.75)" if active else "rgba(255, 255, 255, 0.18)"
    return (
        f"color: {color};"
        "font-size: 10px;"
        "font-family: 'Consolas', monospace;"
        "padding: 7px;"
        "background: transparent;"
    )
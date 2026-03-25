"""
VisionWidget — screen capture UI.
Allows capturing Chrome, Teams, or the Full Screen.
Sends the captured image to OCRWorker.
"""

from __future__ import annotations
import ctypes
import os
from pathlib import Path
import io
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap

from stealthapp.ai.ocr_worker import OCRWorker
from stealthapp.core.logger import get_logger

logger = get_logger(__name__)

def find_window_by_name(substrings: list[str]) -> int:
    hwnds = []
    def callback(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.lower()
                for sub in substrings:
                    if sub.lower() in title:
                        hwnds.append(hwnd)
                        break
        return True

    try:
        EnumWindows = ctypes.windll.user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        EnumWindows(EnumWindowsProc(callback), 0)
    except Exception as e:
        logger.error(f"Failed to enumerate windows: {e}")

    return hwnds[0] if hwnds else 0


def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Get window coordinates (left, top, right, bottom)."""
    try:
        rect = ctypes.wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception as e:
        logger.error(f"Failed to get window rect: {e}")
    return None


def activate_window(hwnd: int) -> bool:
    """Bring a window to the foreground."""
    try:
        # Get current foreground window to restore later
        user32 = ctypes.windll.user32
        # SetForegroundWindow requires the window to be visible first
        user32.ShowWindow(ctypes.c_void_p(hwnd), 5)  # SW_SHOW
        user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
        logger.info(f"Activated window {hwnd}")
        return True
    except Exception as e:
        logger.error(f"Failed to activate window: {e}")
        return False


def restore_focus(hwnd: int) -> None:
    """Restore focus to a specific window."""
    try:
        if hwnd != 0:
            user32 = ctypes.windll.user32
            user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
            logger.info(f"Restored focus to window {hwnd}")
    except Exception as e:
        logger.error(f"Failed to restore focus: {e}")

class VisionWidget(QWidget):
    text_extracted = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._worker = None
        self._build()

    def _build(self):
        lo = QVBoxLayout(self); lo.setContentsMargins(10, 6, 10, 6); lo.setSpacing(4)
        self.setStyleSheet("background:transparent;")

        hdr = QHBoxLayout()
        title = QLabel("VISION")
        title.setStyleSheet("color:rgba(255,255,255,0.35);font-size:9px;font-family:'Consolas',monospace;letter-spacing:2px;background:transparent;")
        hdr.addWidget(title); hdr.addStretch()
        
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color:rgba(255,255,255,0.2);font-size:10px;background:transparent;")
        hdr.addWidget(self._status_dot)
        lo.addLayout(hdr)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        
        self._btn_chrome = QPushButton("Capture Chrome")
        self._btn_teams = QPushButton("Capture Teams")
        self._btn_screen = QPushButton("Capture Screen")
        
        for btn in (self._btn_chrome, self._btn_teams, self._btn_screen):
            btn.setFixedSize(90, 20)
            btn.setStyleSheet(self._btn_style())
            btn_layout.addWidget(btn)
            
        btn_layout.addStretch()
        lo.addLayout(btn_layout)
        
        self._btn_chrome.clicked.connect(lambda: self._capture_target(["google chrome"]))
        self._btn_teams.clicked.connect(lambda: self._capture_target(["microsoft teams"]))
        self._btn_screen.clicked.connect(lambda: self._capture_target([]))

        self._info = QLabel("Ready")
        self._info.setStyleSheet("color:rgba(255,255,255,0.25);font-size:10px;font-family:'Consolas',monospace;background:transparent;")
        lo.addWidget(self._info)

    def _capture_target(self, target_names: list[str]):
        hwnd = 0
        prev_hwnd = 0
        
        if target_names:
            hwnd = find_window_by_name(target_names)
            if hwnd == 0:
                self._info.setText(f"Could not find '{target_names[0]}'")
                logger.warning(f"Window not found for: {target_names}")
                return
            logger.info(f"Found window hwnd={hwnd} for: {target_names}")
            
            # Save current foreground window to restore later
            try:
                prev_hwnd = ctypes.windll.user32.GetForegroundWindow()
                logger.info(f"Saved previous foreground window: {prev_hwnd}")
            except Exception as e:
                logger.error(f"Failed to get current foreground window: {e}")
            
            # Activate the target window (bring to front)
            activate_window(hwnd)
            
            # Wait for window to render
            import time
            time.sleep(0.3)
        
        self._info.setText("Capturing...")
        self._status_dot.setStyleSheet("color:rgba(255,200,50,0.9);font-size:10px;background:transparent;")
        
        pixmap = None
        
        # Try PIL ImageGrab first (more reliable for Windows)
        if hwnd != 0:
            try:
                from PIL import ImageGrab
                rect = get_window_rect(hwnd)
                if rect:
                    left, top, right, bottom = rect
                    logger.info(f"Attempting PIL ImageGrab with rect: left={left}, top={top}, right={right}, bottom={bottom}")
                    # PIL ImageGrab expects (left, top, right, bottom)
                    pil_img = ImageGrab.grab(bbox=(left, top, right, bottom))
                    logger.info(f"PIL ImageGrab successful: {pil_img.size}")
                    
                    # Convert PIL Image to QPixmap
                    buffer = io.BytesIO()
                    pil_img.save(buffer, format="PNG")
                    buffer.seek(0)
                    pixmap = QPixmap()
                    pixmap.loadFromData(buffer.getvalue())
                    logger.info(f"Converted to QPixmap: {pixmap.width()}x{pixmap.height()}")
            except Exception as e:
                logger.warning(f"PIL ImageGrab failed: {e}")
                pixmap = None
        
        # Fallback to PyQt grabWindow if PIL didn't work or for full screen
        if pixmap is None or pixmap.isNull():
            logger.info("Falling back to PyQt grabWindow")
            screen = QApplication.primaryScreen()
            
            if hwnd != 0:
                pixmap = screen.grabWindow(hwnd)
                logger.info(f"grabWindow({hwnd}) returned: size={pixmap.width()}x{pixmap.height()}, isNull={pixmap.isNull()}")
                
                # If grabWindow returns empty/invalid pixmap, use full screen + crop
                if pixmap.isNull() or pixmap.width() <= 0 or pixmap.height() <= 0:
                    logger.warning(f"grabWindow({hwnd}) returned invalid pixmap, falling back to full screen + crop")
                    
                    rect = get_window_rect(hwnd)
                    if rect:
                        left, top, right, bottom = rect
                        logger.info(f"Window rect: left={left}, top={top}, right={right}, bottom={bottom}, size={right-left}x{bottom-top}")
                        full_pixmap = screen.grabWindow(0)
                        pixmap = full_pixmap.copy(left, top, right - left, bottom - top)
                        logger.info(f"Cropped pixmap: size={pixmap.width()}x{pixmap.height()}, isNull={pixmap.isNull()}")
                    else:
                        logger.warning("Could not get window rect, using full screen")
                        pixmap = screen.grabWindow(0)
            else:
                pixmap = screen.grabWindow(0)
                logger.info(f"Captured full screen: size={pixmap.width()}x{pixmap.height()}")
        
        # Restore previous window focus
        if prev_hwnd != 0:
            restore_focus(prev_hwnd)
        
        # Debug: save the captured image for inspection
        try:
            debug_path = Path(os.getcwd()) / "last_capture.png"
            pixmap.save(str(debug_path))
            logger.info(f"Saved debug capture to: {debug_path}")
        except Exception as e:
            logger.error(f"Failed to save debug image: {e}")
        
        self._info.setText(f"Captured {pixmap.width()}x{pixmap.height()}. Running OCR...")
        self._start_ocr(pixmap)

    def _start_ocr(self, pixmap):
        self._worker = OCRWorker(pixmap)
        self._worker.text_extracted.connect(self._on_ocr_success)
        self._worker.error_occurred.connect(self._on_ocr_error)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()
        
        # Disable buttons while processing
        for btn in (self._btn_chrome, self._btn_teams, self._btn_screen):
            btn.setEnabled(False)

    def _on_ocr_success(self, text: str):
        self._info.setText(f"OCR Success: {len(text)} chars.")
        self._status_dot.setStyleSheet("color:rgba(80,200,120,0.9);font-size:10px;background:transparent;")
        self.text_extracted.emit(text)
        self._reset_buttons()

    def _on_ocr_error(self, err: str):
        self._info.setText(f"OCR Error: {err}")
        self._status_dot.setStyleSheet("color:rgba(255,80,80,0.9);font-size:10px;background:transparent;")
        self._reset_buttons()

    def _reset_buttons(self):
        for btn in (self._btn_chrome, self._btn_teams, self._btn_screen):
            btn.setEnabled(True)

    @staticmethod
    def _btn_style() -> str:
        return """
            QPushButton {
                background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.8);
                border: none; border-radius: 4px; font-size: 9px; font-family: 'Consolas', monospace;
            }
            QPushButton:hover { background: rgba(255,255,255,0.18); }
            QPushButton:disabled { opacity: 0.4; }
        """

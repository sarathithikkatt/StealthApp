from __future__ import annotations
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPixmap

class AIEngine(QObject):
    """Base interface for all AI engines."""
    token_received  = pyqtSignal(str)    # incremental token
    response_done   = pyqtSignal(str)    # full response when complete
    error_occurred  = pyqtSignal(str)
    status_changed  = pyqtSignal(str)    # "thinking" / "ready" / "offline"

    def chat(self, user_message: str):
        raise NotImplementedError

    def clear_history(self):
        raise NotImplementedError

    def set_model(self, model: str):
        raise NotImplementedError

    def ping(self):
        raise NotImplementedError


class Transcriber(QObject):
    """Base interface for all transcription engines."""
    text_ready = pyqtSignal(str)
    model_loaded = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)
    silence_timeout = pyqtSignal()

    def load_model(self):
        raise NotImplementedError

    @pyqtSlot(bytes, int)
    def process_chunk(self, pcm: bytes, rate: int):
        raise NotImplementedError

    @property
    def is_active(self) -> bool:
        raise NotImplementedError

    @is_active.setter
    def is_active(self, value: bool):
        raise NotImplementedError


class OCRScanner(QObject):
    """Base interface for all OCR engines."""
    text_extracted = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def scan(self, pixmap: QPixmap):
        raise NotImplementedError

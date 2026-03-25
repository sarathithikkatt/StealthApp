"""
AudioWidget — microphone capture UI.
Shows a VU meter, record/stop button, and last transcribed text.
Connects to AudioRecorder; transcription hook is left open for Whisper.
"""

from __future__ import annotations
import time
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import QThread, pyqtSlot, QTimer, QMetaObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from stealthapp.ai.transcript import TranscriptionWorker
from stealthapp.audio.recorder import AudioRecorder
from stealthapp.core.logger import get_logger

logger = get_logger(__name__)

class _VUMeter(QWidget):
    """Simple horizontal bar VU meter."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(6)
        self._level = 0.0
        self._bars = 20

    def set_level(self, v: float):
        self._level = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QBrush
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width(); h = self.height()
        bar_w = w / self._bars
        active = int(self._level * self._bars)
        for i in range(self._bars):
            if i < active:
                ratio = i / self._bars
                if ratio < 0.6:
                    color = QColor(80, 200, 120)
                elif ratio < 0.85:
                    color = QColor(255, 200, 50)
                else:
                    color = QColor(255, 80, 80)
            else:
                color = QColor(255, 255, 255, 20)
            p.fillRect(int(i * bar_w) + 1, 0, int(bar_w) - 1, h, color)


class AudioWidget(QWidget):
    text_transcribed = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        logger.info("__init__ start")
        # 1. Initialize the recorder
        self._recorder = AudioRecorder(config)

        # 2. Initialize the worker AND the thread
        self._worker = TranscriptionWorker(config.get("whisper_model", "base"))
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        # 3. Connect the signals
        self._recorder.chunk_ready.connect(self._on_chunk)
        self._recorder.chunk_ready.connect(self._worker.process_chunk)
        self._worker.text_ready.connect(self._on_text_received)
        self._worker.silence_timeout.connect(self._stop_recording) # Auto-stop on silence

        self._recorder.level_changed.connect(self._on_level)
        self._recorder.error_occurred.connect(self._on_error)
        self._recording = False
        # 4. Start the thread loop (model load deferred until user starts audio)
        self._thread.start()
        logger.info("transcription thread started (model load deferred)")
        # Decay VU meter when not recording
        self._decay = QTimer()
        self._decay.setInterval(80)
        self._decay.timeout.connect(self._decay_level)

        self._build()

        if config.get("audio_enabled", True):
            self._auto_start()
            logger.info("auto_start requested")

        logger.info("__init__ done")

        # Connect model-loaded signal to handler
        try:
            self._worker.model_loaded.connect(self._on_model_loaded)
        except Exception:
            pass

    def _build(self):
        lo = QVBoxLayout(self); lo.setContentsMargins(10,6,10,6); lo.setSpacing(4)
        self.setStyleSheet("background:transparent;")

        hdr = QHBoxLayout()
        title = QLabel("AUDIO")
        title.setStyleSheet("color:rgba(255,255,255,0.35);font-size:9px;font-family:'Consolas',monospace;letter-spacing:2px;background:transparent;")
        hdr.addWidget(title); hdr.addStretch()

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color:rgba(255,255,255,0.2);font-size:10px;background:transparent;")
        hdr.addWidget(self._status_dot)

        self._btn = QPushButton("Start Mic")
        self._btn.setFixedSize(72, 20)
        self._btn.setStyleSheet(self._btn_style(False))
        self._btn.clicked.connect(self._toggle)
        hdr.addWidget(self._btn)
        lo.addLayout(hdr)

        self._vu = _VUMeter()
        lo.addWidget(self._vu)

        self._info = QLabel("Mic inactive")
        self._info.setStyleSheet("color:rgba(255,255,255,0.25);font-size:10px;font-family:'Consolas',monospace;background:transparent;")
        lo.addWidget(self._info)

    def _auto_start(self):
        self._start_recording()

    def _start_recording(self):
        self._recording = True
        # If the transcription model is not ready yet, request loading and defer starting
        if not getattr(self._worker, "_ready", False):
            self._pending_start = True
            self._btn.setText("Loading…")
            self._btn.setEnabled(False)
            try:
                QMetaObject.invokeMethod(self._worker, "load_model", Qt.ConnectionType.QueuedConnection)
                logger.info("scheduled worker.load_model() on Start")
            except Exception as e:
                logger.error(f"failed to schedule model load: {e}")
                self._btn.setEnabled(True)
            return

        self._pending_start = False
        self._worker.is_active = True
        self._worker.last_activity = time.time()
        self._recorder.start()
        self._decay.start()
        self._btn.setText("Stop Mic")
        self._btn.setStyleSheet(self._btn_style(True))
        self._status_dot.setStyleSheet("color:rgba(80,200,120,0.9);font-size:10px;background:transparent;")
        self._info.setText("Recording...")

    def _stop_recording(self):
        self._recording = False
        self._recorder.stop()
        self._decay.stop()
        self._vu.set_level(0)
        self._btn.setText("Start Mic")
        self._btn.setStyleSheet(self._btn_style(False))
        self._status_dot.setStyleSheet("color:rgba(255,255,255,0.2);font-size:10px;background:transparent;")
        self._info.setText("Mic inactive")

    def _toggle(self):
        if self._recording: self._stop_recording()
        else: self._start_recording()

    def _on_model_loaded(self, success: bool, msg: str):
        logger.info(f"model_loaded: success={success} msg={msg}")
        self._btn.setEnabled(True)
        if not success:
            self._info.setText(f"Model load failed: {msg}")
            self._btn.setText("Start Mic")
            self._pending_start = False
            return
        # If user attempted to start recording before load completed, start now
        if getattr(self, "_pending_start", False):
            self._start_recording()

    @pyqtSlot(float)
    def _on_level(self, v: float):
        self._vu.set_level(v)

    @pyqtSlot(bytes, int)
    def _on_chunk(self, pcm: bytes, rate: int):
        kb = len(pcm) / 1024
        self._info.setText(f"Audio captured: {kb:.1f} KB. Sent to worker.")
        logger.info(f"[AudioWidget] Audio block captured and delegated asynchronously: {kb:.1f} KB")

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._info.setText(f"⚠ {msg}")
        self._stop_recording()

    @pyqtSlot(str)
    def _on_text_received(self, text):
        # Handle the transcribed text (e.g., add to a text edit)
        logger.info(f"Transcribed: {text}")
        self._info.setText(f"Last text: {text[:30]}...")
        try:
            logger.info("[AudioWidget] Emitting transcribed text to downstream components")
            self.text_transcribed.emit(text)
        except Exception as e:
            logger.error(f"[AudioWidget] Failed to emit transcribed text: {e}")

    def _decay_level(self):
        # Smooth decay so meter doesn't snap to zero between callbacks
        current = self._vu._level
        if current > 0:
            self._vu.set_level(current * 0.85)

    @staticmethod
    def _btn_style(active: bool) -> str:
        bg = "rgba(255,80,80,0.7)" if active else "rgba(255,255,255,0.08)"
        return f"""
            QPushButton {{
                background:{bg}; color:rgba(255,255,255,0.8);
                border:none; border-radius:4px; font-size:9px; font-family:'Consolas',monospace;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.18); }}
        """

    def closeEvent(self, event):
        """Ensures the thread is cleaned up when the widget is closed."""
        # 1. Stop the worker's processing
        self._worker.is_active = False
        
        # 2. Stop the recorder
        self._recorder.stop()
        
        # 3. Quit the thread and wait for it to finish
        self._thread.quit()
        self._thread.wait()
        
        super().closeEvent(event)
"""
AudioWidget — microphone capture UI.
Shows a VU meter, record/stop button, and last transcribed text.
Connects to AudioRecorder; transcription hook is left open for Whisper.
"""

from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QColor
from stealthapp.audio.recorder import AudioRecorder


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
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._recorder = AudioRecorder(config)
        self._recorder.level_changed.connect(self._on_level)
        self._recorder.error_occurred.connect(self._on_error)
        self._recorder.chunk_ready.connect(self._on_chunk)
        self._recording = False

        # Decay VU meter when not recording
        self._decay = QTimer()
        self._decay.setInterval(80)
        self._decay.timeout.connect(self._decay_level)

        self._build()

        if config.get("audio_enabled", True):
            self._auto_start()

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

    @pyqtSlot(float)
    def _on_level(self, v: float):
        self._vu.set_level(v)

    @pyqtSlot(bytes, int)
    def _on_chunk(self, pcm: bytes, rate: int):
        """
        PCM audio chunk is ready.
        Hook Whisper or any STT here:

            import whisper
            model = whisper.load_model("base")
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32767
            result = model.transcribe(audio, fp16=False)
            print(result["text"])
        """
        kb = len(pcm) / 1024
        self._info.setText(f"Chunk captured: {kb:.1f} KB — hook STT here")

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._info.setText(f"⚠ {msg}")
        self._stop_recording()

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

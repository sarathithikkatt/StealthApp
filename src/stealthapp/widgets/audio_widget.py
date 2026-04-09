"""
AudioWidget — microphone capture UI.
Shows a VU meter, record/stop button, and last transcribed text.
Connects to AudioRecorder; transcription hook is left open for Whisper.
"""

from __future__ import annotations
import time
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox
from PyQt6.QtCore import QThread, pyqtSlot, QTimer, QMetaObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from stealthapp.ai.factory import AIEngineFactory
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
        self._worker = AIEngineFactory.create_transcriber(config)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        # 3. Connect the signals
        self._recorder.chunk_ready.connect(self._on_chunk)
        self._recorder.chunk_ready.connect(self._worker.process_chunk)
        self._worker.text_ready.connect(self._on_text_received)
        self._worker.silence_timeout.connect(self._stop_recording) # Auto-stop on silence

        self._recorder.level_changed.connect(self._on_level)
        self._recorder.error_occurred.connect(self._on_error)
        self._recorder.devices_updated.connect(self._on_devices_updated)
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

        # Device selection row
        device_row = QHBoxLayout()
        device_label = QLabel("Device:")
        device_label.setStyleSheet("color:rgba(255,255,255,0.25);font-size:9px;font-family:'Consolas',monospace;background:transparent;")
        device_row.addWidget(device_label)
        
        self._device_dropdown = QComboBox()
        self._device_dropdown.setStyleSheet("""
            QComboBox {
                background: rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.8);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 9px;
                font-family: 'Consolas', monospace;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid rgba(255,255,255,0.5);
                margin-right: 4px;
            }
            QComboBox QAbstractItemView {
                background: rgba(30,30,30,0.95);
                color: rgba(255,255,255,0.9);
                border: 1px solid rgba(255,255,255,0.2);
                selection-background-color: rgba(80,200,120,0.3);
            }
        """)
        self._device_dropdown.currentIndexChanged.connect(self._on_device_changed)
        device_row.addWidget(self._device_dropdown)
        
        self._refresh_btn = QPushButton("⟳")
        self._refresh_btn.setFixedSize(20, 18)
        self._refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.6);
                border: 1px solid rgba(255,255,255,0.15);
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.15);
                color: rgba(255,255,255,0.8);
            }
        """)
        self._refresh_btn.clicked.connect(self._refresh_devices)
        device_row.addWidget(self._refresh_btn)
        device_row.addStretch()
        lo.addLayout(device_row)
        
        # Initialize device list
        self._refresh_devices()

    def _auto_start(self):
        self._start_recording()

    def _start_recording(self):
        self._recording = True
        self._device_dropdown.setEnabled(False)
        
        # Update status with device info
        device_info = self._recorder.get_device_info()
        device_name = device_info.get("name", "Unknown Device")
        
        # If the transcription model is not ready yet, request loading and defer starting
        if not getattr(self._worker, "_ready", False):
            self._pending_start = True
            self._btn.setText("Loading…")
            self._btn.setEnabled(False)
            self._info.setText(f"Loading model for {device_name}...")
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
        self._info.setText(f"Recording on {device_name}...")

    def _stop_recording(self):
        self._recording = False
        self._recorder.stop()
        self._decay.stop()
        self._vu.set_level(0)
        self._btn.setText("Start Mic")
        self._btn.setStyleSheet(self._btn_style(False))
        self._status_dot.setStyleSheet("color:rgba(255,255,255,0.2);font-size:10px;background:transparent;")
        self._info.setText("Mic inactive")
        self._device_dropdown.setEnabled(True)

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
        device_info = self._recorder.get_device_info()
        device_name = device_info.get("name", "Unknown Device")
        self._info.setText(f"Audio captured: {kb:.1f} KB @ {rate//1000}kHz from {device_name}")
        logger.info(f"[AudioWidget] Audio block captured and delegated asynchronously: {kb:.1f} KB")

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._info.setText(f"⚠ {msg}")
        self._stop_recording()
        self._device_dropdown.setEnabled(True)

    @pyqtSlot(str)
    def _on_text_received(self, text):
        # Handle the transcribed text (e.g., add to a text edit)
        logger.info(f"Transcribed: {text}")
        device_info = self._recorder.get_device_info()
        device_name = device_info.get("name", "Unknown Device")
        self._info.setText(f"Last: {text[:30]}... ({device_name})")
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

    def _refresh_devices(self):
        """Refresh the list of available audio devices"""
        try:
            devices = self._recorder.list_devices()
            self._device_dropdown.clear()
            
            current_device_index = self.config.get("audio_device_index", None)
            selected_index = -1
            
            for i, device in enumerate(devices):
                display_name = device["name"]
                if device["is_default"]:
                    display_name += " (Default)"
                if device["default_rate"] != 16000:
                    display_name += f" @{device['default_rate']//1000}kHz"
                
                self._device_dropdown.addItem(display_name, device["index"])
                
                if current_device_index == device["index"] or (current_device_index is None and device["is_default"]):
                    selected_index = i
            
            if selected_index >= 0:
                self._device_dropdown.setCurrentIndex(selected_index)
                # Set the device in recorder if not already set
                if current_device_index is None:
                    default_device = devices[selected_index]
                    self._recorder.set_device(default_device["index"])
            
            logger.info(f"Refreshed {len(devices)} audio devices")
        except Exception as e:
            logger.error(f"Failed to refresh devices: {e}")
            self._info.setText(f"⚠ Device refresh failed: {e}")
    
    @pyqtSlot(int)
    def _on_device_changed(self, index: int):
        """Handle device selection change"""
        if index < 0:
            return
        
        device_index = self._device_dropdown.itemData(index)
        if device_index is not None and device_index != self.config.get("audio_device_index"):
            success = self._recorder.set_device(device_index)
            if success:
                device_info = self._recorder.get_device_info()
                logger.info(f"Device changed to: {device_info.get('name', 'Unknown')}")
                if not self._recording:
                    self._info.setText(f"Device: {device_info.get('name', 'Unknown')}")
            else:
                logger.error("Failed to change device")
                self._info.setText("⚠ Failed to change device")
    
    @pyqtSlot(list)
    def _on_devices_updated(self, devices: list):
        """Handle device list updates"""
        # This can be called when devices are plugged/unplugged
        self._refresh_devices()
    
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
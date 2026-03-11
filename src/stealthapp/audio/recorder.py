"""
AudioRecorder — captures microphone audio in chunks and emits
a signal with raw PCM bytes. Plug into Whisper or any STT pipeline.
"""

from __future__ import annotations
import threading
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

try:
    import sounddevice as sd
    _HAS_SD = True
except ImportError:
    _HAS_SD = False


class AudioRecorder(QObject):
    # Emits (pcm_bytes: bytes, sample_rate: int) when a chunk is ready
    chunk_ready = pyqtSignal(bytes, int)
    level_changed = pyqtSignal(float)   # 0.0 – 1.0 RMS level for VU meter
    error_occurred = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._rate: int = config.get("audio_sample_rate", 16000)
        self._chunk_secs: int = config.get("audio_chunk_seconds", 5)
        self._device = config.get("audio_device_index", None)
        self._recording = False
        self._stream = None

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        if not _HAS_SD:
            self.error_occurred.emit("sounddevice not installed.\nRun: pip install sounddevice")
            return
        if self._recording:
            return
        self._recording = True
        threading.Thread(target=self._record_loop, daemon=True).start()

    def stop(self):
        self._recording = False

    @staticmethod
    def list_devices() -> list[dict]:
        if not _HAS_SD:
            return []
        devs = sd.query_devices()
        return [
            {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
            for i, d in enumerate(devs)
            if d["max_input_channels"] > 0
        ]

    # ── Recording loop ────────────────────────────────────────────────────────

    def _record_loop(self):
        chunk_frames = self._rate * self._chunk_secs
        buf: list[np.ndarray] = []
        frames_collected = 0

        def callback(indata: np.ndarray, frames: int, time_info, status):
            nonlocal frames_collected
            if status:
                print(f"[Audio] {status}")

            mono = indata[:, 0] if indata.ndim > 1 else indata.flatten()

            # Emit VU level
            rms = float(np.sqrt(np.mean(mono ** 2)))
            normalized = min(rms * 10, 1.0)
            self.level_changed.emit(normalized)

            buf.append(mono.copy())
            frames_collected += frames

            if frames_collected >= chunk_frames:
                pcm = np.concatenate(buf)
                pcm_bytes = (pcm * 32767).astype(np.int16).tobytes()
                self.chunk_ready.emit(pcm_bytes, self._rate)
                buf.clear()
                frames_collected = 0

        try:
            with sd.InputStream(
                samplerate=self._rate,
                channels=1,
                dtype="float32",
                device=self._device,
                blocksize=1024,
                callback=callback,
            ):
                while self._recording:
                    sd.sleep(100)
        except Exception as e:
            self.error_occurred.emit(str(e))
            self._recording = False

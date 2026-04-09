"""
AudioRecorder — captures microphone audio in chunks and emits
a signal with raw PCM bytes. Plug into Whisper or any STT pipeline.
"""

from __future__ import annotations
import threading
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from stealthapp.core.logger import get_logger

logger = get_logger(__name__)

try:
    import sounddevice as sd
    _HAS_SD = True
except ImportError:
    _HAS_SD = False

try:
    from scipy import signal
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


class AudioRecorder(QObject):
    # Emits (pcm_bytes: bytes, sample_rate: int) when a chunk is ready
    chunk_ready = pyqtSignal(bytes, int)
    level_changed = pyqtSignal(float)   # 0.0 – 1.0 RMS level for VU meter
    error_occurred = pyqtSignal(str)
    devices_updated = pyqtSignal(list)  # Emits list of available devices

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._target_rate: int = config.get("audio_sample_rate", 16000)
        self._chunk_secs: int = config.get("audio_chunk_seconds", 5)
        self._device = config.get("audio_device_index", None)
        self._auto_resample = config.get("audio_auto_resample", True)
        self._recording = False
        self._stream = None
        self._current_device_rate = None
        logger.info(f"initialized, target_rate={self._target_rate}, auto_resample={self._auto_resample}")

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        if not _HAS_SD:
            self.error_occurred.emit("sounddevice not installed.\nRun: pip install sounddevice")
            return
        if self._recording:
            return
        self._recording = True
        logger.info("start() called")
        threading.Thread(target=self._record_loop, daemon=True).start()

    def stop(self):
        self._recording = False

    @staticmethod
    def list_devices() -> list[dict]:
        """Get detailed list of available input devices"""
        if not _HAS_SD:
            return []
        try:
            devs = sd.query_devices()
            default_input = sd.default.device[0]  # Default input device index
            devices = []
            for i, d in enumerate(devs):
                if d["max_input_channels"] > 0:
                    devices.append({
                        "index": i,
                        "name": d["name"],
                        "channels": d["max_input_channels"],
                        "default_rate": d.get("default_samplerate", 44100),
                        "is_default": i == default_input
                    })
            return devices
        except Exception as e:
            logger.error(f"Failed to list devices: {e}")
            return []

    def set_device(self, device_index: int) -> bool:
        """Set the recording device. Returns True if successful."""
        if self._recording:
            logger.warning("Cannot change device while recording")
            return False
        
        devices = self.list_devices()
        device = next((d for d in devices if d["index"] == device_index), None)
        
        if not device:
            logger.error(f"Device {device_index} not found")
            return False
        
        self._device = device_index
        self._current_device_rate = device["default_rate"]
        self.config.set("audio_device_index", device_index)
        logger.info(f"Device set to: {device['name']} @ {self._current_device_rate}Hz")
        return True

    def get_device_info(self, device_index: int = None) -> dict:
        """Get information about a specific device or current device"""
        if device_index is None:
            device_index = self._device
        
        devices = self.list_devices()
        device = next((d for d in devices if d["index"] == device_index), None)
        return device or {}

    def _resample_audio(self, audio_data: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        """Resample audio data from source_rate to target_rate"""
        if source_rate == target_rate:
            return audio_data
        
        if not _HAS_SCIPY:
            logger.warning("Scipy not available, using simple resampling")
            # Simple linear interpolation as fallback
            ratio = target_rate / source_rate
            new_length = int(len(audio_data) * ratio)
            indices = np.linspace(0, len(audio_data) - 1, new_length)
            return np.interp(indices, np.arange(len(audio_data)), audio_data)
        
        try:
            # Use scipy for high-quality resampling
            resample_ratio = target_rate / source_rate
            new_length = int(len(audio_data) * resample_ratio)
            return signal.resample(audio_data, new_length)
        except Exception as e:
            logger.error(f"Scipy resampling failed: {e}, falling back to simple resampling")
            ratio = target_rate / source_rate
            new_length = int(len(audio_data) * ratio)
            indices = np.linspace(0, len(audio_data) - 1, new_length)
            return np.interp(indices, np.arange(len(audio_data)), audio_data)

    # ── Recording loop ────────────────────────────────────────────────────────

    def _record_loop(self):
        buf: list[np.ndarray] = []

        def callback(indata: np.ndarray, frames: int, time_info, status):
            if status:
                logger.warning(f"Audio status: {status}")

            mono = indata[:, 0] if indata.ndim > 1 else indata.flatten()

            # Emit VU level
            rms = float(np.sqrt(np.mean(mono ** 2)))
            normalized = min(rms * 10, 1.0)
            self.level_changed.emit(normalized)

            buf.append(mono.copy())

        try:
            # Use device's native sample rate for better quality, then resample if needed
            device_info = self.get_device_info()
            native_rate = device_info.get("default_rate", 44100)
            
            with sd.InputStream(
                samplerate=native_rate,
                channels=1,
                dtype="float32",
                device=self._device,
                blocksize=1024,
                callback=callback,
            ):
                logger.info(f"InputStream opened at {native_rate}Hz")
                while self._recording:
                    sd.sleep(100)
            
            # Emit final buffer once recording stops
            if buf:
                pcm = np.concatenate(buf)
                
                # Resample if necessary
                if self._auto_resample and native_rate != self._target_rate:
                    logger.info(f"Resampling from {native_rate}Hz to {self._target_rate}Hz")
                    pcm = self._resample_audio(pcm, native_rate, self._target_rate)
                
                pcm_bytes = (pcm * 32767).astype(np.int16).tobytes()
                logger.info(f"Emitting full buffered recording: {len(pcm_bytes)} bytes at {self._target_rate}Hz")
                self.chunk_ready.emit(pcm_bytes, self._target_rate)
        except Exception as e:
            logger.error(f"exception in record loop: {e}")
            self.error_occurred.emit(str(e))
            self._recording = False

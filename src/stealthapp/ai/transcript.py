from __future__ import annotations

"""Transcription worker that uses a subprocess to isolate native model code.

Parent spawns `_transcription_process.py` (lightweight) and sends JSON lines
to stdin. The child loads `faster_whisper` only after receiving a `load`
command, preventing crashes during process startup.
"""
import os
import sys
import json
import base64
import time
import queue
import threading
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QMutex, QMutexLocker
from stealthapp.core.logger import get_logger

logger = get_logger(__name__)


class TranscriptionWorker(QObject):
    text_ready = pyqtSignal(str)
    silence_timeout = pyqtSignal()
    model_loaded = pyqtSignal(bool, str)

    def __init__(self, model_size: str = "base", debug: bool = False) -> None:
        super().__init__()
        self._model_size = model_size
        self._debug = debug
        self._proc = None
        self._reader_thread = None
        self.mutex = QMutex()
        self._loading = False
        self._ready = False
        self._send_times = queue.Queue()

        # State
        self._is_active = True
        self.last_activity = time.time()
        self.silence_threshold_secs = 20
        self.min_speech_level = 0.005

    @property
    def is_active(self) -> bool:
        locker = QMutexLocker(self.mutex)
        return self._is_active

    @is_active.setter
    def is_active(self, value: bool):
        locker = QMutexLocker(self.mutex)
        self._is_active = value

    @pyqtSlot()
    def load_model(self) -> None:
        """Spawn subprocess and ask it to load the model."""
        if self._proc is not None or self._loading:
            return
        self._loading = True
        self._load_start_time = time.time()

        script = os.path.join(os.path.dirname(__file__), "_transcription_process.py")
        if not os.path.exists(script):
            self.model_loaded.emit(False, f"worker script not found: {script}")
            return

        try:
            import subprocess

            self._proc = subprocess.Popen(
                [sys.executable, script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            def reader():
                try:
                    for line in self._proc.stdout:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        if obj.get("status") == "ready":
                            elapsed = time.time() - self._load_start_time
                            logger.info(f"[Transcription] Model loaded in {elapsed:.2f}s")
                            self._ready = True
                            self._loading = False
                            self.model_loaded.emit(True, "")
                        if "text" in obj:
                            try:
                                sent_time = self._send_times.get_nowait()
                                elapsed = time.time() - sent_time
                                text_out = obj.get("text", "")
                                logger.info(f"[Transcription] Output: {text_out}")
                                logger.info(f"[Transcription] Response Time: {elapsed:.2f}s")
                            except queue.Empty:
                                pass
                                
                            text = obj.get("text", "")
                            if text:
                                self.text_ready.emit(text)
                                try:
                                    self._write_transcript_to_file(text)
                                except Exception as e:
                                    logger.error(f"write file error: {e}")
                        if "error" in obj:
                            self._loading = False
                            self._ready = False
                            self.model_loaded.emit(False, obj.get("error", ""))
                except Exception as e:
                    logger.error(f"reader thread error: {e}")

            self._reader_thread = threading.Thread(target=reader, daemon=True)
            self._reader_thread.start()
            logger.info(f"reader thread started for pid={getattr(self._proc, 'pid', None)}")

            # start a monitor to detect unexpected subprocess exit
            def monitor():
                try:
                    while True:
                        if self._proc is None:
                            break
                        rc = self._proc.poll()
                        if rc is not None:
                            logger.error(f"subprocess exited with code {rc}")
                            self._ready = False
                            self._loading = False
                            try:
                                self.model_loaded.emit(False, f"subprocess exited: {rc}")
                            except Exception:
                                pass
                            break
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"monitor thread error: {e}")

            tmon = threading.Thread(target=monitor, daemon=True)
            tmon.start()

            # ask subprocess to load the model
            try:
                load_cmd = json.dumps({"cmd": "load", "model": self._model_size}) + "\n"
                self._proc.stdin.write(load_cmd)
                self._proc.stdin.flush()
            except Exception as e:
                logger.error(f"failed to send load command: {e}")
                self.model_loaded.emit(False, str(e))

        except Exception as e:
            logger.error(f"failed to start subprocess: {e}")
            self._proc = None
            self.model_loaded.emit(False, str(e))

    def _send_transcribe(self, pcm_bytes: bytes, rate: int) -> bool:
        if self._proc is None or self._proc.stdin is None:
            return False
        try:
            b64 = base64.b64encode(pcm_bytes).decode()
            obj = {"cmd": "transcribe", "pcm": b64, "rate": rate}
            self._proc.stdin.write(json.dumps(obj) + "\n")
            self._proc.stdin.flush()
            self._send_times.put(time.time())
            return True
        except Exception as e:
            logger.error(f"send failed: {e}")
            # if the subprocess is broken, clear the reference so caller can retry
            try:
                if isinstance(e, (BrokenPipeError, ConnectionResetError)):
                    self._proc = None
            except Exception:
                pass
            return False

    def _validate_audio(self, pcm_bytes: bytes, rate: int) -> bool:
        if not pcm_bytes:
            logger.warning("empty pcm_bytes")
            return False
        if not isinstance(rate, int) or rate <= 0:
            logger.warning(f"invalid sample rate: {rate}")
            return False
        return True

    def _write_transcript_to_file(self, text: str) -> None:
        """Append a timestamped transcript line to a transcripts.txt file in the project root."""
        if not self._debug:
            return
        try:
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            path = os.path.join(root, "transcripts.txt")
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{ts} {text}\n")
            logger.info(f"wrote transcript to: {path}")
        except Exception as e:
            logger.error(f"failed to write transcript: {e}")

    @pyqtSlot(bytes, int)
    def process_chunk(self, pcm_bytes: bytes, rate: int) -> None:
        if not self.is_active:
            return
        if not self._validate_audio(pcm_bytes, rate):
            logger.warning("dropping invalid audio chunk")
            return
        logger.info(f"processing chunk size={len(pcm_bytes)} rate={rate}")
        sent = self._send_transcribe(pcm_bytes, rate)
        if not sent:
            logger.warning("chunk not sent (no subprocess or send failure)")

    def shutdown(self) -> None:
        try:
            if self._proc and self._proc.stdin:
                self._proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                self._proc.stdin.flush()
        except Exception:
            pass
        try:
            if self._proc:
                self._proc.terminate()
        except Exception:
            pass

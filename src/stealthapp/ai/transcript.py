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
import threading
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QMutex, QMutexLocker


class TranscriptionWorker(QObject):
    text_ready = pyqtSignal(str)
    silence_timeout = pyqtSignal()
    model_loaded = pyqtSignal(bool, str)

    def __init__(self, model_size: str = "base") -> None:
        super().__init__()
        self._model_size = model_size
        self._proc = None
        self._reader_thread = None
        self.mutex = QMutex()
        self._loading = False
        self._ready = False

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
                            self._ready = True
                            self._loading = False
                            self.model_loaded.emit(True, "")
                        if "text" in obj:
                            text = obj.get("text", "")
                            if text:
                                self.text_ready.emit(text)
                                try:
                                    self._write_transcript_to_file(text)
                                except Exception as e:
                                    print(f"[TranscriptionWorker] write file error: {e}")
                                try:
                                    self._send_to_ollama_async(text)
                                except Exception as e:
                                    print(f"[TranscriptionWorker] schedule ollama send failed: {e}")
                        if "error" in obj:
                            self._loading = False
                            self._ready = False
                            self.model_loaded.emit(False, obj.get("error", ""))
                except Exception as e:
                    print(f"[TranscriptionWorker] reader thread error: {e}")

            self._reader_thread = threading.Thread(target=reader, daemon=True)
            self._reader_thread.start()
            print(f"[TranscriptionWorker] reader thread started for pid={getattr(self._proc, 'pid', None)}")

            # start a monitor to detect unexpected subprocess exit
            def monitor():
                try:
                    while True:
                        if self._proc is None:
                            break
                        rc = self._proc.poll()
                        if rc is not None:
                            print(f"[TranscriptionWorker] subprocess exited with code {rc}")
                            self._ready = False
                            self._loading = False
                            try:
                                self.model_loaded.emit(False, f"subprocess exited: {rc}")
                            except Exception:
                                pass
                            break
                        time.sleep(1)
                except Exception as e:
                    print(f"[TranscriptionWorker] monitor thread error: {e}")

            tmon = threading.Thread(target=monitor, daemon=True)
            tmon.start()

            # ask subprocess to load the model
            try:
                load_cmd = json.dumps({"cmd": "load", "model": self._model_size}) + "\n"
                self._proc.stdin.write(load_cmd)
                self._proc.stdin.flush()
            except Exception as e:
                print(f"[TranscriptionWorker] failed to send load command: {e}")
                self.model_loaded.emit(False, str(e))

        except Exception as e:
            print(f"[TranscriptionWorker] failed to start subprocess: {e}")
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
            return True
        except Exception as e:
            print(f"[TranscriptionWorker] send failed: {e}")
            # if the subprocess is broken, clear the reference so caller can retry
            try:
                if isinstance(e, (BrokenPipeError, ConnectionResetError)):
                    self._proc = None
            except Exception:
                pass
            return False

    def _validate_audio(self, pcm_bytes: bytes, rate: int) -> bool:
        if not pcm_bytes:
            print("[TranscriptionWorker] warning: empty pcm_bytes")
            return False
        if not isinstance(rate, int) or rate <= 0:
            print(f"[TranscriptionWorker] warning: invalid sample rate: {rate}")
            return False
        return True

    def _write_transcript_to_file(self, text: str) -> None:
        """Append a timestamped transcript line to a transcripts.txt file in the project root."""
        try:
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            path = os.path.join(root, "transcripts.txt")
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{ts} {text}\n")
            print(f"[TranscriptionWorker] wrote transcript to: {path}")
        except Exception as e:
            print(f"[TranscriptionWorker] failed to write transcript: {e}")

    def _send_to_ollama_async(self, text: str) -> None:
        """Non-blocking stub: attempt to send transcript to Ollama via `ollama_client.send_to_ollama` if available.

        This is a best-effort, non-fatal call. Implement `send_to_ollama(text)` in
        `src/stealthapp/ai/ollama_client.py` to hook into the real Ollama flow.
        """
        def task():
            try:
                try:
                    from stealthapp.ai import ollama_client as ollama
                except Exception:
                    print("[TranscriptionWorker] ollama_client import failed or not present")
                    return
                if hasattr(ollama, "send_to_ollama"):
                    try:
                        ollama.send_to_ollama(text)
                    except Exception as e:
                        print(f"[TranscriptionWorker] ollama send error: {e}")
                else:
                    print("[TranscriptionWorker] ollama_client.send_to_ollama not implemented")
            except Exception as e:
                print(f"[TranscriptionWorker] unexpected error in ollama task: {e}")

        t = threading.Thread(target=task, daemon=True)
        t.start()

    def process_chunk(self, pcm_bytes: bytes, rate: int) -> None:
        if not self.is_active:
            return
        if not self._validate_audio(pcm_bytes, rate):
            print("[TranscriptionWorker] dropping invalid audio chunk")
            return
        print(f"[TranscriptionWorker] processing chunk size={len(pcm_bytes)} rate={rate}")
        sent = self._send_transcribe(pcm_bytes, rate)
        if not sent:
            print("[TranscriptionWorker] chunk not sent (no subprocess or send failure)")

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

"""
OllamaClient — thin async wrapper around the Ollama /api/chat endpoint.
Streams tokens back via a Qt signal so the UI updates incrementally.
"""

from __future__ import annotations
import json, threading
from PyQt6.QtCore import QObject, pyqtSignal

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


class OllamaClient(QObject):
    token_received  = pyqtSignal(str)    # incremental token
    response_done   = pyqtSignal(str)    # full response when complete
    error_occurred  = pyqtSignal(str)
    status_changed  = pyqtSignal(str)    # "thinking" / "ready" / "offline"

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._base   = config.get("ollama_base_url", "http://localhost:11434").rstrip("/")
        self._model  = config.get("ollama_model", "llama3")
        self._system = config.get("ollama_system_prompt", "You are a concise gaming assistant.")
        self._history: list[dict] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def chat(self, user_message: str):
        """Send a message. Streams response tokens via token_received signal."""
        if not _HAS_HTTPX:
            self.error_occurred.emit("httpx not installed.\nRun: pip install httpx")
            return
        self._history.append({"role": "user", "content": user_message})
        threading.Thread(target=self._stream_chat, args=(user_message,), daemon=True).start()

    def clear_history(self):
        self._history.clear()

    def set_model(self, model: str):
        self._model = model
        self.config.set("ollama_model", model)

    def ping(self):
        """Check if Ollama is running. Emits status_changed."""
        threading.Thread(target=self._ping, daemon=True).start()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _ping(self):
        try:
            with httpx.Client(timeout=3) as c:
                r = c.get(f"{self._base}/api/tags")
            if r.status_code == 200:
                self.status_changed.emit("ready")
            else:
                self.status_changed.emit("offline")
        except Exception:
            self.status_changed.emit("offline")

    def _stream_chat(self, user_message: str):
        self.status_changed.emit("thinking")
        messages = [{"role": "system", "content": self._system}] + self._history
        full = ""
        try:
            with httpx.Client(timeout=60) as c:
                with c.stream(
                    "POST",
                    f"{self._base}/api/chat",
                    json={"model": self._model, "messages": messages, "stream": True},
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = data.get("message", {}).get("content", "")
                        if token:
                            full += token
                            self.token_received.emit(token)
                        if data.get("done"):
                            break
            self._history.append({"role": "assistant", "content": full})
            self.response_done.emit(full)
            self.status_changed.emit("ready")
        except httpx.ConnectError:
            self.error_occurred.emit("Cannot connect to Ollama.\nMake sure `ollama serve` is running.")
            self.status_changed.emit("offline")
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.status_changed.emit("ready")

"""
OllamaClient — thin async wrapper around the Ollama /api/chat endpoint.
Streams tokens back via a Qt signal so the UI updates incrementally.
"""

from __future__ import annotations
import json, threading, time
from PyQt6.QtCore import pyqtSignal
from stealthapp.ai.base import AIEngine
from stealthapp.core.logger import get_logger

logger = get_logger(__name__)

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


class OllamaClient(AIEngine):
    def __init__(self, config):
        import time
        start_init = time.time()
        super().__init__()
        self.config = config
        self._base   = config.get("ollama_base_url", "http://localhost:11434").rstrip("/")
        self._model  = config.get("ollama_model", "llama3")
        self._system = config.get("ollama_system_prompt")
        logger.info(f"OllamaClient initialized with base={self._base} model={self._model}")
        self._history: list[dict] = []
        elapsed = time.time() - start_init
        logger.info(f"[OllamaClient] Initialized in {elapsed:.4f}s")

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
        logger.info("ping() scheduling background check")
        threading.Thread(target=self._ping, daemon=True).start()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _ping(self):
        import time
        start_time = time.time()
        logger.info("_ping start")
        try:
            with httpx.Client(timeout=3) as c:
                r = c.get(f"{self._base}/api/tags")
            if r.status_code == 200:
                self.status_changed.emit("ready")
            else:
                self.status_changed.emit("offline")
        except Exception:
            self.status_changed.emit("offline")
        elapsed = time.time() - start_time
        logger.info(f"_ping done in {elapsed:.2f}s")

    def _stream_chat(self, user_message: str):
        self.status_changed.emit("thinking")
        messages = [{"role": "system", "content": self._system}] + self._history
        
        start_time = time.time()
        logger.info(f"[Ollama] Input: {user_message}")
        
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
            
            elapsed = time.time() - start_time
            logger.info(f"[Ollama] Output: {full}")
            logger.info(f"[Ollama] Response Time: {elapsed:.2f}s")
            logger.debug(f"History updated: {self._history}")
        except httpx.ConnectError:
            self.error_occurred.emit("Cannot connect to Ollama.\nMake sure `ollama serve` is running.")
            self.status_changed.emit("offline")
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.status_changed.emit("ready")

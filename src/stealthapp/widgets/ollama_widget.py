"""
OllamaWidget — chat interface connected to a local Ollama instance.
Streams responses token-by-token.
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QScrollArea, QSizePolicy, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QThread, QTimer
from stealthapp.ai.factory import AIEngineFactory
from stealthapp.core.logger import get_logger
import httpx

logger = get_logger(__name__)

_BUBBLE_USER = """
    QLabel {
        background: rgba(120,200,255,0.12);
        color: rgba(255,255,255,0.9);
        font-size: 11px;
        font-family: 'Segoe UI', sans-serif;
        border-radius: 8px;
        padding: 6px 10px;
    }
"""
_BUBBLE_AI = """
    QLabel {
        background: rgba(255,255,255,0.05);
        color: rgba(200,255,200,0.9);
        font-size: 11px;
        font-family: 'Segoe UI', sans-serif;
        border-radius: 8px;
        padding: 6px 10px;
    }
"""


class _Bubble(QLabel):
    def __init__(self, text: str, is_user: bool):
        super().__init__(text)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(_BUBBLE_USER if is_user else _BUBBLE_AI)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)


class _ModelFetcher(QThread):
    """Background thread that fetches installed Ollama models via httpx."""
    models_fetched = pyqtSignal(list)

    def __init__(self, base_url: str):
        super().__init__()
        self._base_url = base_url.rstrip("/")

    def run(self):
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self._base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    names = [m.get("name", "") for m in data.get("models", [])]
                    self.models_fetched.emit([n for n in names if n])
                else:
                    logger.error(f"[ModelFetcher] status={resp.status_code}")
                    self.models_fetched.emit([])
        except Exception as e:
            logger.error(f"[ModelFetcher] failed: {e}")
            self.models_fetched.emit([])


class OllamaWidget(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        logger.info("__init__ start")
        self._client = AIEngineFactory.create_ai_engine(config)
        self._client.token_received.connect(self._on_token)
        self._client.response_done.connect(self._on_done)
        self._client.error_occurred.connect(self._on_error)
        self._client.status_changed.connect(self._on_status)
        self._current_bubble: _Bubble | None = None
        self._current_text = ""

        self._build()
        # Load available Ollama models asynchronously
        self._load_available_models()

        if config.get("ollama_enabled", True):
            logger.info("pinging Ollama")
            self._client.ping()
        logger.info("__init__ done")

    def _build(self):
        lo = QVBoxLayout(self); lo.setContentsMargins(0,0,0,0); lo.setSpacing(0)
        self.setStyleSheet("background:transparent;")

        # Header
        hdr = QWidget(); hdr.setStyleSheet("background:rgba(255,255,255,0.03);")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(12,5,12,5)
        title = QLabel("OLLAMA")
        title.setStyleSheet("color:rgba(255,255,255,0.35);font-size:9px;font-family:'Consolas',monospace;letter-spacing:2px;background:transparent;")
        hl.addWidget(title); hl.addStretch()

        # Model selection combo box
        self._model_combo = QComboBox()
        self._model_combo.setStyleSheet("color:rgba(255,255,255,0.9);font-size:9px;font-family:'Consolas',monospace;background:rgba(255,255,255,0.07);border:none;border-radius:3px;padding:2px 4px;")
        hl.addWidget(self._model_combo)
        # Description label for selected model
        self._model_desc_lbl = QLabel()
        self._model_desc_lbl.setStyleSheet("color:rgba(255,255,255,0.5);font-size:8px;font-family:'Consolas',monospace;background:transparent;")
        hl.addWidget(self._model_desc_lbl)
        # Connect change signal
        self._model_combo.currentTextChanged.connect(self._on_model_change)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color:rgba(255,255,255,0.2);font-size:10px;background:transparent;margin-left:6px;")
        hl.addWidget(self._status_dot)

        clear_btn = QPushButton("✕ clear")
        clear_btn.setFixedSize(52, 18)
        clear_btn.setStyleSheet("QPushButton{background:rgba(255,255,255,0.06);color:rgba(255,255,255,0.4);border:none;border-radius:3px;font-size:9px;}QPushButton:hover{background:rgba(255,255,255,0.14);}")
        clear_btn.clicked.connect(self._clear)
        hl.addWidget(clear_btn)
        lo.addWidget(hdr)

        # Message scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setMinimumHeight(140)
        self._scroll.setStyleSheet("""
            QScrollArea{border:none;background:transparent;}
            QScrollBar:vertical{background:rgba(255,255,255,0.05);width:4px;border-radius:2px;}
            QScrollBar::handle:vertical{background:rgba(255,255,255,0.2);border-radius:2px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
        """)

        self._msg_container = QWidget(); self._msg_container.setStyleSheet("background:transparent;")
        self._msg_lo = QVBoxLayout(self._msg_container)
        self._msg_lo.setContentsMargins(10,6,10,6); self._msg_lo.setSpacing(6)
        self._msg_lo.addStretch()

        self._placeholder = QLabel("Ask Ollama anything…\nMake sure `ollama serve` is running.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.setStyleSheet("color:rgba(255,255,255,0.18);font-size:10px;font-family:'Consolas',monospace;padding:12px;background:transparent;")
        self._msg_lo.insertWidget(0, self._placeholder)

        self._scroll.setWidget(self._msg_container)
        lo.addWidget(self._scroll)

        # Input row
        input_row = QWidget(); input_row.setStyleSheet("background:rgba(255,255,255,0.03);")
        il = QHBoxLayout(input_row); il.setContentsMargins(8,6,8,6); il.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask something...")
        self._input.setStyleSheet("""
            QLineEdit {
                background: rgba(255,255,255,0.07);
                color: rgba(255,255,255,0.9);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-family: 'Segoe UI', sans-serif;
            }
            QLineEdit:focus { border-color: rgba(120,200,255,0.4); }
        """)
        self._input.returnPressed.connect(self._send)
        il.addWidget(self._input)

        send_btn = QPushButton("↵")
        send_btn.setFixedSize(28, 26)
        send_btn.setStyleSheet("""
            QPushButton{background:rgba(120,200,255,0.15);color:rgba(120,200,255,0.9);border:none;border-radius:5px;font-size:14px;}
            QPushButton:hover{background:rgba(120,200,255,0.3);}
            QPushButton:disabled{opacity:0.3;}
        """)
        send_btn.clicked.connect(self._send)
        self._send_btn = send_btn
        il.addWidget(send_btn)
        lo.addWidget(input_row)

    def _send(self):
        text = self._input.text().strip()
        if not text: return
        self._input.clear()
        self._send_btn.setEnabled(False)
        if self._placeholder.isVisible(): self._placeholder.hide()

        self._add_bubble(text, is_user=True)

        # Placeholder AI bubble for streaming
        self._current_text = ""
        self._current_bubble = _Bubble("…", is_user=False)
        self._msg_lo.insertWidget(self._msg_lo.count()-1, self._current_bubble)
        self._scroll_bottom()

        self._client.chat(text)

    @pyqtSlot(str)
    def receive_transcription(self, text: str):
        if not text: return
        try:
            logger.info(f"[OllamaWidget] Receiving transcribed text: {text}")
            current_text = self._input.text()
            if current_text:
                self._input.setText(current_text + " " + text)
            else:
                self._input.setText(text)
            self._send()
            logger.info("[OllamaWidget] Successfully dispatched transcribed text to Ollama chat")
        except Exception as e:
            logger.error(f"[OllamaWidget] Failed to process incoming transcription: {e}")

    @pyqtSlot(str)
    def receive_ocr(self, text: str):
        if not text: return
        try:
            logger.info(f"[OllamaWidget] Receiving OCR text: {len(text)} chars")
            prompt = self.config.get("ollama_ocr_prompt")
            if prompt is None:
                prompt = ""
            prompt = prompt + f"{text}\n---\n"
            self._input.setText(prompt)
            logger.info(f"[OllamaWidget] Prepared prompt for OCR text: {prompt[:200]}...")
            self._send()
            logger.info("[OllamaWidget] Successfully dispatched OCR text to Ollama chat")
        except Exception as e:
            logger.error(f"[OllamaWidget] Failed to process incoming OCR text: {e}")

    @pyqtSlot(str)
    def _on_token(self, token: str):
        self._current_text += token
        if self._current_bubble:
            self._current_bubble.setText(self._current_text)
        self._scroll_bottom()

    @pyqtSlot(str)
    def _on_done(self, full: str):
        self._current_bubble = None
        self._current_text = ""
        self._send_btn.setEnabled(True)

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._add_bubble(f"⚠ {msg}", is_user=False)
        self._current_bubble = None
        self._send_btn.setEnabled(True)

    @pyqtSlot(str)
    def _on_status(self, status: str):
        colors = {"ready": "rgba(80,200,120,0.9)", "thinking": "rgba(255,200,50,0.9)", "offline": "rgba(255,80,80,0.7)"}
        self._status_dot.setStyleSheet(f"color:{colors.get(status,'rgba(255,255,255,0.2)')};font-size:10px;background:transparent;margin-left:6px;")

    def _add_bubble(self, text: str, is_user: bool):
        b = _Bubble(text, is_user)
        self._msg_lo.insertWidget(self._msg_lo.count()-1, b)
        self._scroll_bottom()

    def _clear(self):
        self._client.clear_history()
        for i in reversed(range(self._msg_lo.count())):
            w = self._msg_lo.itemAt(i).widget()
            if w and w is not self._placeholder: w.deleteLater()
        self._placeholder.show()

    def _scroll_bottom(self):
        QTimer.singleShot(40, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))

    # ---------------------------------------------------------------------
    # Model selection handling (background QThread)
    # ---------------------------------------------------------------------
    def _on_model_change(self, model_name: str):
        """Handle user selecting a different model from the combo box."""
        logger.info(f"[OllamaWidget] Model changed to {model_name}")
        # Update client and persist selection
        self._client.set_model(model_name)
        self.config.set("ollama_model", model_name)
        # Update description label
        desc = self._MODEL_DESCRIPTIONS.get(model_name, "No description available")
        self._model_desc_lbl.setText(desc)

    def _load_available_models(self):
        """Spawn a background QThread to fetch installed Ollama models."""
        base_url = self.config.get("ollama_base", "http://localhost:11434")
        self._model_fetcher = _ModelFetcher(base_url)
        self._model_fetcher.models_fetched.connect(self._on_models_fetched)
        self._model_fetcher.start()

    @pyqtSlot(list)
    def _on_models_fetched(self, models: list):
        """Populate combo box once background fetch completes."""
        self._model_combo.clear()
        if models:
            self._model_combo.addItems(models)
            current = self.config.get("ollama_model", "llama3")
            if current in models:
                self._model_combo.setCurrentText(current)
            else:
                self._model_combo.setCurrentIndex(0)
            self._on_model_change(self._model_combo.currentText())
        else:
            # Fallback: add the configured model so the combo isn't empty
            fallback = self.config.get("ollama_model", "llama3")
            self._model_combo.addItem(fallback)
            self._model_combo.setCurrentText(fallback)

    # Mapping of known model names to short descriptions
    _MODEL_DESCRIPTIONS = {
        "llama3": "General‑purpose chat model",
        "llama3:8b": "General‑purpose (8 B params)",
        "llama3:70b": "High‑capability large model",
        "codellama": "Optimized for coding tasks",
        "codellama:7b": "Lightweight coding model",
        "codellama:34b": "High‑accuracy coding model",
        "mistral": "Fast & lightweight",
        "mistral:7b": "Fast & lightweight (7 B)",
        "mixtral": "Mixture‑of‑experts, strong reasoning",
        "gemma": "Google Gemma model",
        "gemma:2b": "Ultra‑lightweight Gemma",
        "gemma:7b": "Balanced Gemma model",
        "phi3": "Microsoft Phi‑3, small but capable",
        "phi3:mini": "Ultra‑fast Phi‑3 mini",
        "qwen": "Alibaba Qwen, multilingual",
        "deepseek-coder": "Optimized for code generation",
        "neural-chat": "Intel neural chat model",
        "orca-mini": "Fast, lightweight Q&A model",
    }

from __future__ import annotations
from stealthapp.ai.base import AIEngine, Transcriber, OCRScanner
from stealthapp.ai.ollama_client import OllamaClient
from stealthapp.ai.transcript import TranscriptionWorker
from stealthapp.ai.ocr_worker import OCRWorker

class AIEngineFactory:
    @staticmethod
    def create_ai_engine(config) -> AIEngine:
        engine_type = config.get("ai_engine", "ollama").lower()
        if engine_type == "ollama":
            return OllamaClient(config)
        else:
            # Fallback to Ollama or raise error
            return OllamaClient(config)

    @staticmethod
    def create_transcriber(config) -> Transcriber:
        engine_type = config.get("transcriber_engine", "whisper").lower()
        if engine_type == "whisper":
            return TranscriptionWorker(
                config.get("whisper_model", "base"),
                initial_prompt=config.get("whisper_initial_prompt", "This is a conversation in Indian English."),
                debug=config.get("debug", False)
            )
        else:
            return TranscriptionWorker(
                config.get("whisper_model", "base"),
                initial_prompt=config.get("whisper_initial_prompt", "This is a conversation in Indian English."),
                debug=config.get("debug", False)
            )

    @staticmethod
    def create_ocr_scanner(config) -> OCRScanner:
        engine_type = config.get("ocr_engine", "tesseract").lower()
        if engine_type == "tesseract":
            return OCRWorker()
        else:
            return OCRWorker()

"""Config loader — reads config.json, merges with defaults, persists changes."""

from __future__ import annotations
import json, os
from typing import Any


DEFAULTS: dict[str, Any] = {
    "overlay_x": 20,
    "overlay_y": 20,
    "overlay_width": 440,
    "overlay_height": 750,
    "opacity": 0.93,
    "stats_file": "stats.json",
    "twitch_enabled": False,
    "twitch_channel": "",
    "twitch_token": "",
    "twitch_bot_name": "",
    "youtube_enabled": False,
    "youtube_video_id": "",
    "max_chat_messages": 60,
    "audio_enabled": True,
    "audio_device_index": None,
    "audio_sample_rate": 16000,
    "audio_chunk_seconds": 5,
    "ollama_enabled": True,
    "ollama_base_url": "http://localhost:11434",
    "ollama_model": "llama3",
    "ollama_system_prompt": (
        "You are a concise gaming assistant. Answer in 1-2 sentences."
    ),
}


class Config:
    def __init__(self, path: str = "config.json"):
        self._path = path
        self._data: dict[str, Any] = {**DEFAULTS}
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._data.update(json.load(f))
            except json.JSONDecodeError as e:
                print(f"[Config] JSON error in {self._path}: {e}")
        else:
            self._save()

    def _save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, fallback: Any = None) -> Any:
        return self._data.get(key, fallback if fallback is not None else DEFAULTS.get(key))

    def set(self, key: str, value: Any):
        self._data[key] = value
        self._save()

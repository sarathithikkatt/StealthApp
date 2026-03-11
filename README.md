# StealthApp 🎮

Transparent, always-on-top gaming overlay — **completely invisible to screen capture** (OBS, Discord, Zoom, Twitch streams).

## Features
- ✅ Invisible to all screen capture tools (Windows `WDA_EXCLUDEFROMCAPTURE`)
- ✅ Live game stat panel — auto-reloads from `stats.json`
- ✅ Twitch IRC + YouTube live chat
- ✅ Microphone capture with VU meter (hook Whisper for STT)
- ✅ Ollama AI chat — streams responses from your local model
- ✅ Click-through by default, interactive on ALT hold
- ✅ Drag to reposition (Ctrl+drag), saves position

---

## Quick Start

**Windows:**
```bat
setup.bat
.venv\Scripts\activate
stealthapp
```

**macOS / Linux:**
```bash
chmod +x setup.sh && ./setup.sh
source .venv/bin/activate
stealthapp
```

---

## Hotkeys

| Key | Action |
|-----|--------|
| **Hold ALT** | Enter interactive mode (click buttons, scroll chat, type in Ollama) |
| **Release ALT** | Return to click-through (game gets all inputs) |
| **Ctrl + drag** | Move the overlay |
| **Ctrl + H** | Toggle visibility |

---

## Configuration (`config.json`)

Created automatically from `config.example.json` on first run.

```json
{
  "twitch_channel": "your_channel",
  "youtube_video_id": "VIDEO_ID",
  "ollama_model": "llama3",
  "audio_enabled": true
}
```

---

## Stats Integration

Write to `stats.json` from any script or game tool:

```json
{
  "game": "Valorant",
  "stats": { "KDA": "12/3/7", "HP": "87%", "FPS": "240" },
  "custom": [{ "key": "Agent", "value": "Jett" }]
}
```

The overlay picks up changes instantly via `watchdog`.

---

## Audio / STT

The `AudioWidget` captures mic audio in chunks. To add speech-to-text, edit `widgets/audio_widget.py` → `_on_chunk`:

```python
import whisper, numpy as np
model = whisper.load_model("base")

def _on_chunk(self, pcm: bytes, rate: int):
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32767
    result = model.transcribe(audio, fp16=False)
    # Send to Ollama, display, etc.
    self._client.chat(result["text"])
```

---

## Ollama Setup

```bash
# Install Ollama from https://ollama.com
ollama pull llama3
ollama serve       # Keep this running
```

The overlay auto-detects whether Ollama is online (green dot = connected).

---

## Project Structure

```
stealthapp/
├── pyproject.toml
├── setup.bat / setup.sh
├── config.example.json
├── stats.json
└── src/stealthapp/
    ├── app.py
    ├── __main__.py
    ├── core/
    │   ├── config.py
    │   ├── capture_exclusion.py   ← WDA_EXCLUDEFROMCAPTURE
    │   ├── overlay_window.py      ← ALT pass-through fix
    │   └── stat_watcher.py
    ├── audio/
    │   └── recorder.py            ← sounddevice mic capture
    ├── ai/
    │   └── ollama_client.py       ← streaming Ollama chat
    └── widgets/
        ├── header_bar.py
        ├── stat_panel.py
        ├── chat_widget.py
        ├── audio_widget.py
        └── ollama_widget.py
```

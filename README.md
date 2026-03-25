# StealthApp 🎮

Transparent, always-on-top gaming overlay — designed to be invisible to screen capture tools and provide lightweight in-game overlays (stats, chat, mic VU, and Ollama chat).

Key changes and notes
- The transcription model (`faster-whisper`) is now loaded in a background worker thread so the UI starts immediately.
- The `AudioWidget` can auto-start mic capture; disable this by setting `"audio_enabled": false` in `config.json` if you do not want the mic opened on startup.
- On Windows, installing `sounddevice` via `pip` provides bundled PortAudio DLLs; no extra system install is required in most cases.

Quick Start

Windows (PowerShell):
```powershell
.\setup.bat
.venv\Scripts\Activate.ps1
python -m stealthapp
```

macOS / Linux:
```bash
./setup.sh
source .venv/bin/activate
python -m stealthapp
```

Tips
- To avoid loading the transcription model at startup, set `"audio_enabled": false` in `config.json`.
- If you prefer the UI to start without audio or Ollama checks, set `audio_enabled` and `ollama_enabled` to `false`.

Hotkeys
- Hold ALT: enter interactive mode
- Release ALT: return to click-through
- Ctrl+drag: move overlay
- Ctrl+H: toggle visibility

Configuration (`config.json`)

`config.json` is created from `config.example.json` on first run. Useful keys:
- `twitch_channel`, `youtube_video_id` — chat integration
- `ollama_enabled`, `ollama_base_url`, `ollama_model` — Ollama settings
- `audio_enabled`, `audio_device_index` — microphone capture

Dependencies & Installation
- Install runtime dependencies into the virtual environment:
```powershell
python -m pip install -r requirements.txt
```
Or install individually:
```powershell
python -m pip install PyQt6 watchdog sounddevice numpy faster-whisper httpx av
```

Notes
- `sounddevice` installs PortAudio DLLs on Windows when installed via `pip`.
- `faster-whisper` may require additional runtime libraries depending on platform and performance choices (CPU vs GPU).

Project layout

See `src/stealthapp/` for the application code. The overlay window is implemented in `src/stealthapp/core/overlay_window.py` and the widgets live under `src/stealthapp/widgets/`.

Contributing
- Run `setup.bat` (Windows) or `setup.sh` (macOS/Linux) to create the venv and install editable deps.
- Use `python -m stealthapp` to run from the repo root.

License: MIT


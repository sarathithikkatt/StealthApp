# StealthAssistant 🎮

Transparent, always-on-top gaming overlay — designed to be invisible to screen capture tools and provide lightweight in-game overlays (stats, chat, mic VU, and Ollama chat).

## 📸 Product Preview

<p align="center">
  <img src="https://github.com/user-attachments/assets/6992cfde-910d-4c52-bae0-e30df7436261" width="700"/>
</p>

<p align="center"> <em>Captured using an external device — the overlay remains invisible to screen recording tools</em> </p> 

<p align="center"> <em>"Struggling with success — had to pull out my phone just to prove it exists."</em> </p>
Key changes and notes
- Added Vision/Screen Capture capabilities. You can capture specific windows (Google Chrome, Microsoft Teams) or your entire screen and extract text using OCR (`pytesseract`). This dynamically extracted text is automatically formatted into an interview prompt and sent directly to Ollama.
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

Command-line control
```powershell
python -m stealthapp start
python -m stealthapp status
python -m stealthapp stop
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
python -m pip install PyQt6 watchdog sounddevice numpy faster-whisper httpx av pytesseract pillow
```

System Requirements & External Tools

- **Tesseract OCR**: Required for the Vision widget OCR features (used via `pytesseract`). Install Tesseract on your system and ensure `tesseract` is on your `PATH` or set `TESSDATA_PREFIX` to the tessdata folder.
	- **Windows**: Download the installer (recommended: UB Mannheim build) or use Chocolatey:
		```powershell
		choco install tesseract
		```
	- **macOS**:
		```bash
		brew install tesseract
		```
	- **Debian/Ubuntu**:
		```bash
		sudo apt-get update
		sudo apt-get install -y tesseract-ocr libtesseract-dev
		```
	- To add extra languages (example: Spanish): `sudo apt-get install tesseract-ocr-spa` (package names vary by distro).
	- Verify installation:
		```bash
		tesseract --version
		```

- **Ollama & Model (e.g. lamma3.1:8b)**: The app integrates with an Ollama instance for LLM-based features. Install and run Ollama, then pull the desired model.
	- Install Ollama following the official instructions for your platform (installer/homebrew/choco). Ensure the `ollama` CLI is available.
	- Pull the model (example name provided here as `lamma3.1:8b` — replace with the exact model you want):
		```bash
		ollama pull lamma3.1:8b
		```
	- Start the Ollama daemon if needed:
		```bash
		ollama daemon
		```
	- Configure the model in `config.json` using the `ollama_model` and `ollama_base_url` keys if you use a custom host or model name.
	- Verify by running a quick inference or `ollama list` to see available models.

Notes
- If Ollama or Tesseract are installed in non-standard locations, make sure to update environment variables or the `config.json` entries so the app can find them.
- Model names and availability depend on your Ollama setup and downloaded images; replace `lamma3.1:8b` with the exact model identifier you intend to use.
Notes
- `sounddevice` installs PortAudio DLLs on Windows when installed via `pip`.
- `faster-whisper` may require additional runtime libraries depending on platform and performance choices (CPU vs GPU).

Project layout

See `src/stealthapp/` for the application code. The overlay window is implemented in `src/stealthapp/core/overlay_window.py` and the widgets live under `src/stealthapp/widgets/`.

Contributing
- Run `setup.bat` (Windows) or `setup.sh` (macOS/Linux) to create the venv and install editable deps.
- Use `python -m stealthapp` to run from the repo root.

License: MIT


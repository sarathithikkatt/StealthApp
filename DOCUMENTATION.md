# StealthApp Documentation

## Overview

StealthAssistant is a transparent, always-on-top assistant built to help you when you're in a pinch. It operates discreetly and is designed to remain invisible to screen capture tools, making it ideal for real-time support without disruption.

## Architecture

The application is built using PyQt6 and follows a modular architecture:

- **Core modules**: Handle window management, configuration, and system integration (capture exclusion).
- **AI modules**: Provide audio transcription, OCR text extraction, and Ollama chat functionality.
- **Audio & Vision modules**: Handle microphone recording, window capture processing, and audio/visual pipelines.
- **Widget modules**: UI components exposing the underlying feature logic.

---

## Core Modules

### `stealthapp/__main__.py`
**Command Line Interface**
- Implements `start`, `stop`, and `status` commands.
- **`start`**: On Windows, it tries to use `pythonw.exe` for background execution unless `--foreground` is specified. It writes a PID file to `~/.stealthapp/stealthapp.pid`.
- **`stop`**: Kills the process using the PID from the PID file.
- **`status`**: Checks if the PID is alive.

### `stealthapp/app.py`
**Main application bootstrap module**
- **`run()`** - Application entry point that initializes Qt, loads config, sets up crash handling, and starts the main window.
- **Fault handler** - Enables native crash logging to `crash.log` for debugging segmentation faults.

### `stealthapp/core/config.py`
**Configuration management**
- Loads config from `config.json`, merges with `DEFAULTS`, and saves changes intelligently.
- Manages feature switches like `audio_enabled`, `ollama_enabled`, positional states (`overlay_x`), and hardware target settings.

### `stealthapp/core/overlay_window.py`
**Main transparent overlay window implementation**
- Constructs the UI stacking different widgets (`HeaderBar`, `AudioWidget`, `VisionWidget`, `OllamaWidget`).
- Uses `WS_EX_LAYERED | WS_EX_TRANSPARENT` Win32 API to achieve zero-flicker pass-through mode, with an ALT hotkey to toggle interactivity.

### `stealthapp/core/capture_exclusion.py`
**OS-level screen capture exclusion**
- Uses `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` on Windows, making the app invisible to OBS/Discord stream shares.
- Uses `NSWindowSharingNone` on macOS.

---

## AI Modules

### `stealthapp/ai/ocr_worker.py`
**Background worker for performing OCR on captured screens**
- **`OCRWorker` class**: Subclasses `QThread` and accepts a `QPixmap`.
- Uses `pytesseract` and `PIL.Image` asynchronously to extract structured text. Emits `text_extracted` upon successful parsing to avoid locking the UI thread.

### `stealthapp/ai/transcript.py`
**Transcription worker that isolates audio processing**
- Instantiates a background subprocess (`_transcription_process.py`) to keep the main Qt event loop free of `faster-whisper` ML model loads.
- Emits `text_ready` when transcription finishes successfully.

### `stealthapp/ai/ollama_client.py`
**HTTP streaming client for local Ollama APIs**
- **`OllamaClient` class**: Maintains rolling conversation history and token-by-token streaming API calls to `localhost:11434`.

---

## Widget Modules

### `stealthapp/widgets/vision_widget.py`
**Screen and Target Window Capture**
- UI with specific app targeting buttons: **"Capture Chrome"**, **"Capture Teams"**, and **"Capture Screen"**.
- Employs `ctypes.windll.user32.EnumWindows` to iterate visible user windows looking for Chrome or Teams window handles (`HWND`).
- Fires screenshot capture via PyQt `QApplication.primaryScreen().grabWindow(hwnd)`.
- Passes the result to the `OCRWorker` and delegates extracted text out via `text_extracted`.

### `stealthapp/widgets/audio_widget.py`
**Microphone transcription**
- Simple VU meter alongside "Start Mic" and "Stop Mic" buttons.
- Records local audio in chunks and feeds the `TranscriptionWorker`.

### `stealthapp/widgets/ollama_widget.py`
**Unified AI Chat interface**
- Displays streaming token messages similar to a conventional LLM chat interface.
- Includes `receive_ocr` and `receive_transcription` slots directly connected to the overlay UI elements above it.
- Automatically constructs advanced analytical prompts (specifically, a customized interview solver) when raw text is pushed in from the `VisionWidget`.

---

## Dependencies

- **UI Framework**: `PyQt6`
- **Audio Processing**: `sounddevice`, `numpy`, `faster-whisper`
- **Vision Processing**: `pillow`, `pytesseract` (Requires host Tesseract-OCR binary installation)
- **Networking**: `httpx` (for Ollama HTTP calls)
- **Utilities**: `watchdog`, `av`

---

## Configuration (`config.json`)

Useful keys available for overrides:
- **`ollama_base_url`**: Usually `http://localhost:11434`.
- **`ollama_model`**: The model to use for inferences (e.g., `llama3`).
- **`audio_device_index`**: ID of the targeted capture microphone.

---

## Architecture Notes

### Event Bus Safety
All widget communication occurs exclusively via typed Qt Signal-Slot connections (`pyqtSignal(str)`). Lengthy background events such as OCR and native `faster-whisper` runs are strictly localized inside custom threading primitives (or OS subprocesses).

### Platform Considerations
- **Vision Capture capabilities**: Window handle (HWND) target parsing relies fully on Win32 SDK endpoints and operates gracefully under Windows. Cross-platform environments fallback to simple full-desktop grabbing depending on KDE/Wayland configurations.
- **Native Crash Logs**: Native exceptions are routed securely to local `crash.log`.

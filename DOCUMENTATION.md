# StealthApp Documentation

## Overview

StealthApp is a transparent, always-on-top gaming overlay designed to be invisible to screen capture tools. It provides lightweight in-game overlays for stats, chat, microphone VU meter, and Ollama chat integration.

## Architecture

The application is built using PyQt6 and follows a modular architecture:

- **Core modules**: Handle window management, configuration, and system integration
- **AI modules**: Provide transcription and Ollama chat functionality  
- **Audio modules**: Handle microphone recording and processing
- **Widget modules**: UI components for different overlay features

---

## Core Modules

### `stealthapp/app.py`

**Main application bootstrap module**

- **`run()`** - Application entry point that initializes Qt, loads config, sets up crash handling, and starts the main window
- **Exception handling setup** - Configures global exception hooks for both main thread and background threads
- **Fault handler** - Enables native crash logging to `crash.log` for debugging segmentation faults

### `stealthapp/core/config.py`

**Configuration management**

- **`DEFAULTS`** - Dictionary containing all default configuration values
- **`Config` class**:
  - **`__init__(path)`** - Loads config from JSON file, merges with defaults
  - **`_load()`** - Reads and parses config.json, handles JSON errors gracefully
  - **`_save()`** - Writes current configuration to file
  - **`get(key, fallback)`** - Retrieves configuration value with fallback
  - **`set(key, value)`** - Updates configuration and persists to file

**Configuration keys**:
- Window position/size: `overlay_x`, `overlay_y`, `overlay_width`, `overlay_height`
- Appearance: `opacity`
- Integration toggles: `twitch_enabled`, `youtube_enabled`, `audio_enabled`, `ollama_enabled`
- Audio settings: `audio_device_index`, `audio_sample_rate`, `audio_chunk_seconds`
- Chat settings: `twitch_channel`, `youtube_video_id`, `max_chat_messages`
- Ollama settings: `ollama_base_url`, `ollama_model`, `ollama_system_prompt`

### `stealthapp/core/overlay_window.py`

**Main overlay window implementation**

**Key Functions**:
- **`_init_window()`** - Sets up window flags (frameless, always-on-top, transparent background)
- **`_build_ui()`** - Constructs the UI layout with all widgets
- **`_post_show_setup()`** - Applies capture exclusion and sets up input handling
- **`_enter_interactive()` / `_exit_interactive()`** - Toggle between pass-through and interactive modes
- **`_poll_alt_state()`** - Monitors ALT key state for mode switching
- **`_hotkey_message_loop()`** - Background thread for global Ctrl+H hotkey
- **`_toggle_visibility()`** - Shows/hides the overlay
- **Mouse event handlers** - Implement Ctrl+drag repositioning

**Windows-specific features**:
- Uses Win32 layered window API for zero-flicker input passthrough
- Registers global hotkey for visibility toggle
- Applies capture exclusion to hide from OBS/Discord

### `stealthapp/core/capture_exclusion.py`

**OS-level screen capture exclusion**

- **`apply(hwnd)`** - Main entry point that delegates to platform-specific implementation
- **`_apply_windows(hwnd)`** - Uses `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` on Windows
- **`_apply_macos(hwnd)`** - Uses `NSWindowSharingNone` on macOS via PyObjC
- **`_apply_linux(hwnd)`** - Best-effort implementation (no universal API)

### `stealthapp/core/stat_watcher.py`

**File system watcher for stats.json**

**`StatWatcher` class**:
- **`__init__(filepath)`** - Sets up file watcher and creates default stats file if missing
- **`_write_default()`** - Creates initial stats.json with game/stats/custom structure
- **`_read()`** - Parses stats file and emits signal if changed
- **`start()`** - Starts monitoring (uses watchdog library if available, falls back to polling)
- **`_start_watchdog()`** - Sets up efficient file system monitoring
- **`_start_poll()`** - Fallback polling-based monitoring

**Signals**:
- **`stats_updated`** - Emitted when stats.json content changes

---

## AI Modules

### `stealthapp/ai/_transcription_process.py`

**Subprocess worker for speech transcription**

**Standalone process that isolates native Whisper model loading**:
- **`main()`** - Process entry point, handles JSON command protocol
- **Protocol**: Accepts commands via stdin JSON lines:
  - `{"cmd":"load","model":"base"}` - Loads Whisper model
  - `{"cmd":"transcribe","pcm":"<base64>","rate":16000}` - Transcribes audio chunk
  - `{"cmd":"quit"}` - Exits process
- **Responses**: JSON lines with `{"text":"..."}` or `{"error":"..."}`

### `stealthapp/ai/transcript.py`

**Transcription worker that manages the subprocess**

**`TranscriptionWorker` class**:
- **`__init__(model_size)`** - Sets up worker but delays model loading
- **`load_model()`** - Spawns subprocess and sends load command
- **`process_chunk(pcm_bytes, rate)`** - Sends audio data for transcription
- **`_send_transcribe()`** - Handles base64 encoding and subprocess communication
- **`_validate_audio()`** - Validates audio data before processing
- **`_write_transcript_to_file()`** - Saves transcriptions to transcripts.txt
- **`_send_to_ollama_async()`** - Optional integration with Ollama
- **`shutdown()`** - Cleanly terminates subprocess

**Signals**:
- **`text_ready`** - Emitted when transcription is complete
- **`silence_timeout`** - Emitted when no speech detected
- **`model_loaded`** - Emitted when model loading finishes

### `stealthapp/ai/ollama_client.py`

**HTTP client for Ollama API integration**

**`OllamaClient` class**:
- **`__init__(config)`** - Initializes with Ollama server settings
- **`chat(user_message)`** - Sends message and streams response tokens
- **`ping()`** - Checks if Ollama server is reachable
- **`clear_history()`** - Resets conversation history
- **`set_model(model)`** - Changes the active model
- **`_stream_chat()`** - Handles streaming chat API calls
- **`_ping()`** - Background server availability check

**Signals**:
- **`token_received`** - Individual response tokens for streaming UI
- **`response_done`** - Complete response when finished
- **`error_occurred`** - Connection or API errors
- **`status_changed`** - "ready"/"thinking"/"offline" status updates

---

## Audio Modules

### `stealthapp/audio/recorder.py`

**Microphone audio capture**

**`AudioRecorder` class**:
- **`__init__(config)`** - Sets up recording parameters from config
- **`start()` / `stop()`** - Control recording state
- **`list_devices()`** - Static method to enumerate available microphones
- **`_record_loop()`** - Main recording thread with sounddevice callback
- **`callback()`** - Processes audio chunks, calculates VU levels, emits signals

**Signals**:
- **`chunk_ready`** - Raw PCM audio data bytes and sample rate
- **`level_changed`** - RMS audio level for VU meter (0.0-1.0)
- **`error_occurred`** - Recording errors

---

## Widget Modules

### `stealthapp/widgets/header_bar.py`

**Window header with controls**

**`HeaderBar` class**:
- **`__init__(config)`** - Creates header with title and control buttons
- **UI elements**: StealthApp icon, title, minimize button, close button

**Signals**:
- **`close_clicked`** - User clicked close button
- **`minimize_clicked`** - User clicked minimize button

### `stealthapp/widgets/stat_panel.py`

**Game statistics display**

**`StatPanel` class**:
- **`__init__(config)`** - Creates stats display with game name and stat cards
- **`update_stats(data)`** - Updates display with new stats data
- **`_clear_grid()` / `_clear_custom()`** - Reset display before updates
- **`_Card` class** - Individual stat display widget

**Data format**:
```json
{
  "game": "Game Name",
  "stats": {"fps": 60, "ping": 25},
  "custom": [{"key": "custom", "value": "data"}]
}
```

### `stealthapp/widgets/chat_widget.py`

**Twitch and YouTube live chat integration**

**`ChatWidget` class**:
- **`__init__(config)`** - Sets up chat display and connects to platforms
- **`_connect()`** - Starts background threads for enabled platforms
- **`_on_msg()`** - Handles incoming chat messages
- **`_build()`** - Creates chat UI with scrollable message area

**Background threads**:
- **`_TwitchThread`** - IRC connection to Twitch chat servers
- **`_YouTubeThread`** - Live YouTube chat via pytchat library

**Signals**:
- **`received`** - New chat message (platform, user, message)

### `stealthapp/widgets/audio_widget.py`

**Microphone recording and transcription interface**

**`AudioWidget` class**:
- **`__init__(config)`** - Sets up audio recorder and transcription worker
- **`_start_recording()` / `_stop_recording()`** - Control recording state
- **`_toggle()`** - Handle button clicks
- **`_on_chunk()`** - Receives audio chunks from recorder
- **`_on_text_received()`** - Handles transcribed text
- **`_on_level()`** - Updates VU meter
- **`_auto_start()`** - Automatic start if enabled in config

**Components**:
- **`_VUMeter`** - Visual audio level indicator
- Integration with `AudioRecorder` and `TranscriptionWorker`
- Status indicators and error handling

### `stealthapp/widgets/ollama_widget.py`

**Ollama chat interface**

**`OllamaWidget` class**:
- **`__init__(config)`** - Creates chat UI and connects to Ollama client
- **`_send()`** - Sends user message to Ollama
- **`_on_token()`** - Updates UI with streaming response tokens
- **`_on_done()`** - Handles response completion
- **`_clear()`** - Clears chat history
- **`_add_bubble()`** - Adds message bubble to chat

**UI Components**:
- Scrollable chat area with message bubbles
- Input field with send button
- Status indicators for Ollama connection
- Model display and clear button

---

## Entry Points

### `stealthapp/__main__.py`

**Module entry point for `python -m stealthapp`**

- **`main()`** - Simple wrapper that calls `stealthapp.app.run()`

### `stealthapp/__init__.py`

**Package initialization**

- Defines package version: `__version__ = "0.1.0"`

---

## Configuration

### `config.example.json`

Template configuration file with all available settings:

**Window settings**: position, size, opacity
**Platform integration**: Twitch, YouTube, Ollama enable flags
**Audio settings**: device, sample rate, chunk size
**Chat limits**: maximum message count
**Ollama settings**: server URL, model, system prompt

---

## Dependencies

### Core Dependencies
- **PyQt6** - GUI framework
- **watchdog** - File system monitoring
- **sounddevice** - Audio capture
- **numpy** - Audio processing
- **faster-whisper** - Speech transcription
- **httpx** - HTTP client for Ollama
- **av** - Audio/video utilities

### Optional Dependencies
- **pytchat** - YouTube live chat (if YouTube integration needed)
- **pyobjc-framework-Cocoa** - macOS capture exclusion

---

## Usage

### Installation
```bash
# Windows
.\setup.bat
.venv\Scripts\Activate.ps1
python -m stealthapp

# macOS/Linux
./setup.sh
source .venv/bin/activate
python -m stealthapp
```

### Controls
- **Hold ALT** - Enter interactive mode
- **Release ALT** - Return to click-through mode
- **Ctrl+drag** - Move overlay position
- **Ctrl+H** - Toggle visibility

### Configuration
Edit `config.json` to customize:
- Window appearance and position
- Platform integrations (Twitch, YouTube)
- Audio device and transcription settings
- Ollama server configuration

---

## Architecture Notes

### Thread Safety
- All Qt signal/slot connections ensure thread-safe communication
- Background threads for audio, transcription, chat, and file watching
- Proper cleanup in widget closeEvent handlers

### Error Handling
- Global exception hooks capture crashes
- Subprocess isolation for native model loading
- Graceful fallbacks when optional dependencies missing

### Platform Compatibility
- Windows: Full feature support with Win32 API integration
- macOS: Capture exclusion via PyObjC
- Linux: Best-effort implementation (no universal capture exclusion)

### Performance
- Lazy loading of transcription models
- Efficient file watching vs polling
- Streaming responses for real-time UI updates
- Minimal resource usage when idle

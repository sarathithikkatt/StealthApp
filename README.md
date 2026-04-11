# StealthAssistant 🎮

What if your AI assistant could see exactly what you're seeing and hear exactly what you're saying — and nobody else could tell it was there? StealthAssistant is a screen-invisible desktop overlay that pipes your screen and voice into a local LLM (Ollama), giving you real-time contextual AI responses with nothing leaving your machine.

## 📸 Product Preview

<p align="center">
  <img src="https://github.com/user-attachments/assets/6992cfde-910d-4c52-bae0-e30df7436261" width="700"/>
</p>

<p align="center"> <em>Captured using an external device — the overlay remains invisible to screen recording tools</em> </p> 

<p align="center"> <em>"Struggling with success — had to pull out my phone just to prove it exists."</em> </p>
## 🚀 Features

- **Invisible Overlay**: Screen-invisible desktop overlay using OS-level capture exclusion.
- **Vision & OCR**: Capture specific windows (Chrome, Teams) or the entire screen and extract text using Tesseract OCR.
- **Audio Transcription**: Real-time microphone transcription using `faster-whisper` (runs in a background process).
- **Local AI Integration**: Connects to [Ollama](https://ollama.com/) for private, local LLM responses.
- **Discreet Control**: Hotkeys for toggling visibility and interactivity (ALT, Ctrl+H).

## 🛠️ Installation

### 1. Prerequisites

- **Python 3.11+**: Ensure Python is installed and added to your PATH.
- **Tesseract OCR**: Required for vision features.
  - **Windows**: [Download Installer](https://github.com/UB-Mannheim/tesseract/wiki) or `choco install tesseract`.
  - **macOS**: `brew install tesseract`.
  - **Linux**: `sudo apt install tesseract-ocr`.
- **Ollama**: [Download and Install Ollama](https://ollama.com/).

### 2. Setup

Clone the repository and run the setup script for your platform:

#### Windows (PowerShell)
```powershell
git clone https://github.com/sarathithikkatt/StealthApp.git
cd StealthApp
.\setup.bat
```

#### macOS / Linux (Bash)
```bash
git clone https://github.com/sarathithikkatt/StealthApp.git
cd StealthApp
chmod +x setup.sh
./setup.sh
```

---

## 🏃 Running StealthApp

Before running, ensure your virtual environment is activated:

### Activate Virtual Environment

- **Windows**:
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
- **macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```

### Command-Line Interface

StealthApp provides a built-in CLI for easy management:

- **Start StealthApp (Background)**:
  ```bash
  python -m stealthapp start
  ```
- **Start StealthApp (Foreground)**:
  ```bash
  python -m stealthapp start --foreground
  ```
- **Check Status**:
  ```bash
  python -m stealthapp status
  ```
- **Stop StealthApp**:
  ```bash
  python -m stealthapp stop
  ```

*Note: On Windows, `python -m stealthapp start` uses `pythonw.exe` to run without a console window.*

---

## ⌨️ Hotkeys

- **Hold ALT**: Enter interactive mode (click on buttons/text).
- **Release ALT**: Return to click-through (transparent) mode.
- **Ctrl + Drag**: Move the overlay window.
- **Ctrl + H**: Toggle visibility (Hide/Show).

---

## ⚙️ Configuration

A `config.json` file is generated on the first run. You can customize:
- `ollama_model`: The LLM model to use (e.g., `llama3`).
- `audio_enabled`: Set to `true` to enable microphone transcription.
- `ollama_enabled`: Set to `false` to disable AI features.
- `opacity`: Adjust overlay transparency (0.0 to 1.0).

---

## 🛠️ Project Structure

- `src/stealthapp/`: Core application logic.
- `src/stealthapp/core/`: Window management, config, and OS-level capture exclusion.
- `src/stealthapp/widgets/`: UI components (Vision, Audio, Ollama).
- `src/stealthapp/ai/`: Background workers for OCR, Transcription, and Ollama integration.

## 🤝 Contributing

1. Clone the repository.
2. Run `setup.bat` (Windows) or `setup.sh` (macOS/Linux).
3. Activate the virtual environment.
4. Run in foreground for development: `python -m stealthapp start --foreground`.

## 📄 License

MIT License


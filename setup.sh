#!/usr/bin/env bash
set -e

echo "=== StealthApp Setup ==="

# Find python
PY=$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3 || true)
if [[ -z "$PY" ]]; then
    echo "[ERROR] Python 3.11+ not found."
    exit 1
fi
echo "[1/4] Using: $PY ($($PY --version))"

echo "[2/4] Creating virtual environment..."
if [[ -d .venv ]]; then
    echo "      .venv already exists, skipping."
else
    $PY -m venv .venv
fi

echo "[3/4] Installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e .

echo "[4/4] Creating default config if missing..."
if [[ ! -f config.json ]]; then
    cp config.example.json config.json
    echo "      config.json created. Edit it before running."
fi

echo ""
echo "Setup complete!"
echo "Run:  source .venv/bin/activate && stealthapp"

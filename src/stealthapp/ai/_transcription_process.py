#!/usr/bin/env python
"""Subprocess transcription worker.

Protocol: parent sends JSON per line to stdin:
  {"cmd":"transcribe","pcm":"<base64>","rate":16000}

Child responds with JSON per line:
  {"text":"..."}
  {"error":"..."}

This isolates native crashes inside the subprocess.
"""
import sys
import json
import base64
import traceback

def main():
    model = None
    np = None
    WhisperModel = None

    # Signal started; parent should send a `load` command to load the model.
    print(json.dumps({"status": "started"}), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            cmd = obj.get("cmd")
            if cmd == "load":
                model_size = obj.get("model", "base")
                try:
                    import numpy as _np
                    from faster_whisper import WhisperModel as _WhisperModel
                    np = _np
                    WhisperModel = _WhisperModel
                    print(json.dumps({"status": f"loading model {model_size}"}), flush=True)
                    model = WhisperModel(model_size, device="cpu", compute_type="int8")
                    print(json.dumps({"status": "ready"}), flush=True)
                except Exception as e:
                    print(json.dumps({"error": f"model load failed: {e}"}), flush=True)
                    traceback.print_exc()
                    # continue; allow parent to decide next steps
            elif cmd == "transcribe":
                if model is None:
                    print(json.dumps({"error": "model not loaded"}), flush=True)
                    continue
                b64 = obj.get("pcm", "")
                rate = int(obj.get("rate", 16000))
                try:
                    pcm = base64.b64decode(b64)
                    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32767.0
                    segments, _ = model.transcribe(audio, beam_size=1)
                    full_text = "".join([s.text for s in segments]).strip()
                    print(json.dumps({"text": full_text}), flush=True)
                except Exception as e:
                    print(json.dumps({"error": f"transcribe failed: {e}"}), flush=True)
            elif cmd == "quit":
                break
        except Exception as e:
            print(json.dumps({"error": f"protocol error: {e}"}), flush=True)

if __name__ == "__main__":
    main()

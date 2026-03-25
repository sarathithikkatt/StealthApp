"""Watches stats.json and emits stats_updated signal on change."""

from __future__ import annotations
import json, os, time, threading
from PyQt6.QtCore import QObject, pyqtSignal

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _HAS_WATCHDOG = True
except ImportError:
    _HAS_WATCHDOG = False


class StatWatcher(QObject):
    stats_updated = pyqtSignal(dict)

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = os.path.abspath(filepath)
        self._last: dict = {}
        self._running = False
        if not os.path.exists(self.filepath):
            self._write_default()

    def _write_default(self):
        default = {"game": "Unknown", "stats": {}, "custom": []}
        with open(self.filepath, "w") as f:
            json.dump(default, f, indent=2)

    def _read(self):
        try:
            with open(self.filepath) as f:
                data = json.load(f)
            if data != self._last:
                self._last = data
                self.stats_updated.emit(data)
        except Exception:
            pass

    def start(self):
        self._running = True
        self._read()
        print(f"[StatWatcher] start watching {self.filepath} (has_watchdog={_HAS_WATCHDOG})")
        if _HAS_WATCHDOG:
            self._start_watchdog()
        else:
            self._start_poll()

    def stop(self):
        self._running = False
        if hasattr(self, "_observer"):
            self._observer.stop()

    def _start_watchdog(self):
        ref = self
        print("[StatWatcher] starting watchdog observer")
        class H(FileSystemEventHandler):
            def on_modified(self, event):
                if os.path.abspath(event.src_path) == ref.filepath:
                    ref._read()
        self._observer = Observer()
        self._observer.schedule(H(), os.path.dirname(self.filepath), recursive=False)
        self._observer.start()

    def _start_poll(self):
        print("[StatWatcher] starting poll loop")
        def loop():
            mtime = 0
            while self._running:
                try:
                    m = os.path.getmtime(self.filepath)
                    if m != mtime:
                        mtime = m
                        self._read()
                except FileNotFoundError:
                    pass
                time.sleep(0.5)
        threading.Thread(target=loop, daemon=True).start()

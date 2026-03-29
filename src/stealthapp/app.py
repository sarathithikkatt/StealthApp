"""Application bootstrap."""

import sys
import os
import threading
import traceback
import faulthandler
import signal

# Allow running from repo root without install
_src = os.path.join(os.path.dirname(__file__), "..", "..")
if _src not in sys.path:
    sys.path.insert(0, _src)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from stealthapp.core.config import Config
from stealthapp.core.overlay_window import OverlayWindow
from stealthapp.core.logger import get_logger

logger = get_logger(__name__)


def run():
    # Work from the directory that holds config.json / stats.json
    # so relative paths in config resolve correctly.
    launch_dir = os.environ.get("STEALTHAPP_DIR", os.getcwd())
    os.chdir(launch_dir)

    logger.info("starting up")
    logger.info(f"launch_dir={launch_dir}")
    # Enable faulthandler to capture native crashes (segfaults) to a file
    try:
        crash_path = os.path.join(launch_dir, "crash.log")
        _crash_file = open(crash_path, "w")
        faulthandler.enable(file=_crash_file)
        for _sig in (getattr(signal, s) for s in ("SIGSEGV", "SIGABRT", "SIGFPE", "SIGILL") if hasattr(signal, s)):
            try:
                faulthandler.register(_sig, file=_crash_file, all_threads=True)
            except Exception:
                pass
        logger.info(f"faulthandler logging to {crash_path}")
    except Exception:
        pass
    # Global exception hooks to capture unhandled exceptions and thread errors
    def _sys_excepthook(exc_type, exc_value, exc_tb):
        logger.error("Unhandled exception:", exc_info=(exc_type, exc_value, exc_tb))
        print("[EXCEPTION] Unhandled:")
        traceback.print_exception(exc_type, exc_value, exc_tb)

    def _thread_excepthook(args):
        # args is threading.ExceptHookArgs
        logger.error(f"Unhandled in thread {getattr(args,'thread',None)}", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        print(f"[EXCEPTION] Unhandled in thread {getattr(args,'thread',None)}")
        traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = _sys_excepthook
    threading.excepthook = _thread_excepthook
    app = QApplication(sys.argv)
    app.setApplicationName("StealthApp")
    app.setQuitOnLastWindowClosed(True)

    config = Config("config.json")
    logger.info("config loaded")
    try:
        window = OverlayWindow(config)
        logger.info("window created")
        window.show()
        logger.info("window shown")
    except Exception as exc:
        import traceback

        logger.error(f"exception while creating/showing window: {exc}")
        traceback.print_exc()
        sys.exit(1)

    try:
        rc = app.exec()
    except Exception as exc:
        import traceback

        logger.error(f"exception in app.exec(): {exc}")
        traceback.print_exc()
        rc = 1

    logger.info(f"exiting rc={rc}")
    sys.exit(rc)


if __name__ == "__main__":
    run()

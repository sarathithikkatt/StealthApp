"""stealthapp command line interface."""

import argparse
import ctypes
import ctypes.wintypes
import os
import subprocess
import sys
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

PID_PATH = Path.home() / ".stealthapp" / "stealthapp.pid"
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008


def _read_pid():
    try:
        return int(PID_PATH.read_text().strip())
    except (OSError, ValueError):
        return None


def _is_pid_alive(pid: int) -> bool:
    if psutil is not None:
        return psutil.pid_exists(pid)

    if sys.platform.startswith("win"):
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.wintypes.DWORD()
            alive = (
                ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                and exit_code.value == 259
            )
            return alive
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _ensure_dir():
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)


def _unsupported():
    print("unsupported OS")
    return 1


def _start(foreground: bool = False) -> int:
    if not sys.platform.startswith("win"):
        return _unsupported()

    pid = _read_pid()
    if pid and _is_pid_alive(pid):
        print("already running")
        return 0

    if PID_PATH.exists():
        PID_PATH.unlink(missing_ok=True)

    python_exe = Path(sys.executable)
    if foreground:
        proc = subprocess.Popen(
            [str(python_exe), "-m", "stealthapp.app"],
            close_fds=True,
        )
    else:
        pythonw = python_exe.with_name("pythonw.exe")
        if not pythonw.exists():
            pythonw = python_exe
        proc = subprocess.Popen(
            [str(pythonw), "-m", "stealthapp.app"],
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
            close_fds=True,
        )

    _ensure_dir()
    PID_PATH.write_text(str(proc.pid))
    print(f"StealthApp started (pid: {proc.pid})")

    if foreground:
        return proc.wait()

    return 0


def _stop() -> int:
    if not sys.platform.startswith("win"):
        return _unsupported()

    pid = _read_pid()
    if not pid or not PID_PATH.exists() or not _is_pid_alive(pid):
        PID_PATH.unlink(missing_ok=True)
        print("not running")
        return 0

    subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False)
    PID_PATH.unlink(missing_ok=True)
    print("StealthApp stopped")
    return 0


def _status() -> int:
    if not sys.platform.startswith("win"):
        return _unsupported()

    pid = _read_pid()
    if pid and _is_pid_alive(pid):
        print(f"running (pid: {pid})")
        return 0

    PID_PATH.unlink(missing_ok=True)
    print("not running")
    return 0


def cli(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="stealthapp")
    subparsers = parser.add_subparsers(dest="command", required=True)
    start_parser = subparsers.add_parser("start")
    start_parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run StealthApp in the foreground instead of in the background.",
    )
    subparsers.add_parser("stop")
    subparsers.add_parser("status")
    args = parser.parse_args(argv)

    if args.command == "start":
        return _start(foreground=args.foreground)
    if args.command == "stop":
        return _stop()
    if args.command == "status":
        return _status()
    return 1


if __name__ == "__main__":
    raise SystemExit(cli())

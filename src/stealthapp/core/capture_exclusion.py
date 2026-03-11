"""
Apply OS-level screen-capture exclusion so the overlay is invisible
to OBS, Discord, Zoom, and any other capture tool.

Windows : SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)
macOS   : NSWindow.sharingType = NSWindowSharingNone  (via PyObjC)
Linux   : KWin rule via D-Bus (best-effort)
"""

from __future__ import annotations
import platform, ctypes, sys


_WDA_EXCLUDEFROMCAPTURE = 0x00000011


def apply(hwnd: int) -> bool:
    """
    Mark the window as excluded from screen capture.
    Returns True on success, False otherwise.
    """
    os_name = platform.system()

    if os_name == "Windows":
        return _apply_windows(hwnd)
    elif os_name == "Darwin":
        return _apply_macos(hwnd)
    else:
        return _apply_linux(hwnd)


# ── Windows ───────────────────────────────────────────────────────────────────

def _apply_windows(hwnd: int) -> bool:
    try:
        user32 = ctypes.windll.user32
        ok = user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), _WDA_EXCLUDEFROMCAPTURE)
        if ok:
            print("[CaptureExclusion] Windows: WDA_EXCLUDEFROMCAPTURE applied ✓")
            return True
        else:
            err = ctypes.get_last_error()
            print(f"[CaptureExclusion] Windows: SetWindowDisplayAffinity failed (err={err})")
            return False
    except Exception as e:
        print(f"[CaptureExclusion] Windows exception: {e}")
        return False


# ── macOS ─────────────────────────────────────────────────────────────────────

def _apply_macos(hwnd: int) -> bool:
    try:
        from AppKit import NSApp, NSWindowSharingNone  # type: ignore
        for win in NSApp.windows():
            win.setSharingType_(NSWindowSharingNone)
        print("[CaptureExclusion] macOS: NSWindowSharingNone applied ✓")
        return True
    except ImportError:
        print("[CaptureExclusion] macOS: pyobjc-framework-Cocoa not installed.")
        print("  Run: pip install pyobjc-framework-Cocoa")
        return False
    except Exception as e:
        print(f"[CaptureExclusion] macOS exception: {e}")
        return False


# ── Linux ─────────────────────────────────────────────────────────────────────

def _apply_linux(hwnd: int) -> bool:
    # KWin supports _KDE_NET_WM_SKIP_CLOSE_ANIMATION and window rules,
    # but there's no universal X11/Wayland API for capture exclusion.
    # Best we can do is set _NET_WM_BYPASS_COMPOSITOR on the window.
    print("[CaptureExclusion] Linux: No universal capture-exclusion API.")
    print("  KWin users: add a Window Rule to mark this window as 'never captured'.")
    return False

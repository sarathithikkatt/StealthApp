"""
Apply OS-level screen-capture exclusion so the overlay is invisible
to OBS, Discord, Zoom, and any other capture tool.

Windows : SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)
macOS   : NSWindow.sharingType = NSWindowSharingNone  (via PyObjC)
Linux   : KWin rule via D-Bus (best-effort)
"""

from __future__ import annotations
import platform, ctypes
from stealthapp.core.logger import get_logger

logger = get_logger(__name__)


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
            logger.info("Windows: WDA_EXCLUDEFROMCAPTURE applied (ok)")
            return True
        else:
            err = ctypes.get_last_error()
            logger.error(f"Windows: SetWindowDisplayAffinity failed (err={err})")
            return False
    except Exception as e:
        logger.error(f"Windows exception: {e}")
        return False


# ── macOS ─────────────────────────────────────────────────────────────────────

def _apply_macos(hwnd: int) -> bool:
    try:
        from AppKit import NSApp  # type: ignore
        NSWindowSharingNone = 0   # safe fallback — value is stable in the macOS SDK
        applied = 0
        for win in NSApp.windows():
            win.setSharingType_(NSWindowSharingNone)
            applied += 1
        if applied == 0:
            logger.warning("macOS: no NSWindows found yet — try increasing QTimer delay")
            return False
        logger.info(f"macOS: NSWindowSharingNone applied to {applied} window(s)")
        return True
    except ImportError:
        logger.warning("macOS: pyobjc-framework-Cocoa not installed. Run: pip install pyobjc-framework-Cocoa")
        return False
    except Exception as e:
        logger.error(f"macOS exception: {e}")
        return False


# ── Linux ─────────────────────────────────────────────────────────────────────
def _apply_linux(hwnd: int) -> bool:
    # There is no universal capture-exclusion API on Linux.
    # Wayland compositors (KWin, Mutter) are adding per-window capture
    # exclusion via the ext-session-lock and security-context protocols,
    # but no stable Python-accessible API exists yet (as of 2025).
    #
    # Best-effort: set _NET_WM_BYPASS_COMPOSITOR on the X11 window.
    # This hints to the compositor to render this window differently,
    # which *some* compositors honour for capture exclusion.
    try:
        from Xlib import display, X  # type: ignore  # pip install python-xlib
        d = display.Display()
        win = d.create_resource_object("window", hwnd)
        atom = d.intern_atom("_NET_WM_BYPASS_COMPOSITOR")
        win.change_property(atom, X.CARDINAL, 32, [2])   # 2 = always bypass
        d.sync()
        logger.info("Linux: _NET_WM_BYPASS_COMPOSITOR set (best-effort)")
        return True
    except ImportError:
        pass  # python-xlib not installed, skip silently
    except Exception:
        pass  # Wayland or other non-X11 session, skip silently

    logger.warning(
        "Linux: No capture-exclusion API available. "
        "KWin users: Settings → Window Rules → add rule for 'StealthApp' "
        "and set 'Block compositing' to Force/Yes."
    )
    return False
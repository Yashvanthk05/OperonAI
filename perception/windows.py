"""Window enumeration and cursor tracking via Win32 API."""

from __future__ import annotations

import ctypes
from typing import List, Optional, Tuple

import win32gui
import win32process

from core.models import BoundingBox, WindowInfo


def get_cursor_position() -> Tuple[int, int]:
    """Return the current (x, y) position of the mouse cursor."""

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


def get_window_info(hwnd: int) -> Optional[WindowInfo]:
    """Build a WindowInfo for a single window handle, or None if invalid."""
    try:
        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return None

        rect = win32gui.GetWindowRect(hwnd)
        box = BoundingBox(rect[0], rect[1], rect[2], rect[3])
        if box.width < 10 or box.height < 10:
            return None

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return WindowInfo(
            handle=hwnd,
            title=win32gui.GetWindowText(hwnd),
            class_name=win32gui.GetClassName(hwnd),
            bounding_box=box,
            is_maximized=bool(win32gui.IsZoomed(hwnd)),
            is_minimized=bool(win32gui.IsIconic(hwnd)),
            process_id=pid,
        )
    except Exception:
        return None


def get_active_window() -> Optional[WindowInfo]:
    """Return info about the currently focused window."""
    return get_window_info(win32gui.GetForegroundWindow())


def enumerate_windows() -> List[WindowInfo]:
    """List all visible windows on the desktop."""
    windows: List[WindowInfo] = []

    def _callback(hwnd: int, _) -> None:
        info = get_window_info(hwnd)
        if info:
            windows.append(info)

    try:
        win32gui.EnumWindows(_callback, None)
    except Exception:
        pass

    return windows

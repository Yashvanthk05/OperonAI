import time

import pyautogui
import win32con
import win32gui

from actions.mouse import _move_and_click
from core.models import DesktopState
from core.types import ActionResult


def _ensure_focus(hwnd: int) -> None:

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    except Exception:
        pass

    try:
        win32gui.BringWindowToTop(hwnd)
    except Exception:
        pass

    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def find_and_focus_window(window_title: str, state: DesktopState, element_name: str | None = None) -> ActionResult:
    
    for window in state.windows:
        if window_title.lower() not in window.title.lower():
            continue

        try:
            _ensure_focus(window.handle)
            time.sleep(0.15)

            try:
                win32gui.ShowWindow(window.handle, win32con.SW_MAXIMIZE)
            except Exception:
                pass

            if element_name:
                for el in state.interactive_elements:
                    if (
                        el.window_handle == window.handle
                        and element_name.lower() in el.name.lower()
                    ):
                        x, y = el.bounding_box.center
                        _move_and_click(x, y)
                        return ActionResult(
                            True,
                            f"Clicked '{element_name}' in '{window.title}'",
                            (x, y),
                        )

            return ActionResult(True, f"Focused window: {window.title}")
        except Exception as exc:
            return ActionResult(False, f"Window found but focus failed: {exc}")

    try:
        import uiautomation as auto

        win = auto.WindowControl(
            searchDepth=1, SubName=window_title, searchWaitTime=2
        )
        if win.Exists(maxSearchSeconds=3):
            win.SetActive()
            try:
                win.Maximize()
            except Exception:
                pass
            hwnd = int(getattr(win, "NativeWindowHandle", 0) or 0)
            if hwnd:
                _ensure_focus(hwnd)
                try:
                    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                except Exception:
                    pass
            return ActionResult(
                True, f"Focused window via uiautomation: {window_title}"
            )
    except Exception:
        pass

    return ActionResult(False, f"Window '{window_title}' not found")


def wait(seconds: float) -> ActionResult:

    time.sleep(seconds)
    return ActionResult(True, f"Waited {seconds}s")

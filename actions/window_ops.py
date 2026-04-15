"""Window management and wait actions."""

import time

import win32con
import win32gui

from actions.mouse import _move_and_click
from core.models import DesktopState
from core.types import ActionResult


def find_and_focus_window(
    window_title: str,
    state: DesktopState,
    element_name: str | None = None,
) -> ActionResult:
    """Find a window by title substring, bring it to the foreground,
    and optionally click a named element inside it.
    """
    for window in state.windows:
        if window_title.lower() not in window.title.lower():
            continue

        try:
            win32gui.ShowWindow(window.handle, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(window.handle)
            time.sleep(0.5)

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

    # Fallback: try uiautomation package for windows not in the tree
    try:
        import uiautomation as auto

        win = auto.WindowControl(
            searchDepth=1, SubName=window_title, searchWaitTime=2
        )
        if win.Exists(maxSearchSeconds=3):
            win.SetActive()
            return ActionResult(
                True, f"Focused window via uiautomation: {window_title}"
            )
    except Exception:
        pass

    return ActionResult(False, f"Window '{window_title}' not found")


def wait(seconds: float) -> ActionResult:
    """Pause execution for the specified number of seconds."""
    time.sleep(seconds)
    return ActionResult(True, f"Waited {seconds}s")

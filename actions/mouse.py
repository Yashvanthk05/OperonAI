"""Mouse click and cursor movement actions."""

import time
from typing import Any, Optional, Tuple

import pyautogui

from actions.element_lookup import (
    find_by_index,
    find_by_name,
    find_by_uiautomation,
    go_to_excel_cell,
    is_excel_active,
    is_excel_reference,
)
from core.models import DesktopState
from core.types import ActionResult
from perception.vision import find_click_target

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


def _move_and_click(x: int, y: int, button: str = "left", clicks: int = 1) -> None:
    """Move to (x, y) and perform the requested click(s)."""
    pyautogui.moveTo(x, y, duration=0.2)
    time.sleep(0.1)
    if clicks == 2:
        pyautogui.doubleClick(x, y, button=button)
    elif clicks == 1:
        pyautogui.click(x, y, button=button)
    else:
        for _ in range(clicks):
            pyautogui.click(x, y, button=button)
            time.sleep(0.1)


def click(
    state: DesktopState,
    target: Any,
    button: str = "left",
    clicks: int = 1,
) -> ActionResult:
    """Click on a target found by index, name, uiautomation, coordinates, or vision.

    Resolution order:
      1. Numeric index (int or string like "0")
      2. pywinauto UI tree name match
      3. Excel cell reference (if Excel is active)
      4. uiautomation package
      5. Vision model (if screenshot available)
    """
    x: Optional[int] = None
    y: Optional[int] = None
    description = ""

    # Coerce string-encoded integers: LLM often sends "0" instead of 0
    if isinstance(target, str) and target.strip().isdigit():
        target = int(target.strip())

    # --- Target is an element index ---
    if isinstance(target, int):
        result = find_by_index(state, target)
        if not result:
            return ActionResult(False, f"Element index {target} not found")
        el, box = result
        x, y = box.center
        description = f"{el.control_type}: '{el.name}'"

    # --- Target is a name string ---
    elif isinstance(target, str):
        # 1) pywinauto tree
        result = find_by_name(state, target)
        if result:
            el, box = result
            x, y = box.center
            description = f"{el.control_type}: '{el.name}'"

        # 2) Excel cell reference
        elif is_excel_active(state) and is_excel_reference(target):
            return go_to_excel_cell(target)

        # 3) uiautomation fallback
        else:
            coords = find_by_uiautomation(target)
            if coords:
                x, y = coords
                description = f"uiautomation: '{target}'"

            # 4) Vision model fallback
            elif state.screenshot:
                vx, vy, reason = find_click_target(state.screenshot, target)
                if vx is not None and vy is not None:
                    x, y = vx, vy
                    description = f"vision: '{target}'"
                else:
                    return ActionResult(False, f"Could not find '{target}': {reason}")
            else:
                return ActionResult(False, f"Element '{target}' not found")

    # --- Target is [x, y] coordinates ---
    elif isinstance(target, (tuple, list)) and len(target) == 2:
        x, y = int(target[0]), int(target[1])
        description = f"coordinates ({x}, {y})"

    else:
        return ActionResult(False, f"Invalid click target: {target}")

    try:
        _move_and_click(int(x), int(y), button=button, clicks=clicks)
        return ActionResult(True, f"Clicked {description}", (int(x), int(y)))
    except Exception as exc:
        return ActionResult(False, f"Click failed: {exc}")


def move_cursor(
    x: int,
    y: int,
    drag: bool = False,
    start_x: int | None = None,
    start_y: int | None = None,
) -> ActionResult:
    """Move the mouse cursor, or drag from one point to another."""
    try:
        if drag and start_x is not None and start_y is not None:
            pyautogui.moveTo(start_x, start_y, duration=0.2)
            time.sleep(0.1)
            pyautogui.dragTo(x, y, duration=0.5, button="left")
        else:
            pyautogui.moveTo(x, y, duration=0.2)
        return ActionResult(True, f"Moved to ({x}, {y})", (x, y))
    except Exception as exc:
        return ActionResult(False, f"Move failed: {exc}")

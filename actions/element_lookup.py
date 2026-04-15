import re
import time
from typing import Optional, Tuple

import pyautogui

from core.models import BoundingBox, DesktopState, UIElement
from core.types import ActionResult


def find_by_index(state: DesktopState, index: int) -> Optional[Tuple[UIElement, BoundingBox]]:
    
    if 0 <= index < len(state.interactive_elements):
        el = state.interactive_elements[index]
        return (el, el.bounding_box)
    return None


def find_by_name(state: DesktopState, name: str, control_type: str | None = None) -> Optional[Tuple[UIElement, BoundingBox]]:
    
    target = name.lower().strip()
    for el in state.interactive_elements:
        el_name = el.name.lower().strip()
        if target in el_name or el_name in target:
            if not control_type or el.control_type.lower() == control_type.lower():
                return (el, el.bounding_box)
    return None


def find_by_uiautomation(name: str) -> Optional[Tuple[int, int]]:
    
    try:
        import uiautomation as auto

        control = auto.Control(searchDepth=8, Name=name, searchWaitTime=1)
        if control.Exists(maxSearchSeconds=2):
            rect = control.BoundingRectangle
            cx = rect.left + (rect.right - rect.left) // 2
            cy = rect.top + (rect.bottom - rect.top) // 2
            return (cx, cy)
    except Exception:
        pass
    return None


# def is_excel_reference(text: str) -> bool:
    
#     pattern = r"^[a-z]{1,3}[1-9][0-9]{0,6}(?::[a-z]{1,3}[1-9][0-9]{0,6})?$"
#     return bool(re.match(pattern, text.strip(), re.IGNORECASE))


# def is_excel_active(state: DesktopState) -> bool:
#     """Check if Excel is the currently active application."""
#     if state.active_window:
#         title = state.active_window.title.lower()
#         cls = state.active_window.class_name.lower()
#         if "excel" in title or cls == "xlmain":
#             return True
#     return False


# def go_to_excel_cell(reference: str) -> ActionResult:
#     """Navigate to a specific Excel cell using Ctrl+G."""
#     normalized = reference.strip().upper()
#     try:
#         pyautogui.hotkey("ctrl", "g")
#         time.sleep(0.2)
#         pyautogui.write(normalized, interval=0.02)
#         pyautogui.press("enter")
#         time.sleep(0.2)
#         return ActionResult(True, f"Focused Excel cell: {normalized}")
#     except Exception as exc:
#         return ActionResult(False, f"Could not focus cell {normalized}: {exc}")

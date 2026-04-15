"""Build the UI accessibility tree using pywinauto's UIA backend."""

from __future__ import annotations

from typing import List, Optional

import win32gui
from pywinauto import Desktop

from core.models import BoundingBox, UIElement, WindowInfo

# Control types considered interactive (clickable / editable)
INTERACTIVE_TYPES = {
    "Button", "CheckBox", "ComboBox", "Edit", "Hyperlink",
    "List", "ListItem", "Menu", "MenuItem", "RadioButton",
    "Slider", "Spinner", "Tab", "TabItem", "Text", "Toggle",
    "SplitButton", "Tree", "TreeItem", "Custom",
}

# Structural types that are never directly interactive
STRUCTURAL_TYPES = {
    "Pane", "Group", "Header", "HeaderItem", "ScrollBar",
    "Thumb", "TitleBar", "Separator",
}


def is_interactive(control_type: str, name: str) -> bool:
    """Decide whether a control should appear in the interactive-elements list."""
    if control_type in STRUCTURAL_TYPES:
        return False
    if control_type in INTERACTIVE_TYPES:
        return True
    return bool(name.strip())


def build_element(
    wrapper,
    max_depth: int,
    window_handle: int,
    window_name: str,
) -> Optional[UIElement]:
    """Recursively convert a pywinauto wrapper into a UIElement."""
    try:
        rect = wrapper.rectangle()
        box = BoundingBox(rect.left, rect.top, rect.right, rect.bottom)
        if box.width < 2 or box.height < 2 or box.area < 10:
            return None

        try:
            info = wrapper.element_info
            control_type = getattr(info, "control_type", "") or ""
            automation_id = getattr(info, "automation_id", "") or ""
            class_name = (
                getattr(info, "class_name", "") or wrapper.class_name() or ""
            )
        except Exception:
            control_type, automation_id, class_name = "", "", ""

        element = UIElement(
            name=wrapper.window_text() or "",
            control_type=control_type,
            automation_id=automation_id,
            class_name=class_name,
            bounding_box=box,
            window_handle=window_handle,
            window_name=window_name,
        )

        if max_depth > 0:
            try:
                for child in wrapper.children():
                    child_el = build_element(
                        child, max_depth - 1, window_handle, window_name
                    )
                    if child_el:
                        element.children.append(child_el)
            except Exception:
                pass

        return element
    except Exception:
        return None


def build_ui_tree(
    windows: List[WindowInfo], max_depth: int = 3
) -> Optional[UIElement]:
    """Build the full UI tree for all visible windows."""
    try:
        desktop = Desktop(backend="uia")
        children: List[UIElement] = []

        for window in windows:
            try:
                wrapper = desktop.window(handle=window.handle)
                if not wrapper.exists(timeout=0.5):
                    continue

                root = build_element(
                    wrapper, max_depth, window.handle, window.title
                )
                if root:
                    children.append(root)
            except Exception:
                continue

        if not children:
            return None

        desktop_rect = win32gui.GetWindowRect(win32gui.GetDesktopWindow())
        return UIElement(
            name="Desktop",
            control_type="Desktop",
            automation_id="",
            class_name="Desktop",
            bounding_box=BoundingBox(*desktop_rect),
            children=children,
        )
    except Exception:
        return None


def collect_interactive_elements(
    element: Optional[UIElement], depth: int = 0
) -> List[UIElement]:
    """Flatten the UI tree to a list of interactive elements only."""
    if not element:
        return []

    results: List[UIElement] = []
    if depth > 0 and is_interactive(element.control_type, element.name):
        results.append(element)

    for child in element.children:
        results.extend(collect_interactive_elements(child, depth + 1))

    return results

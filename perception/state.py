from __future__ import annotations

import base64
import io
from typing import List

from PIL import Image

from core.models import DesktopState, UIElement, WindowInfo
from perception.screenshot import annotate_screenshot, capture_screenshot
from perception.ui_tree import build_ui_tree, collect_interactive_elements
from perception.windows import enumerate_windows, get_active_window, get_cursor_position


def capture_desktop_state(use_vision: bool = False, scale: float = 1.0,) -> DesktopState:
    
    cursor = get_cursor_position()
    windows = enumerate_windows()
    active = get_active_window()

    ui_tree = build_ui_tree(windows, active_window=active)
    elements = collect_interactive_elements(ui_tree) if ui_tree else []

    screenshot = None
    screenshot_b64 = None

    if use_vision:
        try:
            screenshot = capture_screenshot()

            if screenshot and elements:
                screenshot = annotate_screenshot(screenshot, elements, cursor)

            if screenshot and scale != 1.0:
                new_size = (
                    max(1, int(screenshot.width * scale)),
                    max(1, int(screenshot.height * scale)),
                )
                screenshot = screenshot.resize(new_size, Image.Resampling.LANCZOS)

            if screenshot:
                buf = io.BytesIO()
                screenshot.save(buf, format="PNG")
                screenshot_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                buf.close()
        except Exception:
            pass

    return DesktopState(
        screenshot=screenshot,
        screenshot_base64=screenshot_b64,
        windows=windows,
        active_window=active,
        ui_tree=ui_tree,
        cursor_position=cursor,
        interactive_elements=elements,
    )


def _safe_text(value: str) -> str:

    text = (value or "").replace("\n", " ").replace("\r", " ").strip()
    return text if text else "-"


def elements_to_text(elements: List[UIElement], max_items: int = 50) -> str:
    
    lines: List[str] = []
    if not elements:
        return "(no interactive elements)"

    for i, el in enumerate(elements[:max_items]):
        # Keep the representation minimal and highly readable for LLM
        lines.append(
            f"[{i}] type='{_safe_text(el.control_type)}' "
            f"name='{_safe_text(el.name)}'"
        )

    if len(elements) > max_items:
        lines.append(f"... ({len(elements) - max_items} more elements)")

    return "\n".join(lines)


def windows_to_text(windows: List[WindowInfo]) -> str:
    
    lines: List[str] = []
    if not windows:
        return "(no visible windows)"

    for i, w in enumerate(windows):
        if w.is_minimized:
            status = "MINIMIZED"
        elif w.is_maximized:
            status = "MAXIMIZED"
        else:
            status = "NORMAL"

        lines.append(
            f"[{i}] title='{_safe_text(w.title)}' "
            f"class='{_safe_text(w.class_name)}' "
            f"hwnd={w.handle} pid={w.process_id} state={status} "
            f"bbox=({w.bounding_box.left}, {w.bounding_box.top}, "
            f"{w.bounding_box.right}, {w.bounding_box.bottom})"
        )
    return "\n".join(lines)

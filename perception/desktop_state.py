from __future__ import annotations

import base64
import ctypes
import io
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import mss
from PIL import Image, ImageDraw, ImageFont
from pywinauto import Desktop
import win32gui
import win32process


@dataclass
class BoundingBox:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> Tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)

    @property
    def area(self) -> int:
        return self.width * self.height

    def contains_point(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom


@dataclass
class UIElement:
    name: str
    control_type: str
    automation_id: str
    class_name: str
    bounding_box: BoundingBox
    children: List["UIElement"] = field(default_factory=list)
    window_handle: int = 0
    window_name: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "class_name": self.class_name,
            "bounding_box": {
                "left": self.bounding_box.left,
                "top": self.bounding_box.top,
                "right": self.bounding_box.right,
                "bottom": self.bounding_box.bottom,
                "width": self.bounding_box.width,
                "height": self.bounding_box.height,
                "center": self.bounding_box.center,
            },
            "window_handle": self.window_handle,
            "window_name": self.window_name,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class WindowInfo:
    handle: int
    title: str
    class_name: str
    bounding_box: BoundingBox
    is_maximized: bool
    is_minimized: bool
    process_id: int

    def to_dict(self) -> dict:
        return {
            "handle": self.handle,
            "title": self.title,
            "class_name": self.class_name,
            "bounding_box": {
                "left": self.bounding_box.left,
                "top": self.bounding_box.top,
                "right": self.bounding_box.right,
                "bottom": self.bounding_box.bottom,
                "width": self.bounding_box.width,
                "height": self.bounding_box.height,
                "center": self.bounding_box.center,
            },
            "is_maximized": self.is_maximized,
            "is_minimized": self.is_minimized,
            "process_id": self.process_id,
        }


@dataclass
class DesktopState:
    screenshot: Optional[Image.Image] = None
    screenshot_base64: Optional[str] = None
    windows: List[WindowInfo] = field(default_factory=list)
    active_window: Optional[WindowInfo] = None
    ui_tree: Optional[UIElement] = None
    cursor_position: Tuple[int, int] = (0, 0)
    interactive_elements: List[UIElement] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "windows": [window.to_dict() for window in self.windows],
            "active_window": self.active_window.to_dict()
            if self.active_window
            else None,
            "cursor_position": self.cursor_position,
            "interactive_elements_count": len(self.interactive_elements),
            "has_screenshot": self.screenshot is not None,
        }


def _get_cursor_position() -> Tuple[int, int]:
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    point = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return (point.x, point.y)


def _build_ui_element(
    wrapper,
    max_depth: int,
    window_handle: int,
    window_name: str,
) -> Optional[UIElement]:
    try:
        rect = wrapper.rectangle()
        bounding_box = BoundingBox(rect.left, rect.top, rect.right, rect.bottom)

        if bounding_box.width < 2 or bounding_box.height < 2 or bounding_box.area < 10:
            return None

        try:
            element_info = wrapper.element_info
            control_type = getattr(element_info, "control_type", "") or ""
            automation_id = getattr(element_info, "automation_id", "") or ""
            class_name = (
                getattr(element_info, "class_name", "") or wrapper.class_name() or ""
            )
        except Exception:
            control_type = ""
            automation_id = ""
            class_name = ""

        element = UIElement(
            name=wrapper.window_text() or "",
            control_type=control_type,
            automation_id=automation_id,
            class_name=class_name,
            bounding_box=bounding_box,
            window_handle=window_handle,
            window_name=window_name,
        )

        if max_depth > 0:
            try:
                for child in wrapper.children():
                    child_element = _build_ui_element(
                        child,
                        max_depth=max_depth - 1,
                        window_handle=window_handle,
                        window_name=window_name,
                    )
                    if child_element:
                        element.children.append(child_element)
            except Exception:
                pass

        return element
    except Exception:
        return None


def _get_window_info(hwnd: int) -> Optional[WindowInfo]:
    try:
        if not win32gui.IsWindow(hwnd):
            return None

        if not win32gui.IsWindowVisible(hwnd):
            return None

        rect = win32gui.GetWindowRect(hwnd)
        bounding_box = BoundingBox(rect[0], rect[1], rect[2], rect[3])
        if bounding_box.width < 10 or bounding_box.height < 10:
            return None

        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        is_minimized = win32gui.IsIconic(hwnd)
        is_maximized = win32gui.IsZoomed(hwnd)
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)

        return WindowInfo(
            handle=hwnd,
            title=title,
            class_name=class_name,
            bounding_box=bounding_box,
            is_maximized=is_maximized,
            is_minimized=is_minimized,
            process_id=process_id,
        )
    except Exception:
        return None


def _get_active_window() -> Optional[WindowInfo]:
    hwnd = win32gui.GetForegroundWindow()
    return _get_window_info(hwnd)


def _enumerate_windows() -> List[WindowInfo]:
    windows: List[WindowInfo] = []

    def enum_callback(hwnd: int, _) -> None:
        window = _get_window_info(hwnd)
        if window:
            windows.append(window)

    try:
        win32gui.EnumWindows(enum_callback, None)
    except Exception as exc:
        print(f"Could not enumerate windows: {exc}")

    return windows


def _build_full_ui_tree(
    windows: List[WindowInfo], max_depth: int = 3
) -> Optional[UIElement]:
    try:
        desktop = Desktop(backend="uia")
        children: List[UIElement] = []

        for window in windows:
            try:
                wrapper = desktop.window(handle=window.handle)
                if not wrapper.exists(timeout=0.5):
                    continue

                root = _build_ui_element(
                    wrapper,
                    max_depth=max_depth,
                    window_handle=window.handle,
                    window_name=window.title,
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
            window_handle=0,
            window_name="Desktop",
        )
    except Exception as exc:
        print(f"Could not build UI tree: {exc}")
        return None


def _is_interactive_control(control_type: str, name: str) -> bool:
    interactive_types = {
        "Button",
        "CheckBox",
        "ComboBox",
        "Edit",
        "Hyperlink",
        "List",
        "ListItem",
        "Menu",
        "MenuItem",
        "RadioButton",
        "Slider",
        "Spinner",
        "Tab",
        "TabItem",
        "Text",
        "Toggle",
        "SplitButton",
        "Tree",
        "TreeItem",
        "Custom",
    }

    non_interactive = {
        "Pane",
        "Group",
        "Header",
        "HeaderItem",
        "ScrollBar",
        "Thumb",
        "TitleBar",
        "Separator",
    }

    if control_type in non_interactive:
        return False
    if control_type in interactive_types:
        return True
    return bool(name.strip())


def _collect_interactive_elements(
    element: Optional[UIElement], depth: int = 0
) -> List[UIElement]:
    if not element:
        return []

    results: List[UIElement] = []
    if depth > 0 and _is_interactive_control(element.control_type, element.name):
        results.append(element)

    for child in element.children:
        results.extend(_collect_interactive_elements(child, depth + 1))

    return results


def capture_screenshot(monitor_index: int = 1) -> Image.Image:
    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        screenshot = sct.grab(monitor)
        return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")


def _random_color() -> str:
    return f"#{random.randint(0, 0xFFFFFF):06x}"


def _clamp_box_to_image(
    box: BoundingBox, width: int, height: int
) -> Optional[BoundingBox]:
    left = max(0, min(box.left, width - 1))
    top = max(0, min(box.top, height - 1))
    right = max(0, min(box.right, width))
    bottom = max(0, min(box.bottom, height))
    clamped = BoundingBox(left, top, right, bottom)
    if clamped.width < 2 or clamped.height < 2:
        return None
    return clamped


def capture_with_annotation(
    screenshot: Image.Image,
    elements: List[UIElement],
    cursor_pos: Tuple[int, int],
    grid_lines: Optional[Tuple[int, int]] = None,
) -> Image.Image:
    annotated = screenshot.copy()
    draw = ImageDraw.Draw(annotated)

    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()

    for index, element in enumerate(elements):
        clamped = _clamp_box_to_image(
            element.bounding_box, screenshot.width, screenshot.height
        )
        if not clamped:
            continue

        color = _random_color()
        draw.rectangle(
            [clamped.left, clamped.top, clamped.right, clamped.bottom],
            outline=color,
            width=2,
        )

        label = str(index)
        label_width = draw.textlength(label, font=font)
        label_top = max(0, clamped.top - 18)
        draw.rectangle(
            [clamped.left, label_top, clamped.left + label_width + 4, label_top + 15],
            fill=color,
        )
        draw.text(
            (clamped.left + 2, label_top + 1), label, fill=(255, 255, 255), font=font
        )

    if cursor_pos:
        x, y = cursor_pos
        if 0 <= x < screenshot.width and 0 <= y < screenshot.height:
            radius = 10
            draw.ellipse(
                [x - radius, y - radius, x + radius, y + radius], outline="red", width=2
            )
            draw.line([x - radius, y, x + radius, y], fill="red", width=2)
            draw.line([x, y - radius, x, y + radius], fill="red", width=2)

    if grid_lines:
        cols, rows = grid_lines
        for i in range(1, cols):
            x = screenshot.width * i // cols
            draw.line([(x, 0), (x, screenshot.height)], fill=(200, 200, 200), width=1)
        for i in range(1, rows):
            y = screenshot.height * i // rows
            draw.line([(0, y), (screenshot.width, y)], fill=(200, 200, 200), width=1)

    return annotated


def capture_full_desktop_state(
    use_vision: bool = False,
    use_annotation: bool = True,
    use_ui_tree: bool = True,
    max_image_size: Tuple[int, int] = (1920, 1080),
    scale: float = 1.0,
    grid_lines: Optional[Tuple[int, int]] = None,
) -> DesktopState:
    del max_image_size

    cursor_position = _get_cursor_position()
    windows = _enumerate_windows()
    active_window = _get_active_window()

    ui_tree = None
    interactive_elements: List[UIElement] = []

    if use_ui_tree:
        ui_tree = _build_full_ui_tree(windows)
        if ui_tree:
            interactive_elements = _collect_interactive_elements(ui_tree)

    screenshot = None
    screenshot_base64 = None
    if use_vision:
        try:
            screenshot = capture_screenshot()

            if screenshot and use_annotation and interactive_elements:
                screenshot = capture_with_annotation(
                    screenshot,
                    interactive_elements,
                    cursor_position,
                    grid_lines,
                )

            if screenshot and scale != 1.0:
                resized = (
                    max(1, int(screenshot.width * scale)),
                    max(1, int(screenshot.height * scale)),
                )
                screenshot = screenshot.resize(resized, Image.Resampling.LANCZOS)

            if screenshot:
                buffer = io.BytesIO()
                screenshot.save(buffer, format="PNG")
                screenshot_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                buffer.close()
        except Exception as exc:
            print(f"Could not capture screenshot: {exc}")

    return DesktopState(
        screenshot=screenshot,
        screenshot_base64=screenshot_base64,
        windows=windows,
        active_window=active_window,
        ui_tree=ui_tree,
        cursor_position=cursor_position,
        interactive_elements=interactive_elements,
    )


def elements_to_text(elements: List[UIElement], max_items: int = 50) -> str:
    lines: List[str] = []

    for index, element in enumerate(elements[:max_items]):
        center_x, center_y = element.bounding_box.center
        lines.append(
            f"[{index}] {element.control_type}: '{element.name}' @ ({center_x}, {center_y})"
        )
        if element.automation_id:
            lines.append(f"    automation_id={element.automation_id}")

    if len(elements) > max_items:
        lines.append(f"... ({len(elements) - max_items} more elements)")

    return "\n".join(lines)


def windows_to_text(windows: List[WindowInfo]) -> str:
    lines: List[str] = []
    for index, window in enumerate(windows):
        status = "NORMAL"
        if window.is_minimized:
            status = "MINIMIZED"
        elif window.is_maximized:
            status = "MAXIMIZED"

        lines.append(
            f"[{index}] '{window.title}' ({window.class_name}) - {status} @ "
            f"({window.bounding_box.left}, {window.bounding_box.top})"
        )
    return "\n".join(lines)

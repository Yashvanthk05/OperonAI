from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from PIL import Image


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

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom


@dataclass
class UIElement:
    name: str
    control_type: str
    automation_id: str
    class_name: str
    bounding_box: BoundingBox
    children: List[UIElement] = field(default_factory=list)
    window_handle: int = 0
    window_name: str = ""


@dataclass
class WindowInfo:
    handle: int
    title: str
    class_name: str
    bounding_box: BoundingBox
    is_maximized: bool
    is_minimized: bool
    process_id: int


@dataclass
class DesktopState:
    screenshot: Optional[Image.Image] = None
    screenshot_base64: Optional[str] = None
    windows: List[WindowInfo] = field(default_factory=list)
    active_window: Optional[WindowInfo] = None
    ui_tree: Optional[UIElement] = None
    cursor_position: Tuple[int, int] = (0, 0)
    interactive_elements: List[UIElement] = field(default_factory=list)

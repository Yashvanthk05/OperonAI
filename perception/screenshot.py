from __future__ import annotations

from typing import List, Optional, Tuple

import mss
from PIL import Image, ImageDraw, ImageFont

from core.models import BoundingBox, UIElement

ANNOTATION_COLORS = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
    "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
    "#F8C471", "#82E0AA", "#F1948A", "#85929E", "#73C6B6",
]


def capture_screenshot(monitor_index: int = 1) -> Image.Image:
    
    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def _clamp_box(box: BoundingBox, width: int, height: int) -> Optional[BoundingBox]:
   
    left = max(0, min(box.left, width - 1))
    top = max(0, min(box.top, height - 1))
    right = max(0, min(box.right, width))
    bottom = max(0, min(box.bottom, height))
    clamped = BoundingBox(left, top, right, bottom)
    if clamped.width < 2 or clamped.height < 2:
        return None
    return clamped


def annotate_screenshot(screenshot: Image.Image, elements: List[UIElement], cursor_pos: Tuple[int, int]) -> Image.Image:
    
    annotated = screenshot.copy()
    draw = ImageDraw.Draw(annotated)

    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()

    for idx, element in enumerate(elements):
        clamped = _clamp_box(
            element.bounding_box, screenshot.width, screenshot.height
        )
        if not clamped:
            continue

        color = ANNOTATION_COLORS[idx % len(ANNOTATION_COLORS)]
        draw.rectangle(
            [clamped.left, clamped.top, clamped.right, clamped.bottom],
            outline=color,
            width=2,
        )

        label = str(idx)
        label_w = draw.textlength(label, font=font)
        label_top = max(0, clamped.top - 18)
        draw.rectangle(
            [clamped.left, label_top, clamped.left + label_w + 4, label_top + 15],
            fill=color,
        )
        draw.text(
            (clamped.left + 2, label_top + 1), label, fill="white", font=font
        )

    cx, cy = cursor_pos
    if 0 <= cx < screenshot.width and 0 <= cy < screenshot.height:
        r = 10
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline="red", width=2)
        draw.line([cx - r, cy, cx + r, cy], fill="red", width=2)
        draw.line([cx, cy - r, cx, cy + r], fill="red", width=2)

    return annotated

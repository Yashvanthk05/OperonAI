"""Central action dispatcher — routes action type strings to handler functions.

Normalizes LLM output variants (camelCase, compound names) so that
e.g. "pressEnter", "press_enter", "openApp" all route correctly.
"""

import re
from typing import Any

from actions.apps import open_app
from actions.keyboard import press_key, send_shortcut, type_text
from actions.mouse import click, move_cursor
from actions.scroll import scroll
from actions.window_ops import find_and_focus_window, wait
from core.models import DesktopState
from core.types import ActionResult


def _normalize_action(raw: Any) -> tuple[str, str | None]:
    """Normalize an LLM action string into (action, embedded_value).

    Examples:
        "pressEnter"  → ("press", "enter")
        "openApp"     → ("open_app", None)
        "type_text"   → ("type", None)
        "double_click"→ ("double_click", None)
    """
    raw_str = str(raw) if raw is not None else ""
    # Convert camelCase → snake_case: "pressEnter" → "press_enter"
    snake = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", raw_str).lower().strip()

    # Handle compound press actions: "press_enter" → press("enter")
    if snake.startswith("press_") and snake not in ("press_key",):
        key = snake[6:]  # everything after "press_"
        return "press", key

    # Normalize common aliases
    aliases = {
        "type_text": "type",
        "write": "type",
        "enter_text": "type",
        "open_app": "open_app",
        "open": "open_app",
        "launch": "open_app",
        "hotkey": "shortcut",
        "key_combo": "shortcut",
        "left_click": "click",
        "mouse_click": "click",
        "drag": "move",
        "sleep": "wait",
        "delay": "wait",
        "finish": "done",
        "complete": "done",
        "find_window": "find_window",
        "focus_window": "find_window",
        "switch_window": "find_window",
    }

    return aliases.get(snake, snake), None


def execute_action(
    action_type: str,
    action_value: Any,
    state: DesktopState,
) -> ActionResult:
    """Route an action string to the appropriate handler function.

    Handles LLM output variants like "pressEnter", "openApp", "type_text".
    """
    action, embedded_value = _normalize_action(action_type)

    if action == "click":
        return click(state, action_value)

    if action == "double_click":
        return click(state, action_value, clicks=2)

    if action == "right_click":
        return click(state, action_value, button="right")

    if action == "type":
        return type_text(str(action_value))

    if action == "scroll":
        direction = (
            action_value
            if action_value in ("up", "down", "left", "right")
            else "down"
        )
        return scroll(direction)

    if action == "open_app":
        return open_app(str(action_value))

    if action == "find_window":
        if isinstance(action_value, str):
            return find_and_focus_window(action_value, state)
        return ActionResult(False, "Window name required")

    if action == "shortcut":
        if isinstance(action_value, str):
            keys = [k.strip() for k in action_value.split("+")]
            return send_shortcut(*keys)
        return ActionResult(False, "Shortcut keys required")

    if action == "press":
        # Use embedded value from compound name (e.g. "pressEnter" → "enter")
        key = embedded_value or str(action_value)
        return press_key(key)

    if action == "wait":
        try:
            return wait(float(action_value))
        except Exception:
            return wait(1.0)

    if action == "move":
        if isinstance(action_value, (tuple, list)) and len(action_value) == 2:
            return move_cursor(int(action_value[0]), int(action_value[1]))
        return ActionResult(False, "Coordinates required for move")

    if action == "done":
        return ActionResult(True, "Task completed")

    return ActionResult(False, f"Unknown action: {action_type}")

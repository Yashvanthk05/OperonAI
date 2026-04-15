from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "Missing dependency: mcp. Install with `pip install mcp` (or `uv pip install mcp`)."
    ) from exc

from actions.apps import open_app
from actions.dispatcher import execute_action
from actions.keyboard import press_key, send_shortcut, type_text
from actions.mouse import click, move_cursor
from actions.scroll import scroll
from actions.window_ops import find_and_focus_window, wait
from core.models import DesktopState
from core.types import ActionResult
from perception.state import capture_desktop_state

DEFAULT_SCALE = 0.6
mcp = FastMCP("operon-tools")


def _serialize_result(result: ActionResult) -> Dict[str, Any]:
    return {
        "success": bool(result.success),
        "message": str(result.message),
        "coordinates": list(result.coordinates) if result.coordinates else None,
    }


def _capture_state(use_vision: bool = False, scale: float = DEFAULT_SCALE) -> DesktopState:
    safe_scale = max(0.1, min(1.0, float(scale)))
    return capture_desktop_state(use_vision=bool(use_vision), scale=safe_scale)


def _serialize_state(
    state: DesktopState,
    max_windows: int = 30,
    max_elements: int = 80,
    include_screenshot: bool = False,
) -> Dict[str, Any]:
    active_window = None
    if state.active_window:
        aw = state.active_window
        active_window = {
            "title": aw.title,
            "class_name": aw.class_name,
            "process_id": aw.process_id,
            "is_maximized": aw.is_maximized,
            "is_minimized": aw.is_minimized,
            "bounds": {
                "left": aw.bounding_box.left,
                "top": aw.bounding_box.top,
                "right": aw.bounding_box.right,
                "bottom": aw.bounding_box.bottom,
            },
        }

    windows = []
    for idx, w in enumerate(state.windows[: max(1, int(max_windows))]):
        windows.append(
            {
                "index": idx,
                "title": w.title,
                "class_name": w.class_name,
                "process_id": w.process_id,
                "is_maximized": w.is_maximized,
                "is_minimized": w.is_minimized,
                "bounds": {
                    "left": w.bounding_box.left,
                    "top": w.bounding_box.top,
                    "right": w.bounding_box.right,
                    "bottom": w.bounding_box.bottom,
                },
            }
        )

    elements = []
    for idx, el in enumerate(state.interactive_elements[: max(1, int(max_elements))]):
        cx, cy = el.bounding_box.center
        elements.append(
            {
                "index": idx,
                "name": el.name,
                "control_type": el.control_type,
                "automation_id": el.automation_id,
                "class_name": el.class_name,
                "window_name": el.window_name,
                "window_handle": el.window_handle,
                "center": [cx, cy],
                "bounds": {
                    "left": el.bounding_box.left,
                    "top": el.bounding_box.top,
                    "right": el.bounding_box.right,
                    "bottom": el.bounding_box.bottom,
                },
            }
        )

    payload: Dict[str, Any] = {
        "active_window": active_window,
        "cursor_position": list(state.cursor_position),
        "windows": windows,
        "interactive_elements": elements,
        "counts": {
            "windows": len(state.windows),
            "interactive_elements": len(state.interactive_elements),
        },
    }

    if include_screenshot:
        payload["screenshot_base64"] = state.screenshot_base64

    return payload


@mcp.tool()
def list_operon_tools() -> Dict[str, Any]:
    """List all direct Operon tools exposed to Claude (no internal planning)."""
    return {
        "mode": "direct-tools-only",
        "tools": [
            "get_desktop_state",
            "open_application",
            "focus_window",
            "click_target",
            "type_text_direct",
            "press_key_direct",
            "send_shortcut_direct",
            "scroll_view",
            "move_pointer",
            "wait_seconds",
            "run_action",
        ],
    }


@mcp.tool()
def get_desktop_state(
    use_vision: bool = False,
    include_screenshot: bool = False,
    scale: float = DEFAULT_SCALE,
    max_windows: int = 30,
    max_elements: int = 80,
) -> Dict[str, Any]:
    """Capture and return desktop state for Claude to reason over."""
    state = _capture_state(use_vision=use_vision or include_screenshot, scale=scale)
    return _serialize_state(
        state,
        max_windows=max_windows,
        max_elements=max_elements,
        include_screenshot=include_screenshot,
    )


@mcp.tool()
def open_application(app_name: str) -> Dict[str, Any]:
    """Open an application by name."""
    return _serialize_result(open_app(app_name))


@mcp.tool()
def focus_window(
    window_title: str,
    element_name: Optional[str] = None,
    use_vision: bool = False,
    scale: float = DEFAULT_SCALE,
) -> Dict[str, Any]:
    """Focus and maximize a window by title; optionally click an element in it."""
    state = _capture_state(use_vision=use_vision, scale=scale)
    return _serialize_result(find_and_focus_window(window_title, state, element_name))


@mcp.tool()
def click_target(
    target: Any,
    button: str = "left",
    clicks: int = 1,
    use_vision: bool = True,
    scale: float = DEFAULT_SCALE,
) -> Dict[str, Any]:
    """Click by index, name, or coordinates."""
    state = _capture_state(use_vision=use_vision, scale=scale)
    return _serialize_result(click(state, target, button=button, clicks=int(clicks)))


@mcp.tool()
def type_text_direct(
    text: str,
    target: Any = None,
    clear_first: bool = False,
    use_vision: bool = True,
    scale: float = DEFAULT_SCALE,
) -> Dict[str, Any]:
    """Optionally focus a target, then type text."""
    if target not in (None, ""):
        state = _capture_state(use_vision=use_vision, scale=scale)
        focus_result = click(state, target)
        if not focus_result.success:
            return _serialize_result(
                ActionResult(False, f"Type focus failed: {focus_result.message}")
            )

    return _serialize_result(type_text(text, clear_first=bool(clear_first)))


@mcp.tool()
def press_key_direct(key: str) -> Dict[str, Any]:
    """Press a single keyboard key."""
    return _serialize_result(press_key(key))


@mcp.tool()
def send_shortcut_direct(keys: str) -> Dict[str, Any]:
    """Send a shortcut string like 'ctrl+s' or 'alt+tab'."""
    parts = [k.strip() for k in str(keys).split("+") if k.strip()]
    if not parts:
        return _serialize_result(ActionResult(False, "No shortcut keys provided"))
    return _serialize_result(send_shortcut(*parts))


@mcp.tool()
def scroll_view(direction: str, amount: int = 3) -> Dict[str, Any]:
    """Scroll up/down/left/right."""
    amt = int(amount)
    if amt <= 0:
        return _serialize_result(ActionResult(False, "amount must be > 0"))
    return _serialize_result(scroll(direction, amount=amt))


@mcp.tool()
def move_pointer(
    x: int,
    y: int,
    drag: bool = False,
    start_x: Optional[int] = None,
    start_y: Optional[int] = None,
) -> Dict[str, Any]:
    """Move cursor or perform drag from start_x/start_y to x/y."""
    return _serialize_result(
        move_cursor(
            int(x),
            int(y),
            drag=bool(drag),
            start_x=None if start_x is None else int(start_x),
            start_y=None if start_y is None else int(start_y),
        )
    )


@mcp.tool()
def wait_seconds(seconds: float) -> Dict[str, Any]:
    """Pause execution for the given seconds."""
    return _serialize_result(wait(float(seconds)))


@mcp.tool()
def run_action(
    action: str,
    target: Any = None,
    value: Any = None,
    use_vision: bool = True,
    scale: float = DEFAULT_SCALE,
) -> Dict[str, Any]:
    """Raw action entrypoint for Claude; no planner is used."""
    state = _capture_state(use_vision=use_vision, scale=scale)

    action_value: Any = target
    if str(action).strip().lower() == "type":
        if value not in (None, ""):
            action_value = {
                "target": target,
                "text": value,
            }
        else:
            action_value = target
    elif value not in (None, "") and target in (None, ""):
        action_value = value

    return _serialize_result(execute_action(action, action_value, state))


if __name__ == "__main__":
    mcp.run()

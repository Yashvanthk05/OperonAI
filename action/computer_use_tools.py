import os
import random
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import pyautogui
import win32con
import win32gui
from pywinauto import Desktop

from perception.desktop_state import BoundingBox, DesktopState, UIElement
from perception.vision_agent import find_click_target


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


@dataclass
class ActionResult:
    success: bool
    message: str
    coordinates: Optional[Tuple[int, int]] = None


def _enumerate_visible_window_titles() -> list[str]:
    titles: list[str] = []

    def enum_callback(hwnd: int, _) -> None:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd).strip()
            if title:
                titles.append(title.lower())
        except Exception:
            return

    try:
        win32gui.EnumWindows(enum_callback, None)
    except Exception:
        return titles

    return titles


def _window_matches_any_token(tokens: list[str]) -> bool:
    if not tokens:
        return False

    visible_titles = _enumerate_visible_window_titles()
    lowered_tokens = [token.lower().strip() for token in tokens if token.strip()]

    for title in visible_titles:
        for token in lowered_tokens:
            if token in title:
                return True

    return False


def _is_excel_reference(target: str) -> bool:
    pattern = r"^[a-z]{1,3}[1-9][0-9]{0,6}(?::[a-z]{1,3}[1-9][0-9]{0,6})?$"
    return bool(re.match(pattern, target.strip(), re.IGNORECASE))


def _is_excel_context(desktop_state: DesktopState) -> bool:
    active = desktop_state.active_window
    if active:
        active_title = active.title.lower()
        active_class = active.class_name.lower()
        if "excel" in active_title or active_class == "xlmain":
            return True

    for window in desktop_state.windows:
        title = window.title.lower()
        class_name = window.class_name.lower()
        if "excel" in title or class_name == "xlmain":
            return True

    return False


def _go_to_excel_reference(reference: str) -> ActionResult:
    normalized = reference.strip().upper()
    try:
        pyautogui.hotkey("ctrl", "g")
        time.sleep(0.2)
        pyautogui.write(normalized, interval=0.02)
        pyautogui.press("enter")
        time.sleep(0.2)
        return ActionResult(True, f"Focused Excel reference: {normalized}")
    except Exception as exc:
        return ActionResult(
            False, f"Could not focus Excel reference {normalized}: {exc}"
        )


def _find_element_by_index(
    desktop_state: DesktopState,
    index: int,
) -> Optional[Tuple[UIElement, BoundingBox]]:
    if index < 0 or index >= len(desktop_state.interactive_elements):
        return None

    element = desktop_state.interactive_elements[index]
    return (element, element.bounding_box)


def _find_element_by_name(
    desktop_state: DesktopState,
    name: str,
    control_type: str | None = None,
) -> Optional[Tuple[UIElement, BoundingBox]]:
    target_name = name.lower().strip()
    candidates = []

    for element in desktop_state.interactive_elements:
        element_name = element.name.lower().strip()
        if target_name in element_name or element_name in target_name:
            if not control_type or element.control_type.lower() == control_type.lower():
                candidates.append(element)

    if not candidates:
        return None

    best = candidates[0]
    return (best, best.bounding_box)


def _move_to_and_click(x: int, y: int, button: str = "left", clicks: int = 1) -> None:
    pyautogui.moveTo(x, y, duration=0.2)
    time.sleep(0.1)

    if clicks == 1:
        pyautogui.click(x, y, button=button)
        return
    if clicks == 2:
        pyautogui.doubleClick(x, y, button=button)
        return

    for _ in range(clicks):
        pyautogui.click(x, y, button=button)
        time.sleep(0.1)


def click(
    desktop_state: DesktopState,
    target: Any,
    button: str = "left",
    clicks: int = 1,
    use_vision: bool = True,
) -> ActionResult:
    x: Optional[int] = None
    y: Optional[int] = None
    description = ""

    if isinstance(target, int):
        result = _find_element_by_index(desktop_state, target)
        if not result:
            return ActionResult(False, f"Element index {target} not found")
        element, box = result
        x, y = box.center
        description = f"{element.control_type}: '{element.name}'"

    elif isinstance(target, str):
        result = _find_element_by_name(desktop_state, target)
        if result:
            element, box = result
            x, y = box.center
            description = f"{element.control_type}: '{element.name}'"
        elif _is_excel_context(desktop_state) and _is_excel_reference(target):
            return _go_to_excel_reference(target)
        elif use_vision and desktop_state.screenshot:
            vx, vy, reason = find_click_target(desktop_state.screenshot, target)
            if vx is None or vy is None:
                return ActionResult(False, f"Could not find '{target}': {reason}")
            x, y = vx, vy
            description = f"vision target '{target}'"
        else:
            return ActionResult(False, f"Element '{target}' not found")

    elif isinstance(target, (tuple, list)) and len(target) == 2:
        x, y = int(target[0]), int(target[1])
        description = f"coordinates ({x}, {y})"
    else:
        return ActionResult(False, f"Invalid target: {target}")

    try:
        _move_to_and_click(int(x), int(y), button=button, clicks=clicks)
        return ActionResult(True, f"Clicked {description}", (int(x), int(y)))
    except Exception as exc:
        return ActionResult(False, f"Click failed: {exc}")


def type_text(text: str, clear_first: bool = False) -> ActionResult:
    try:
        if clear_first:
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.press("delete")
            time.sleep(0.1)

        pyautogui.write(text, interval=0.02)
        return ActionResult(True, f"Typed: {text}")
    except Exception as exc:
        return ActionResult(False, f"Type failed: {exc}")


def press_key(key: str) -> ActionResult:
    try:
        pyautogui.press(key)
        return ActionResult(True, f"Pressed: {key}")
    except Exception as exc:
        return ActionResult(False, f"Press key failed: {exc}")


def send_shortcut(*keys: str) -> ActionResult:
    try:
        pyautogui.hotkey(*keys)
        return ActionResult(True, f"Sent: {'+'.join(keys)}")
    except Exception as exc:
        return ActionResult(False, f"Shortcut failed: {exc}")


def scroll(
    direction: str, amount: int = 3, x: int | None = None, y: int | None = None
) -> ActionResult:
    try:
        if x is not None and y is not None:
            pyautogui.moveTo(x, y, duration=0.1)
            time.sleep(0.05)

        if direction == "down":
            pyautogui.scroll(-amount)
        elif direction == "up":
            pyautogui.scroll(amount)
        elif direction == "left":
            pyautogui.hscroll(-amount)
        elif direction == "right":
            pyautogui.hscroll(amount)
        else:
            return ActionResult(False, f"Invalid direction: {direction}")

        return ActionResult(True, f"Scrolled {direction}")
    except Exception as exc:
        return ActionResult(False, f"Scroll failed: {exc}")


def move_cursor(
    x: int,
    y: int,
    drag: bool = False,
    start_x: int | None = None,
    start_y: int | None = None,
) -> ActionResult:
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


def open_app(app_name: str) -> ActionResult:
    normalized = " ".join(app_name.lower().strip().split())

    app_commands = {
        "notepad": ["notepad.exe"],
        "calculator": ["calc.exe"],
        "calc": ["calc.exe"],
        "word": ["winword.exe"],
        "excel": ["excel.exe"],
        "powershell": ["powershell.exe"],
        "cmd": ["cmd.exe"],
        "command": ["cmd.exe"],
        "browser": ["msedge.exe", "chrome.exe", "firefox.exe"],
        "edge": ["msedge.exe"],
        "microsoft edge": ["msedge.exe"],
        "chrome": ["chrome.exe"],
        "google chrome": ["chrome.exe"],
        "vscode": [
            "code",
            "%LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe",
            "%PROGRAMFILES%\\Microsoft VS Code\\Code.exe",
            "%PROGRAMFILES(X86)%\\Microsoft VS Code\\Code.exe",
        ],
        "vs code": [
            "code",
            "%LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe",
            "%PROGRAMFILES%\\Microsoft VS Code\\Code.exe",
            "%PROGRAMFILES(X86)%\\Microsoft VS Code\\Code.exe",
        ],
        "visual studio code": [
            "code",
            "%LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe",
            "%PROGRAMFILES%\\Microsoft VS Code\\Code.exe",
            "%PROGRAMFILES(X86)%\\Microsoft VS Code\\Code.exe",
        ],
        "code": [
            "code",
            "%LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe",
            "%PROGRAMFILES%\\Microsoft VS Code\\Code.exe",
            "%PROGRAMFILES(X86)%\\Microsoft VS Code\\Code.exe",
        ],
        "paint": ["mspaint.exe"],
        "explorer": ["explorer.exe"],
        "file explorer": ["explorer.exe"],
    }

    expected_window_tokens = {
        "notepad": ["notepad"],
        "calculator": ["calculator"],
        "calc": ["calculator"],
        "word": ["word"],
        "excel": ["excel"],
        "powershell": ["powershell"],
        "cmd": ["command prompt", "cmd"],
        "command": ["command prompt", "cmd"],
        "browser": ["edge", "chrome", "firefox"],
        "edge": ["edge"],
        "microsoft edge": ["edge"],
        "chrome": ["chrome"],
        "google chrome": ["chrome"],
        "vscode": ["visual studio code"],
        "vs code": ["visual studio code"],
        "visual studio code": ["visual studio code"],
        "code": ["visual studio code"],
        "paint": ["paint"],
        "explorer": ["file explorer"],
        "file explorer": ["file explorer"],
    }

    search_queries = {
        "vscode": "Visual Studio Code",
        "vs code": "Visual Studio Code",
        "visual studio code": "Visual Studio Code",
        "code": "Visual Studio Code",
    }

    attempted_commands: list[str] = []
    candidates = app_commands.get(normalized, [app_name])
    window_tokens = expected_window_tokens.get(normalized, [normalized])

    try:
        for candidate in candidates:
            command = os.path.expandvars(candidate)

            if os.path.isabs(command) and not os.path.exists(command):
                attempted_commands.append(f"{command} (missing)")
                continue

            try:
                subprocess.Popen([command], shell=False)

                for _ in range(8):
                    time.sleep(0.4)
                    if _window_matches_any_token(window_tokens):
                        pyautogui.hotkey("win", "up")
                        return ActionResult(True, f"Opened: {app_name} via {command}")

                attempted_commands.append(
                    f"{command} (launched but window not detected)"
                )
            except FileNotFoundError:
                attempted_commands.append(f"{command} (not found)")
                continue
            except Exception as exc:
                attempted_commands.append(f"{command} ({exc})")
                continue

        pyautogui.hotkey("win", "s")
        time.sleep(0.5)
        pyautogui.write(search_queries.get(normalized, app_name))
        time.sleep(0.5)
        pyautogui.press("enter")

        for _ in range(10):
            time.sleep(0.4)
            if _window_matches_any_token(window_tokens):
                pyautogui.hotkey("win", "up")
                return ActionResult(True, f"Opened via Start search: {app_name}")

        details = "; ".join(attempted_commands[-4:])
        if details:
            return ActionResult(
                False,
                f"Could not confirm app window for: {app_name}. Attempts: {details}",
            )
        return ActionResult(False, f"Could not confirm app window for: {app_name}")
    except Exception as exc:
        details = "; ".join(attempted_commands[-3:])
        if details:
            return ActionResult(False, f"Open app failed: {exc}. Attempts: {details}")
        return ActionResult(False, f"Open app failed: {exc}")


def excel_random_marks_stats(params: Any = None) -> ActionResult:
    count = 50
    min_mark = 35
    max_mark = 100

    if isinstance(params, dict):
        try:
            count = int(params.get("count", count))
            min_mark = int(params.get("min", min_mark))
            max_mark = int(params.get("max", max_mark))
        except Exception:
            return ActionResult(
                False, "Invalid parameters for excel_random_marks_stats"
            )

    count = max(1, min(count, 5000))
    if min_mark > max_mark:
        min_mark, max_mark = max_mark, min_mark

    try:
        import win32com.client
    except Exception as exc:
        return ActionResult(False, f"Excel COM automation unavailable: {exc}")

    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = True
        workbook = excel.Workbooks.Add()
        sheet = workbook.Worksheets(1)
        sheet.Name = "Marks"

        marks = [random.randint(min_mark, max_mark) for _ in range(count)]
        end_row = count + 1

        sheet.Range("A1").Value = "Marks"
        sheet.Range(f"A2:A{end_row}").Value = tuple((mark,) for mark in marks)
        sheet.Range("B1").Value = "Metric"
        sheet.Range("C1").Value = "Value"
        sheet.Range("B2").Value = "Average"
        sheet.Range("C2").Formula = f"=AVERAGE(A2:A{end_row})"
        sheet.Range("B3").Value = "Std Dev"
        sheet.Range("C3").Formula = f"=STDEV.S(A2:A{end_row})"
        sheet.Columns("A:C").AutoFit()
        sheet.Range("A1").Select()

        return ActionResult(
            True,
            f"Created Excel workbook with {count} random marks and computed average/std dev",
        )
    except Exception as exc:
        return ActionResult(False, f"Excel automation failed: {exc}")


def find_and_click_window(
    window_title: str,
    desktop_state: DesktopState,
    element_name: str | None = None,
) -> ActionResult:
    for window in desktop_state.windows:
        if window_title.lower() not in window.title.lower():
            continue

        try:
            win32gui.ShowWindow(window.handle, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(window.handle)
            time.sleep(0.5)

            if element_name:
                for element in desktop_state.interactive_elements:
                    if (
                        element.window_handle == window.handle
                        and element_name.lower() in element.name.lower()
                    ):
                        x, y = element.bounding_box.center
                        _move_to_and_click(x, y)
                        return ActionResult(
                            True,
                            f"Clicked '{element_name}' in '{window.title}'",
                            (x, y),
                        )

            return ActionResult(True, f"Found window: {window.title}")
        except Exception as exc:
            return ActionResult(False, f"Window found but focus failed: {exc}")

    return ActionResult(False, f"Window '{window_title}' not found")


def wait(seconds: float) -> ActionResult:
    time.sleep(seconds)
    return ActionResult(True, f"Waited {seconds}s")


def execute_action(
    action_type: str,
    action_value: Any,
    desktop_state: DesktopState,
    use_vision: bool = True,
) -> ActionResult:
    action = action_type.lower().strip()

    if action == "click":
        return click(desktop_state, action_value, use_vision=use_vision)

    if action == "double_click":
        return click(desktop_state, action_value, clicks=2, use_vision=use_vision)

    if action == "right_click":
        return click(desktop_state, action_value, button="right", use_vision=use_vision)

    if action == "type":
        return type_text(str(action_value))

    if action == "scroll":
        direction = (
            action_value if action_value in ("up", "down", "left", "right") else "down"
        )
        return scroll(direction)

    if action == "open_app":
        return open_app(str(action_value))

    if action == "find_window":
        if isinstance(action_value, str):
            return find_and_click_window(action_value, desktop_state)
        return ActionResult(False, "Window name required")

    if action == "shortcut":
        if isinstance(action_value, str):
            keys = [key.strip() for key in action_value.split("+")]
            return send_shortcut(*keys)
        return ActionResult(False, "Shortcut keys required")

    if action == "press":
        return press_key(str(action_value))

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

    if action == "excel_random_marks_stats":
        return excel_random_marks_stats(action_value)

    return ActionResult(False, f"Unknown action type: {action_type}")

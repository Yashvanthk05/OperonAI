import pyautogui

from core.types import ActionResult

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


def type_text(text: str, clear_first: bool = False) -> ActionResult:

    try:
        if clear_first:
            pyautogui.hotkey("ctrl", "a")
            pyautogui.press("delete")

        pyautogui.write(text, interval=0.02)
        return ActionResult(True, f"Typed: {text}")
    except Exception as exc:
        return ActionResult(False, f"Type failed: {exc}")


def press_key(key: str) -> ActionResult:

    try:
        pyautogui.press(key)
        return ActionResult(True, f"Pressed: {key}")
    except Exception as exc:
        return ActionResult(False, f"Press failed: {exc}")


def send_shortcut(*keys: str) -> ActionResult:
    
    try:
        pyautogui.hotkey(*keys)
        return ActionResult(True, f"Sent: {'+'.join(keys)}")
    except Exception as exc:
        return ActionResult(False, f"Shortcut failed: {exc}")

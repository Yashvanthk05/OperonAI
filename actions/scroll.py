import pyautogui

from core.types import ActionResult


def scroll(direction: str, amount: int = 3) -> ActionResult:

    try:
        if direction == "down":
            pyautogui.scroll(-amount)
        elif direction == "up":
            pyautogui.scroll(amount)
        elif direction == "left":
            pyautogui.hscroll(-amount)
        elif direction == "right":
            pyautogui.hscroll(amount)
        else:
            return ActionResult(False, f"Invalid scroll direction: {direction}")

        return ActionResult(True, f"Scrolled {direction}")
    except Exception as exc:
        return ActionResult(False, f"Scroll failed: {exc}")

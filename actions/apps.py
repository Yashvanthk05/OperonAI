"""Launch applications using multiple strategies — no hardcoded paths."""

import shutil
import subprocess
import time
from typing import List

import pyautogui
import win32gui

from core.types import ActionResult


def _tokenize_app_name(app_name: str) -> List[str]:
    """Split an app name into useful search tokens.

    "Microsoft PowerPoint" → ["microsoft powerpoint", "powerpoint"]
    "Google Chrome"        → ["google chrome", "chrome"]
    "notepad"              → ["notepad"]
    """
    normalized = app_name.lower().strip()
    tokens = [normalized]

    words = normalized.split()
    if len(words) > 1:
        # Add each individual word as a token (most useful: the last word)
        for word in words:
            if word not in ("microsoft", "google", "mozilla") and word not in tokens:
                tokens.append(word)

    return tokens


def _poll_for_window(tokens: List[str], timeout: float = 4.0) -> bool:
    """Poll visible window titles for a match against any of the given tokens."""
    interval = 0.4
    elapsed = 0.0

    while elapsed < timeout:
        time.sleep(interval)
        elapsed += interval

        titles: List[str] = []

        def _callback(hwnd: int, _) -> None:
            try:
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd).strip().lower()
                    if t:
                        titles.append(t)
            except Exception:
                pass

        try:
            win32gui.EnumWindows(_callback, None)
        except Exception:
            pass

        for title in titles:
            for token in tokens:
                if token in title:
                    return True

    return False


def _try_path_executable(name: str) -> bool:
    """Try to find and launch an executable via the system PATH."""
    # Try the full name, then individual words (e.g. "powerpoint" from "microsoft powerpoint")
    candidates = [name] + [w for w in name.split() if w != name]

    for candidate in candidates:
        exe = shutil.which(candidate) or shutil.which(f"{candidate}.exe")
        if exe:
            try:
                subprocess.Popen([exe], shell=False)
                return True
            except Exception:
                pass
    return False


def _try_pywinauto_start(name: str) -> bool:
    """Try to launch an app using pywinauto's Application.start()."""
    # Try the full name, then individual words
    candidates = [name] + [w for w in name.split() if w != name]

    for candidate in candidates:
        try:
            from pywinauto import Application

            Application(backend="uia").start(candidate)
            return True
        except Exception:
            pass
    return False


def _try_start_menu_search(query: str) -> None:
    """Open the Windows Start menu, type a search query, and press Enter."""
    pyautogui.hotkey("win", "s")
    time.sleep(0.6)
    pyautogui.write(query, interval=0.03)
    time.sleep(0.8)
    pyautogui.press("enter")


def open_app(app_name: str) -> ActionResult:
    """Open an application using a multi-strategy approach.

    Strategy order:
      1. Find executable on system PATH (shutil.which)
      2. pywinauto Application.start()
      3. Windows Start Menu search (always available)

    Window detection uses tokenized name matching so
    "Microsoft PowerPoint" matches a window titled "PowerPoint".
    """
    normalized = app_name.lower().strip()
    search_tokens = _tokenize_app_name(app_name)

    # Strategy 1: System PATH
    if _try_path_executable(normalized):
        if _poll_for_window(search_tokens):
            pyautogui.hotkey("win", "up")
            return ActionResult(True, f"Opened {app_name} via PATH")

    # Strategy 2: pywinauto
    if _try_pywinauto_start(normalized):
        time.sleep(1.5)
        if _poll_for_window(search_tokens):
            pyautogui.hotkey("win", "up")
            return ActionResult(True, f"Opened {app_name} via pywinauto")

    # Strategy 3: Start Menu search (universal fallback)
    _try_start_menu_search(app_name)
    if _poll_for_window(search_tokens, timeout=8.0):
        pyautogui.hotkey("win", "up")
        return ActionResult(True, f"Opened {app_name} via Start search")

    return ActionResult(False, f"Could not open: {app_name}")

import shutil
import subprocess
import time
from typing import List

import pyautogui
import win32gui

from core.types import ActionResult


def _tokenize_app_name(app_name: str) -> List[str]:
    
    normalized = app_name.lower().strip()
    tokens = [normalized]

    words = normalized.split()
    if len(words) > 1:
        
        for word in words:
            if word not in ("microsoft", "google", "mozilla") and word not in tokens:
                tokens.append(word)

    return tokens


def _poll_for_window(tokens: List[str], timeout: float = 4.0) -> bool:
    
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
    
    pyautogui.hotkey("win", "s")
    time.sleep(0.6)
    pyautogui.write(query, interval=0.03)
    time.sleep(0.8)
    pyautogui.press("enter")


def open_app(app_name: str) -> ActionResult:
    
    normalized = app_name.lower().strip()
    search_tokens = _tokenize_app_name(app_name)

    if _try_path_executable(normalized):
        if _poll_for_window(search_tokens):
            pyautogui.hotkey("win", "up")
            return ActionResult(True, f"Opened {app_name} via PATH")

    if _try_pywinauto_start(normalized):
        time.sleep(1.5)
        if _poll_for_window(search_tokens):
            pyautogui.hotkey("win", "up")
            return ActionResult(True, f"Opened {app_name} via pywinauto")

    _try_start_menu_search(app_name)
    if _poll_for_window(search_tokens, timeout=8.0):
        pyautogui.hotkey("win", "up")
        return ActionResult(True, f"Opened {app_name} via Start search")

    return ActionResult(False, f"Could not open: {app_name}")

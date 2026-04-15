"""Voice-first launcher for Operon.

Run:
    python tmp.py

Flow:
1) Wait for Enter key
2) Capture speech and transcribe to text
3) Fall back to typed input if speech fails
4) Route to: uv run python main.py "<instruction>"
"""

from __future__ import annotations

import subprocess
import sys
from typing import Optional

import pyttsx3
import speech_recognition as sr

LISTEN_TIMEOUT_SECONDS = 6
PHRASE_TIME_LIMIT_SECONDS = 12


def speak(engine: Optional[pyttsx3.Engine], text: str) -> None:
    if engine is None:
        return
    engine.say(text)
    engine.runAndWait()


def listen_for_prompt(recognizer: sr.Recognizer) -> str | None:
    try:
        with sr.Microphone() as source:
            print("Calibrating microphone...")
            recognizer.adjust_for_ambient_noise(source, duration=0.8)
            print("Listening now. Speak your instruction.")
            audio = recognizer.listen(
                source,
                timeout=LISTEN_TIMEOUT_SECONDS,
                phrase_time_limit=PHRASE_TIME_LIMIT_SECONDS,
            )
    except sr.WaitTimeoutError:
        print("No speech detected before timeout.")
        return None
    except OSError as exc:
        print(f"Microphone is unavailable: {exc}")
        return None

    try:
        text = recognizer.recognize_google(audio).strip()
        if not text:
            return None
        return text
    except sr.UnknownValueError:
        print("Could not understand the audio.")
        return None
    except sr.RequestError as exc:
        print(f"Speech service request failed: {exc}")
        return None


def launch_main_with_prompt(prompt: str, extra_args: list[str]) -> int:
    command = ["uv", "run", "python", "main.py", prompt, *extra_args]

    try:
        completed = subprocess.run(command, check=False)
        return completed.returncode
    except FileNotFoundError:
        print("'uv' was not found in PATH. Falling back to current Python executable.")
        fallback = [sys.executable, "main.py", prompt, *extra_args]
        completed = subprocess.run(fallback, check=False)
        return completed.returncode


def main() -> int:
    try:
        engine = pyttsx3.init()
    except Exception:
        engine = None

    recognizer = sr.Recognizer()

    print("Press Enter to start voice capture.")
    input()

    prompt = listen_for_prompt(recognizer)

    if prompt:
        print(f"Heard: {prompt}")
        speak(engine, f"You said: {prompt}")
    else:
        speak(engine, "I could not capture your speech. Please type your instruction.")
        prompt = input("Type your instruction: ").strip()

    if not prompt:
        print("No instruction was provided. Exiting.")
        return 1

    print(f"Launching: uv run python main.py \"{prompt}\"")
    return launch_main_with_prompt(prompt, sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

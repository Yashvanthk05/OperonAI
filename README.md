# Operon

A Windows computer-use AI agent that autonomously interacts with the desktop to complete natural-language tasks.

## How It Works

```
{User Instruction → LLM Planner → Action Dispatcher → Desktop
                        ↑                                |
                        └──── Perception (UI tree) ──────┘
```}

1. **Perception** captures the current desktop state — open windows, interactive UI elements, and optionally a screenshot.
2. **Planner** sends the state and task to a local LLM (via Ollama) to generate a sequence of actions.
3. **Actions** execute each step (click, type, open app, etc.) using `pyautogui`, `pywinauto`, `uiautomation`, and Win32 APIs.
4. The loop repeats until the task is done or max iterations are reached.

## Quick Start

```bash
pip install -e .

ollama pull llama3
ollama pull llava

python main.py "open notepad and type hello world"
python main.py "open calculator" --max-iterations 10
```

## Automation Stack

| Package         | Role                                    |
|-----------------|----------------------------------------|
| `pyautogui`     | Mouse/keyboard input simulation         |
| `pywinauto`     | UI tree traversal, app launching        |
| `uiautomation`  | Fallback element/window search          |
| `pywin32`       | Low-level Win32 window management       |
| `mss`           | Fast screenshot capture                 |
| `Pillow`        | Image processing and annotation         |

## Configuration

All settings are in `.env`:

| Variable         | Default                    | Description                      |
|-----------------|----------------------------|----------------------------------|
| `OLLAMA_BASE_URL`| `http://localhost:11434`   | Ollama API endpoint              |
| `TEXT_MODEL`     | `llama3`                   | LLM for plan generation          |
| `VISION_MODEL`   | `llava`                   | Vision model for screenshots     |
| `MAX_ITERATIONS` | `15`                      | Max agent loop iterations        |
# OperonAI

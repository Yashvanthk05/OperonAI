# Operon

A Windows computer-use AI agent that autonomously interacts with the desktop to complete natural-language tasks.

## How It Works

```
User Instruction → LLM Planner → Action Dispatcher → Desktop
                        ↑                                |
                        └──── Perception (UI tree) ──────┘
```

1. **Perception** captures the current desktop state — open windows, interactive UI elements, and optionally a screenshot.
2. **Planner** sends the state and task to a local LLM (via Ollama) to generate a sequence of actions.
3. **Actions** execute each step (click, type, open app, etc.) using `pyautogui`, `pywinauto`, `uiautomation`, and Win32 APIs.
4. The loop repeats until the task is done or max iterations are reached.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Make sure Ollama is running with your models
ollama pull llama3
ollama pull llava

# Run a task
python main.py "open notepad and type hello world"
python main.py "open calculator" --max-iterations 10
```

## Project Structure

```
clean/
├── main.py                  # CLI entry point
├── .env                     # Model and API configuration
├── pyproject.toml            # Dependencies
│
├── config/                  # Application settings
│   └── settings.py          # Pydantic Settings from .env
│
├── core/                    # Shared data models
│   ├── models.py            # BoundingBox, UIElement, WindowInfo, DesktopState
│   └── types.py             # ActionResult
│
├── perception/              # Desktop state capture
│   ├── windows.py           # Window enumeration (Win32 API)
│   ├── ui_tree.py           # UI accessibility tree (pywinauto UIA)
│   ├── screenshot.py        # Screen capture + annotation (mss, Pillow)
│   ├── vision.py            # Vision model helpers (Ollama)
│   └── state.py             # Orchestrates all perception modules
│
├── actions/                 # Desktop interaction
│   ├── keyboard.py          # type_text, press_key, send_shortcut
│   ├── scroll.py            # scroll
│   ├── mouse.py             # click (multi-strategy), move_cursor
│   ├── apps.py              # open_app (PATH → pywinauto → Start search)
│   ├── window_ops.py        # find_and_focus_window, wait
│   ├── excel.py             # Excel COM automation
│   ├── element_lookup.py    # Element finding (index, name, uiautomation, Excel refs)
│   └── dispatcher.py        # Route action strings to handlers
│
└── agent/                   # Agent orchestration
    ├── config.py            # AgentConfig, AgentStep
    ├── planner.py           # LLM plan generation + rule-based shortcuts
    └── loop.py              # Main observe → plan → act loop
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

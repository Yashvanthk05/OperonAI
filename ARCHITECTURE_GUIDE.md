## Operon: Detailed Implementation Guide

Below is a full, simple, file-by-file explanation of your project and the actions/functions in each file.

> Note: This includes all source files in your listed structure, plus `skill_loader.py` found in the workspace.

---

## Big Picture: How Operon Works

Operon follows an **Observe → Plan → Act** loop:

1. **Observe (Perception):** Read windows, UI controls, optional screenshot.
2. **Plan (Agent Planner):** Ask local LLM (Ollama) for next actions.
3. **Act (Actions):** Execute mouse/keyboard/window/app operations.
4. Repeat until done or max iterations reached.

---

## Root Files

### `README.md`

**Purpose:** Human-readable project overview and setup instructions.

**What it contains:**

- Architecture summary (Perception, Planner, Actions loop).
- Quick-start commands.
- Package role table (what each dependency is for).
- `.env` variable descriptions.

---

### `pyproject.toml`

**Purpose:** Python project metadata + dependencies.

**Key details:**

- Project name/version (`operon`, `0.2.0`).
- Requires Python `>=3.11`.
- Declares core runtime dependencies (e.g., `pyautogui`, `pywinauto`, `mss`, `requests`, `pydantic`).

---

### `requirements.txt`

**Purpose:** Plain dependency list for `pip install -r requirements.txt`.

**Contains:**

- Runtime packages used across automation, perception, config.

---

### `main.py`

**Purpose:** CLI entrypoint for running the agent.

**Main function(s):**

- `main(argv=None) -> int`
  - Parses CLI args:
    - positional `instruction`
    - optional `--max-iterations`
  - Builds `AgentConfig`.
  - Creates `ComputerUseAgent`.
  - Runs agent via `agent.run(instruction)`.
  - Prints outcome and step count.
  - Handles `KeyboardInterrupt` and runtime exceptions.

---

## `core/` (Shared Data Models)

### `core/models.py`

**Purpose:** Core dataclasses shared by all modules.

**Classes:**

- `BoundingBox`
  - Rectangle coordinates (`left, top, right, bottom`).
  - Helpers:
    - `width`, `height`, `center`, `area`, `contains(x, y)`.
- `UIElement`
  - One accessible UI control on screen.
  - Includes metadata (name, control type, automation id, class) + `bounding_box` + children.
- `WindowInfo`
  - Metadata for one visible desktop window.
  - Includes title/class, box, maximized/minimized flags, process id.
- `DesktopState`
  - Full observation snapshot:
    - screenshot (optional),
    - windows list,
    - active window,
    - UI tree,
    - cursor position,
    - flattened interactive elements.

---

### `core/types.py`

**Purpose:** Shared action result type.

**Class:**

- `ActionResult`
  - `success: bool`
  - `message: str`
  - `coordinates: Optional[Tuple[int, int]]`

Used by all action handlers to return consistent outcomes.

---

### `core/__init__.py`

**Purpose:** Re-export common core symbols.

**Exports:** `ActionResult`, `BoundingBox`, `DesktopState`, `UIElement`, `WindowInfo`.

---

## `config/` (Settings)

### `config/settings.py`

**Purpose:** Reads runtime settings from environment / `.env`.

**Class:**

- `Settings(BaseSettings)`
  - Fields:
    - `OLLAMA_BASE_URL` → `ollama_base_url`
    - `TEXT_MODEL` → `text_model`
    - `VISION_MODEL` → `vision_model`
    - `MAX_ITERATIONS` → `max_iterations`
  - `model_config` points to `.env`.

**Global object:**

- `cfg = Settings()` (shared config singleton used across modules).

---

### `config/__init__.py`

**Purpose:** Re-export `cfg`.

---

## `perception/` (Observe / Read Desktop)

### `perception/windows.py`

**Purpose:** Window + cursor data via Win32 APIs.

**Functions:**

- `get_cursor_position()`
  - Gets current mouse `(x, y)` from `user32`.
- `get_window_info(hwnd)`
  - Converts one window handle into `WindowInfo` if valid/visible.
- `get_active_window()`
  - Returns focused foreground window info.
- `enumerate_windows()`
  - Enumerates all visible windows and returns `WindowInfo[]`.

---

### `perception/ui_tree.py`

**Purpose:** Build accessibility tree using pywinauto UIA backend.

**Key constants:**

- `INTERACTIVE_TYPES`: controls likely actionable.
- `STRUCTURAL_TYPES`: non-actionable structure controls.

**Functions:**

- `is_interactive(control_type, name)`
  - Decision rule for including an element in actionable list.
- `build_element(wrapper, max_depth, window_handle, window_name)`
  - Recursively transforms pywinauto wrapper → `UIElement`.
- `build_ui_tree(windows, max_depth=3)`
  - Builds desktop-level UI tree from visible windows.
- `collect_interactive_elements(element, depth=0)`
  - Flattens tree to interactive elements only.

---

### `perception/screenshot.py`

**Purpose:** Capture and annotate screenshots.

**Functions:**

- `capture_screenshot(monitor_index=1)`
  - Uses `mss` to capture full monitor as PIL image.
- `_clamp_box(box, width, height)`
  - Safely clamps bounds to image dimensions.
- `annotate_screenshot(screenshot, elements, cursor_pos)`
  - Draws indexed boxes and cursor crosshair for visual debugging/model guidance.

---

### `perception/state.py`

**Purpose:** Central state assembly from all perception sources.

**Functions:**

- `capture_desktop_state(use_vision=False, scale=1.0)`
  - Collects cursor, windows, active window.
  - Builds UI tree + interactive element list.
  - If `use_vision=True`: captures + annotates + rescales screenshot and base64-encodes it.
  - Returns `DesktopState`.
- `elements_to_text(elements, max_items=50)`
  - Converts element list into prompt-friendly indexed text.
- `windows_to_text(windows)`
  - Converts windows list into prompt text including status (MINIMIZED/MAXIMIZED/NORMAL).

---

### `perception/vision.py`

**Purpose:** Vision-model calls via Ollama for target finding and verification.

**Functions:**

- `image_to_base64(image, fmt="PNG")`
  - Encodes PIL image to base64 string.
- `_call_vision(prompt, images, timeout=120)`
  - Sends request to `OLLAMA_BASE_URL/api/generate` with vision model.
- `_extract_json_object(text)`
  - Tries extracting first JSON object from model response text.
- `find_click_target(image, target_description)`
  - Asks vision model for `(x, y)` for target phrase.
- `verify_action_result(before, after, action, target)`
  - Compares screenshots to judge if action succeeded.

---

### `perception/__init__.py`

**Purpose:** Re-export key perception helpers:

- `capture_desktop_state`, `elements_to_text`, `windows_to_text`
- `find_click_target`, `verify_action_result`

---

## `agent/` (Plan + Control Loop)

### `agent/config.py`

**Purpose:** Runtime configuration and step logging models.

**Dataclasses:**

- `AgentConfig`
  - `max_iterations`, `action_delay`, `screenshot_scale`.
- `AgentStep`
  - Stores each executed action record:
    - iteration, action, target, value, reasoning, result, timestamp.

---

### `agent/planner.py`

**Purpose:** Generate actionable plan from task + desktop state.

**Key helper functions:**

- `_clip_text(text, max_chars)`
  - Prompt-size control.
- `_extract_first_int(text)`
  - Extracts integer for task patterns.
- `_parse_plan_json(raw)`
  - Parses LLM output into list of action dicts.
- `_make_rule_based_plan(task)`
  - Deterministic special-case shortcut:
    - Excel random marks + average + stddev workflow.
- `_call_ollama(payload, timeout=120)`
  - Calls text model endpoint with robust error wrapping.

**Main function:**

- `generate_plan(task, state, completed, failed) -> (plan, error)`
  - Uses rule-based shortcut first.
  - Otherwise prepares prompt with:
    - open windows text,
    - indexed interactive elements,
    - recent completed/failed history.
  - Attempts LLM generation in strict JSON mode, then fallback mode.
  - Returns parsed action list or error string.

---

### `agent/loop.py`

**Purpose:** Main autonomous loop implementation.

**Class: `ComputerUseAgent`**

**Important methods:**

- `__init__(config=None)`
  - Initializes state, iteration, history lists.
- `capture_state()`
  - Captures current `DesktopState` (without vision by default).
- `execute_plan(plan)`
  - Executes each planned action using dispatcher.
  - Logs `AgentStep`.
  - Updates completed/failed histories.
  - Recaptures state after screen-changing actions.
  - Sets `task_completed` when action is `"done"` (or specific custom action).
- `verify_completion(task)`
  - Uses vision before/after screenshot comparison.
- `run(task)`
  - Full observe-plan-act loop until done/max iterations.
  - Handles empty-plan streak and prints summary stats.

---

### `agent/__init__.py`

**Purpose:** Re-exports `AgentConfig`, `AgentStep`, `ComputerUseAgent`.

---

## `actions/` (Execute Actions on Desktop)

### `actions/dispatcher.py`

**Purpose:** Central routing of planner action strings to implementation functions.

**Functions:**

- `_normalize_action(raw)`
  - Normalizes LLM action variants:
    - camelCase → snake_case,
    - aliases (`open`, `launch` → `open_app`, etc.),
    - compound forms (`pressEnter` → `press`, `enter`).
- `execute_action(action_type, action_value, state)`
  - Dispatches to:
    - mouse click/move,
    - keyboard type/press/shortcut,
    - scroll,
    - app open,
    - window focus,
    - wait,
    - done.

---

### `actions/apps.py`

**Purpose:** Open applications robustly using multiple strategies.

**Functions:**

- `_tokenize_app_name(app_name)`
  - Builds matching tokens (e.g., from “Microsoft PowerPoint” gets `powerpoint` token).
- `_poll_for_window(tokens, timeout=4.0)`
  - Repeatedly scans visible window titles to detect launch success.
- `_try_path_executable(name)`
  - Tries executable via system PATH (`shutil.which` + `subprocess.Popen`).
- `_try_pywinauto_start(name)`
  - Tries launching via `pywinauto.Application.start`.
- `_try_start_menu_search(query)`
  - Uses `Win+S`, types query, presses Enter.
- `open_app(app_name)`
  - Strategy chain:
    1. PATH,
    2. pywinauto start,
    3. Start menu fallback.
  - Maximizes app (`Win+Up`) when found.

---

### `actions/element_lookup.py`

**Purpose:** Locate target UI elements by multiple methods + Excel helpers.

**Functions:**

- `find_by_index(state, index)`
  - Gets element from indexed `interactive_elements`.
- `find_by_name(state, name, control_type=None)`
  - Substring match against element names.
- `find_by_uiautomation(name)`
  - Fallback search using `uiautomation` directly.
- `is_excel_reference(text)`
  - Detects Excel refs like `A1`, `B2:C10`.
- `is_excel_active(state)`
  - Checks if active app/window looks like Excel.
- `go_to_excel_cell(reference)`
  - Uses `Ctrl+G` to jump to cell/range in Excel.

---

### `actions/mouse.py`

**Purpose:** Click and cursor-move execution with rich target resolution.

**Functions:**

- `_move_and_click(x, y, button="left", clicks=1)`
  - Performs move + click/double-click/multi-click.
- `click(state, target, button="left", clicks=1)`
  - Target resolution order:
    1. numeric index,
    2. name in pywinauto tree,
    3. Excel cell reference (if Excel active),
    4. uiautomation fallback,
    5. vision-model fallback,
    6. direct `[x, y]`.
  - Returns `ActionResult` with coordinates on success.
- `move_cursor(x, y, drag=False, start_x=None, start_y=None)`
  - Simple move or drag operation.

---

### `actions/keyboard.py`

**Purpose:** Typing and key shortcuts.

**Functions:**

- `type_text(text, clear_first=False)`
  - Optional `Ctrl+A` + Delete, then types text.
- `press_key(key)`
  - Presses one key (Enter/Tab/Escape etc.).
- `send_shortcut(*keys)`
  - Sends key combo (e.g., `ctrl+c`).

---

### `actions/scroll.py`

**Purpose:** Vertical/horizontal scrolling.

**Function:**

- `scroll(direction, amount=3)`
  - Supports `up`, `down`, `left`, `right`.

---

### `actions/window_ops.py`

**Purpose:** Focus windows and wait.

**Functions:**

- `find_and_focus_window(window_title, state, element_name=None)`
  - Finds matching window title, restores/focuses it.
  - Optional click of element inside that window.
  - Fallback focus via `uiautomation`.
- `wait(seconds)`
  - Sleep action wrapper.

---

### `actions/__init__.py`

**Purpose:** Re-exports dispatcher entrypoint `execute_action`.

---

## `__init__.py` Files (Package Wiring)

These files expose clean import APIs and do not contain runtime logic:

- `actions/__init__.py`
- `agent/__init__.py`
- `config/__init__.py`
- `core/__init__.py`
- `perception/__init__.py`

---

## End-to-End Flow Example

For a task like **“open notepad and type hello”**:

1. `main.py` receives instruction.
2. `agent.loop.ComputerUseAgent.run()` starts.
3. `perception.state.capture_desktop_state()` gathers windows/elements.
4. `agent.planner.generate_plan()` asks text LLM for actions.
5. `actions.dispatcher.execute_action()` routes each action.
6. `actions.apps.open_app("notepad")` launches app.
7. `actions.keyboard.type_text("hello")` types.
8. Planner emits `"done"` when complete.
9. Loop exits and prints summary.

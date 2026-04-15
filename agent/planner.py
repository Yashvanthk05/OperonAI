"""Plan generation: rule-based shortcuts and LLM-powered planning via Ollama."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import cfg
from core.models import DesktopState
from perception.state import elements_to_text, windows_to_text


def _clip_text(text: str, max_chars: int) -> str:
    """Truncate text with an indicator if it exceeds max_chars."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


def _extract_first_int(text: str) -> Optional[int]:
    """Extract the first integer (1-4 digits) from text."""
    match = re.search(r"\b(\d{1,4})\b", text)
    return int(match.group(1)) if match else None


def _parse_plan_json(raw: str) -> List[Dict[str, Any]]:
    """Parse raw LLM output into a list of action dictionaries."""
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        parsed = json.loads(raw[start:end] if start >= 0 and end > start else raw)
    except Exception:
        parsed = json.loads(raw)

    if isinstance(parsed, dict):
        for key in ("actions", "plan", "steps", "tasks"):
            if key in parsed and isinstance(parsed[key], list):
                return [item for item in parsed[key] if isinstance(item, dict)]
        return [parsed]

    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]

    return []


def _make_rule_based_plan(task: str) -> Optional[List[Dict[str, Any]]]:
    """Match well-known task patterns that can be handled deterministically."""
    lowered = task.lower()

    has_excel = "excel" in lowered
    has_marks = any(t in lowered for t in ("mark", "marks", "score", "scores"))
    has_avg = any(t in lowered for t in ("average", "mean"))
    has_std = any(
        t in lowered
        for t in ("standard deviation", "std deviation", "std dev", "stdev")
    )
    has_random = "random" in lowered

    if has_excel and has_marks and has_avg and has_std and has_random:
        count = _extract_first_int(task) or 50
        count = max(1, min(count, 5000))
        return [
            {
                "action": "excel_random_marks_stats",
                "target": {"count": count, "min": 35, "max": 100},
                "reasoning": "Deterministic Excel automation for stats workflow.",
            },
            {"action": "done", "target": "excel marks stats completed"},
        ]

    return None


def _call_ollama(payload: Dict[str, Any], timeout: int = 120) -> str:
    """Send a generate request to the Ollama API."""
    url = f"{cfg.ollama_base_url}/api/generate"

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("response", "[]")
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response else "unknown"
        body = ""
        if exc.response is not None:
            try:
                body = _clip_text((exc.response.text or "").strip(), 600)
            except Exception:
                pass
        msg = f"Ollama API failed (HTTP {status})"
        if body:
            msg += f": {body}"
        raise RuntimeError(msg) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Cannot reach Ollama at {cfg.ollama_base_url}: {exc}"
        ) from exc


_PLAN_PROMPT = """You are a Windows desktop automation AI controlling a PC via an agent.
Your task: {task}
{history}
CURRENT DESKTOP STATE:
Windows open:
{windows}

Interactive elements ({index_info}):
{elements}

RULES:
1. Output ONLY a valid JSON array of action objects
2. Each action: {{"action": "<type>", "target": <value>, "value": "<optional>"}}
3. Actions must be sequential and include all steps needed
4. If task is already complete, return []
5. Only use valid click indices. Do NOT guess indices outside the provided range.
6. Do not repeat the same failing action-target pair unless screen state changed

Available action types:
- "click": target = element index ({max_idx_str}) or name (string) or [x, y]
- "type": target = text to type
- "press": target = key name like "enter", "tab", "escape", "backspace"
- "scroll": target = "up" or "down"
- "open_app": target = app name (e.g. "notepad", "chrome", "excel")
- "shortcut": target = keys like "ctrl+c", "alt+tab", "ctrl+shift+n"
- "find_window": target = window title substring
- "wait": target = seconds (number)
- "done": task complete

Return ONLY the JSON array."""


def generate_plan(
    task: str,
    state: DesktopState,
    completed: List[str],
    failed: List[str],
) -> Tuple[List[Dict], str]:
    """Generate an action plan using rule-based matching or the LLM.

    Returns (plan, error_message). error_message is empty on success.
    """
    # Try a deterministic shortcut first
    rule_plan = _make_rule_based_plan(task)
    if rule_plan:
        return rule_plan, ""

    if not state:
        return [], "No desktop state available"

    elements_text = _clip_text(
        elements_to_text(state.interactive_elements, max_items=35), 5000
    )
    windows_text = _clip_text(windows_to_text(state.windows[:20]), 2500)

    history = ""
    if completed:
        history += f"\nAlready completed: {', '.join(completed[-5:])}"
    if failed:
        history += f"\nRecently failed (avoid repeating): {', '.join(failed[-5:])}"

    element_count = min(len(state.interactive_elements), 35)
    if element_count == 0:
        index_info = "0 total elements"
        max_idx_str = "None"
    else:
        max_index = max(0, element_count - 1)
        index_info = f"{element_count} total, indexed 0-{max_index} for clicking"
        max_idx_str = f"number 0-{max_index}"

    prompt = _PLAN_PROMPT.format(
        task=task,
        history=history,
        windows=windows_text,
        elements=elements_text,
        index_info=index_info,
        max_idx_str=max_idx_str,
    )

    attempts = [
        {
            "model": cfg.text_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        {
            "model": cfg.text_model,
            "prompt": prompt + "\n\nReturn ONLY a strict JSON array.",
            "stream": False,
        },
    ]

    errors: List[str] = []
    for attempt in attempts:
        try:
            raw = _call_ollama(attempt)
            plan = _parse_plan_json(raw)
            if plan:
                return plan, ""
            errors.append(f"Could not parse plan from: {raw[:200]}")
        except Exception as exc:
            errors.append(str(exc))

    return [], " | ".join(errors[-2:])
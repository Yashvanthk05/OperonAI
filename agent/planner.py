import json
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import cfg
from core.models import DesktopState
from perception.state import elements_to_text, windows_to_text


def _clip_text(text: str, max_chars: int) -> str:
    
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


def _extract_first_int(text: str) -> Optional[int]:
    
    match = re.search(r"\b(\d{1,4})\b", text)
    return int(match.group(1)) if match else None


def _parse_plan_json(raw: str) -> List[Dict[str, Any]]:

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


_PLAN_PROMPT = """You are an expert Windows desktop automation AI Agent.
Your task is to analyze the screen, previous actions, and the objective, then formulate the SINGLE BEST NEXT step to achieve the task.

GOAL: {task}
{history}
{last_result}

CURRENT DESKTOP STATE:
Active window: {active_window}
Cursor position: {cursor}

Windows open:
{windows}

Interactive elements ({index_info}):
{elements}

RULES:
1. IMPORTANT: Output ONLY a valid JSON array containing EXACTLY ONE action object.
2. Provide Chain-of-Thought reasoning FIRST in a "thought" field.
3. The JSON object format MUST be:
   {{
      "thought": "Analyze the screen state and history, explain what you see, and formulate the exact next step.",
'       "action": "action_name_here", 
      "target": <value>, 
      "value": "<optional>"
   }}
4. PREFER KEYBOARD OVER MOUSE: Always try to use "shortcut" (e.g., ctrl+n, alt+f, ctrl+s, alt+tab) or "press" (e.g., tab, enter, down) if possible. Only use "click" as a fallback when keyboard navigation is unknown or inapplicable.
5. Allowed values for "action":
- "click": target = element index (number) or name (string). EX: "target": 5
- "type": target = text to type. (If a text box needs focus first, use the "click" action in one step, then use "type" in the next. DO NOT use click indexes in "type")
- "press": target = key name like "enter", "tab", "escape"
- "scroll": target = "up" or "down"
- "open_app": target = app name (e.g. "notepad")
- "shortcut": target = keys like "ctrl+c", "alt+tab"
- "find_window": target = window title substring
- "wait": target = seconds (number)
- "done": task complete. (Must use when objective is met!)
6. DO NOT GUESS. Only use valid click indices shown above.
7. Only return ONE action object in the array. No long plans. Only the immediate next step.

Return ONLY the JSON array."""


def generate_plan(
    task: str,
    state: DesktopState,
    completed: List[str],
    failed: List[str],
    last_action_result: Optional[str] = None
) -> Tuple[List[Dict], str]:
    
    rule_plan = _make_rule_based_plan(task)
    if rule_plan:
        return rule_plan[:1], "" # only 1 action

    if not state:
        return [], "No desktop state available"

    elements_text = _clip_text(
        elements_to_text(state.interactive_elements, max_items=50), 6000
    )
    windows_text = _clip_text(windows_to_text(state.windows[:20]), 2500)

    history = ""
    if completed:
        history += f"\nLast completed: {', '.join(completed[-5:])}"
    if failed:
        history += f"\nRecently failed: {', '.join(failed[-5:])}"

    last_result_text = f"Result of Last Action: {last_action_result}" if last_action_result else "No previous action result."

    element_count = min(len(state.interactive_elements), 50)
    if element_count == 0:
        index_info = "0 total elements"
    else:
        index_info = f"{element_count} total, indexed 0-{element_count - 1} for clicking"

    active_window_text = state.active_window.title if state.active_window and state.active_window.title else "(none)"
    cursor_text = f"({state.cursor_position[0]}, {state.cursor_position[1]})"

    prompt = _PLAN_PROMPT.format(
        task=task,
        history=history,
        last_result=last_result_text,
        active_window=active_window_text,
        cursor=cursor_text,
        windows=windows_text,
        elements=elements_text,
        index_info=index_info,
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
                # Sanitize common LLM formatting mistakes
                for item in plan:
                    if isinstance(item, dict):
                        if isinstance(item.get("action"), dict):
                            nested = item["action"]
                            item["action"] = nested.get("action", nested.get("type", ""))
                            if "target" in nested: item["target"] = nested["target"]
                            if "value" in nested: item["value"] = nested["value"]
                        
                        if not item.get("action") and "type" in item:
                            item["action"] = item["type"]

                # Sanitize out of range clicks
                if plan[0].get("action") == "click" and isinstance(plan[0].get("target"), int):
                    if plan[0]["target"] < 0 or plan[0]["target"] >= element_count:
                         errors.append(f"Click index {plan[0]['target']} out of bounds")
                         continue
                return plan[:1], ""
            errors.append(f"Could not parse plan from: {raw[:200]}")
        except Exception as exc:
            errors.append(str(exc))

    return [], " | ".join(errors[-2:])
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image

from action.computer_use_tools import ActionResult, execute_action
from perception.desktop_state import (
    DesktopState,
    capture_full_desktop_state,
    elements_to_text,
    windows_to_text,
)
from perception.vision_agent import verify_action_result
from utils.config import cfg


@dataclass
class AgentConfig:
    max_iterations: int = 15
    max_plan_steps: int = 50
    action_delay: float = 1.0
    verify_actions: bool = True
    use_vision_fallback: bool = False
    max_image_size: Tuple[int, int] = (1280, 720)
    scale: float = 0.6
    grid_lines: Optional[Tuple[int, int]] = None


@dataclass
class AgentStep:
    iteration: int
    action: str
    target: Any
    value: Any
    reasoning: str
    result: ActionResult
    timestamp: float = field(default_factory=time.time)


class ComputerUseAgent:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.current_iteration = 0
        self.steps: List[AgentStep] = []
        self.completed_actions: List[str] = []
        self.failed_actions: List[str] = []
        self.desktop_state: Optional[DesktopState] = None
        self.last_screenshot: Optional[Image.Image] = None
        self.task_completed = False

    @staticmethod
    def _extract_first_int(text: str) -> Optional[int]:
        match = re.search(r"\b(\d{1,4})\b", text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except Exception:
            return None

    @staticmethod
    def _clip_text(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n... [truncated]"

    @staticmethod
    def _parse_plan_output(raw_output: str) -> List[Dict[str, Any]]:
        try:
            start = raw_output.find("[")
            end = raw_output.rfind("]") + 1
            parsed = json.loads(
                raw_output[start:end] if start >= 0 and end > start else raw_output
            )
        except Exception:
            parsed = json.loads(raw_output)

        if isinstance(parsed, dict):
            for key in ("actions", "plan", "steps", "tasks"):
                if key in parsed and isinstance(parsed[key], list):
                    maybe_plan = parsed[key]
                    return [item for item in maybe_plan if isinstance(item, dict)]
            return [parsed]

        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]

        return []

    def _call_ollama_generate(self, payload: Dict[str, Any], timeout: int = 120) -> str:
        url = f"{cfg.ollama_base_url}/api/generate"

        try:
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json().get("response", "[]")
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            body = ""
            if exc.response is not None:
                try:
                    body = (exc.response.text or "").strip()
                except Exception:
                    body = ""

            body = self._clip_text(body, 600)
            if body:
                raise RuntimeError(f"Ollama /api/generate failed (HTTP {status}): {body}") from exc
            raise RuntimeError(f"Ollama /api/generate failed (HTTP {status})") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not reach Ollama at {cfg.ollama_base_url}: {exc}") from exc

    def _generate_rule_based_plan(self, task: str) -> Optional[List[Dict[str, Any]]]:
        lowered = task.lower()

        has_excel = "excel" in lowered
        has_marks = any(
            token in lowered for token in ("mark", "marks", "score", "scores")
        )
        has_average = any(token in lowered for token in ("average", "mean"))
        has_std = any(
            token in lowered
            for token in (
                "standard deviation",
                "std deviation",
                "std dev",
                "stdev",
                "stdev.s",
            )
        )
        has_random = "random" in lowered

        if has_excel and has_marks and has_average and has_std and has_random:
            count = self._extract_first_int(task) or 50
            count = max(1, min(count, 5000))
            return [
                {
                    "action": "excel_random_marks_stats",
                    "target": {"count": count, "min": 35, "max": 100},
                    "reasoning": "Use deterministic Excel automation for this stats workflow.",
                },
                {"action": "done", "target": "excel marks stats completed"},
            ]

        return None

    def capture_state(self) -> DesktopState:
        self.desktop_state = capture_full_desktop_state(
            use_vision=False,
            use_annotation=True,
            use_ui_tree=True,
            max_image_size=self.config.max_image_size,
            scale=self.config.scale,
            grid_lines=self.config.grid_lines,
        )

        if self.desktop_state.screenshot:
            self.last_screenshot = self.desktop_state.screenshot.copy()

        return self.desktop_state

    def generate_plan_with_llm(self, task: str) -> Tuple[List[Dict], str]:
        rule_based = self._generate_rule_based_plan(task)
        if rule_based:
            return rule_based, ""

        if not self.desktop_state:
            return [], "No desktop state available"

        ui_elements_text = elements_to_text(
            self.desktop_state.interactive_elements,
            max_items=35,
        )
        windows_text = windows_to_text(self.desktop_state.windows[:20])
        ui_elements_text = self._clip_text(ui_elements_text, 5000)
        windows_text = self._clip_text(windows_text, 2500)

        done_str = ""
        if self.completed_actions:
            done_str = f"\nAlready completed: {', '.join(self.completed_actions[-5:])}"

        failed_str = ""
        if self.failed_actions:
            failed_str = f"\nRecently failed (avoid repeating blindly): {', '.join(self.failed_actions[-5:])}"

        prompt = f"""You are a Windows desktop automation AI controlling a PC via an agent.
Your task: {task}
{done_str}
{failed_str}

CURRENT DESKTOP STATE:
Windows open:
{windows_text}

Interactive elements (indexed for clicking):
{ui_elements_text}

RULES:
1. Output ONLY a valid JSON array of action objects
2. Each action: {{"action": "<type>", "target": <index/name/coords>, "value": "<optional>"}}
3. Actions must be sequential and include all steps needed to complete the task
4. If task is already complete, return []
5. Prefer robust actions over fragile pixel/label guesses
6. Do not repeat the same failing action-target pair unless screen state changed

Available action types:
- "click": target = element index (number) or name (string) or [x, y]
- "type": target = text to type
- "scroll": target = "up" or "down"
- "open_app": target = app name
- "shortcut": target = keys like "ctrl+c", "alt+tab"
- "find_window": target = window title
- "wait": target = seconds to wait (number)
- "excel_random_marks_stats": target = {{"count": 50, "min": 35, "max": 100}} to create workbook, insert random marks, and calculate average + standard deviation
- "done": task complete

Example output:
[
  {{"action": "open_app", "target": "notepad"}},
  {{"action": "wait", "target": 2}},
  {{"action": "type", "target": "Hello World"}},
  {{"action": "click", "target": 5}}
]

Return ONLY the JSON array."""

        attempts: List[Dict[str, Any]] = [
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
                raw_output = self._call_ollama_generate(attempt, timeout=120)
                plan = self._parse_plan_output(raw_output)
                if plan:
                    return plan, ""
                errors.append(f"Could not parse plan JSON from: {raw_output[:200]}")
            except Exception as exc:
                errors.append(str(exc))

        return [], " | ".join(errors[-2:])

    def execute_plan(self, plan: List[Dict]) -> bool:
        if not plan:
            return True

        all_success = True

        for action_dict in plan[: self.config.max_plan_steps]:
            if not isinstance(action_dict, dict):
                continue

            action_type = action_dict.get("action", "")
            target = action_dict.get("target")
            value = action_dict.get("value", "")

            result = execute_action(
                action_type,
                target,
                self.desktop_state,
                use_vision=self.config.use_vision_fallback,
            )

            step = AgentStep(
                iteration=self.current_iteration,
                action=action_type,
                target=target,
                value=value,
                reasoning=action_dict.get("reasoning", ""),
                result=result,
            )
            self.steps.append(step)

            if result.success:
                self.completed_actions.append(f"{action_type}:{target}")
                time.sleep(self.config.action_delay)

                if action_type in ("done", "excel_random_marks_stats"):
                    self.task_completed = True
                    break

                if self.config.verify_actions and action_type in (
                    "click",
                    "type",
                    "open_app",
                    "find_window",
                ):
                    self.capture_state()
            else:
                all_success = False
                self.failed_actions.append(f"{action_type}:{target}")
                if len(self.failed_actions) > 20:
                    self.failed_actions = self.failed_actions[-20:]
                print(f"Action failed: {action_type} -> {target} | {result.message}")

            if self.current_iteration >= self.config.max_iterations:
                break

        return all_success

    def verify_completion(self, task: str) -> Tuple[bool, str]:
        if (
            not self.desktop_state
            or not self.last_screenshot
            or not self.desktop_state.screenshot
        ):
            return False, "No state to verify"

        try:
            return verify_action_result(
                self.last_screenshot,
                self.desktop_state.screenshot,
                "task check",
                task,
            )
        except Exception:
            return False, "Verification failed"

    def run(self, task: str, verbose: bool = True) -> Tuple[bool, List[AgentStep]]:
        if verbose:
            print("Starting Computer Use Agent")
            print(f"Task: {task}")

        empty_plan_streak = 0

        while self.current_iteration < self.config.max_iterations:
            if verbose:
                print(
                    f"Iteration {self.current_iteration + 1}/{self.config.max_iterations}"
                )

            self.capture_state()

            if verbose and self.desktop_state and self.desktop_state.windows:
                active = self.desktop_state.active_window
                active_title = active.title if active else "None"
                print(f"Active window: {active_title}")
                print(
                    f"Interactive elements: {len(self.desktop_state.interactive_elements)}"
                )

            plan, error = self.generate_plan_with_llm(task)
            if error:
                print(f"Plan error: {error}")
                self.current_iteration += 1
                continue

            if not plan:
                empty_plan_streak += 1
                if empty_plan_streak >= 2:
                    print("Two consecutive empty plans. Task appears complete.")
                    break
                print("Empty plan. Re-analyzing...")
                time.sleep(1)
                self.current_iteration += 1
                continue

            empty_plan_streak = 0
            print(f"Plan has {len(plan)} actions")
            self.execute_plan(plan)
            self.current_iteration += 1

            if self.task_completed:
                print("Task marked complete by deterministic/completion action.")
                break

        print("Agent finished")
        print(f"Iterations: {self.current_iteration}")
        print(f"Steps: {len(self.steps)}")

        success_rate = (
            len([step for step in self.steps if step.result.success]) / len(self.steps)
            if self.steps
            else 0.0
        )
        print(f"Success rate: {success_rate:.1%}")

        return (
            self.task_completed or self.current_iteration < self.config.max_iterations,
            self.steps,
        )


def create_agent(config: Dict[str, Any] | None = None) -> ComputerUseAgent:
    if config:
        return ComputerUseAgent(AgentConfig(**config))
    return ComputerUseAgent()


def run_computer_use_task(task: str, **kwargs) -> Tuple[bool, List[AgentStep]]:
    agent = create_agent(kwargs)
    return agent.run(task)

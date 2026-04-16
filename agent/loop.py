import json
import time
import re
from typing import Dict, List, Optional, Tuple

from PIL import Image

from actions.dispatcher import execute_action
from agent.config import AgentConfig, AgentStep
from agent.planner import generate_plan
from core.models import DesktopState
from core.types import ActionResult
from perception.state import capture_desktop_state
from perception.vision import verify_action_result


class ComputerUseAgent:

    def __init__(self, config = None):
        self.config = config or AgentConfig()
        self.iteration = 0
        self.steps: List[AgentStep] = []
        self.completed: List[str] = []
        self.failed: List[str] = []
        self.state: Optional[DesktopState] = None
        self.last_screenshot: Optional[Image.Image] = None
        self.task_completed = False

    def capture_state(self) -> DesktopState:
        
        self.state = capture_desktop_state(
            use_vision=True,
            scale=self.config.screenshot_scale,
        )
        if self.state.screenshot:
            self.last_screenshot = self.state.screenshot.copy()
        return self.state

    def execute_plan(self, plan: List[Dict]) -> Tuple[bool, Optional[str]]:
        
        if not plan:
            return True, None

        def _short(value, max_len: int = 120) -> str:
            text = repr(value)
            if len(text) > max_len:
                return text[: max_len - 3] + "..."
            return text

        def _app_tokens(name: str) -> List[str]:
            lowered = name.lower().strip()
            tokens = [lowered]
            for word in re.split(r"\s+", lowered):
                if not word:
                    continue
                if word not in ("microsoft", "google", "mozilla"):
                    tokens.append(word)
            return list(dict.fromkeys(tokens))

        def _history_key(action: str, action_target: object, action_value: object) -> str:
            key = f"{action}:{action_target}"
            if action == "type" and action_value not in ("", None):
                value_text = str(action_value).strip().lower()
                if len(value_text) > 60:
                    value_text = value_text[:60]
                key = f"{key}:{value_text}"
            return key

        all_ok = True
        total_actions = len(plan)
        for step_idx, action_dict in enumerate(plan, start=1):
            if not isinstance(action_dict, dict):
                continue

            action_type = action_dict.get("action", "")
            target = action_dict.get("target")
            value = action_dict.get("value", "")

            print(
                f"Action {step_idx}/{total_actions}: {action_type} "
                f"target={_short(target)} value={_short(value)}"
            )

            action_value = target
            if action_type == "type":
                
                text_to_type = value if value not in ("", None) else target
                action_value = str(text_to_type) if text_to_type not in ("", None) else ""


            if action_type == "open_app" and isinstance(action_value, str) and self.state:
                tokens = _app_tokens(action_value)

                active_title = ""
                if self.state.active_window and self.state.active_window.title:
                    active_title = self.state.active_window.title.lower()

                open_titles = [w.title.lower() for w in self.state.windows if w.title]

                already_active = any(token in active_title for token in tokens if token)
                already_open = any(
                    any(token in title for token in tokens if token)
                    for title in open_titles
                )

                if already_active:
                    result = ActionResult(
                        True,
                        f"App already active: {action_value}",
                    )
                elif already_open:
                    focus_result = execute_action("find_window", action_value, self.state)
                    if focus_result.success:
                        result = ActionResult(
                            True,
                            f"Focused already-open app: {action_value}",
                            focus_result.coordinates,
                        )
                    else:
                        result = ActionResult(
                            False,
                            (
                                f"App already open but focus failed for '{action_value}': "
                                f"{focus_result.message}"
                            ),
                        )
                else:
                    result = execute_action(action_type, action_value, self.state)
            else:
                result = execute_action(action_type, action_value, self.state)
            status = "OK" if result.success else "FAIL"
            print(f"{status}: {result.message}")

            self.steps.append(AgentStep(
                iteration=self.iteration,
                action=action_type,
                target=target,
                value=value,
                reasoning=action_dict.get("reasoning", ""),
                result=result,
            ))

            if result.success:
                self.completed.append(_history_key(action_type, target, value))
                time.sleep(self.config.action_delay)

                if action_type in ("done", "excel_random_marks_stats"):
                    self.task_completed = True
                    break

                if action_type in ("click", "type", "open_app", "find_window"):
                    self.capture_state()
            else:
                all_ok = False
                self.failed.append(_history_key(action_type, target, value))
                if len(self.failed) > 20:
                    self.failed = self.failed[-20:]
                print(f"Action failed: {action_type} {target} | {result.message}")

            if self.iteration >= self.config.max_iterations:
                break

            last_msg = f"{status}: {result.message}"

        return all_ok, last_msg if 'last_msg' in locals() else None

    def verify_completion(self, task: str) -> Tuple[bool, str]:
        
        if not self.state or not self.last_screenshot or not self.state.screenshot:
            return False, "No state to verify"

        try:
            return verify_action_result(
                self.last_screenshot, self.state.screenshot, "task check", task
            )
        except Exception:
            return False, "Verification failed"

    def run(self, task: str) -> Tuple[bool, List[AgentStep]]:
        
        print(f"Starting agent | Task: {task}")

        empty_streak = 0
        repeated_plan_streak = 0
        last_plan_signature = ""
        last_action_result: Optional[str] = None

        def _tail_all_same(items: List[str], count: int) -> bool:
            return len(items) >= count and len(set(items[-count:])) == 1

        def _history_key(action: str, action_target: object, action_value: object) -> str:
            key = f"{action}:{action_target}"
            if action == "type" and action_value not in ("", None):
                value_text = str(action_value).strip().lower()
                if len(value_text) > 60:
                    value_text = value_text[:60]
                key = f"{key}:{value_text}"
            return key

        while self.iteration < self.config.max_iterations:
            print(f"Iteration {self.iteration + 1}/{self.config.max_iterations}")

            self.capture_state()

            if self.state and self.state.active_window:
                print(f"Active window: {self.state.active_window.title}")

            plan, error = generate_plan(
                task, self.state, self.completed, self.failed, last_action_result
            )

            if error:
                print(f"Plan error: {error}")
                self.iteration += 1
                continue

            if not plan:
                empty_streak += 1
                if empty_streak >= 2:
                    print("Two empty plans in a row - task appears complete.")
                    break
                time.sleep(1)
                self.iteration += 1
                continue

            empty_streak = 0

            try:
                plan_signature = json.dumps(plan, sort_keys=True, ensure_ascii=False)
            except Exception:
                plan_signature = repr(plan)

            if plan_signature == last_plan_signature:
                repeated_plan_streak += 1
            else:
                repeated_plan_streak = 0
            last_plan_signature = plan_signature

            if repeated_plan_streak >= 2:
                print("Repeated identical plan detected - marking plan stale and replanning.")

                for action_dict in plan:
                    if not isinstance(action_dict, dict):
                        continue
                    stale_key = _history_key(
                        str(action_dict.get("action", "")),
                        action_dict.get("target"),
                        action_dict.get("value", ""),
                    )
                    if stale_key:
                        self.failed.append(stale_key)

                if len(self.failed) > 20:
                    self.failed = self.failed[-20:]

                last_action_result = "FAIL: Repeated identical plan detected, planner is stuck."
                self.iteration += 1
                continue

            print(f"Plan: {len(plan)} action(s)")
            all_ok, last_msg = self.execute_plan(plan[:1]) # Execute only the FIRST action
            last_action_result = last_msg
            self.iteration += 1

            if self.task_completed:
                print("Task marked complete.")
                break

            if _tail_all_same(self.failed, 3):
                print("Repeated identical failure 3 times - stopping to avoid loop.")
                break

        success_count = sum(1 for s in self.steps if s.result.success)
        total = len(self.steps)
        rate = (success_count / total * 100) if total else 0
        print(
            f"Agent finished | Iterations: {self.iteration} "
            f"| Steps: {total} | Success: {rate:.0f}%"
        )

        return (self.task_completed or self.iteration < self.config.max_iterations, self.steps)

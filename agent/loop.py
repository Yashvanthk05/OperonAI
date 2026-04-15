"""Main agent loop: observe → plan → act → repeat."""

import time
from typing import Dict, List, Optional, Tuple

from PIL import Image

from actions.dispatcher import execute_action
from agent.config import AgentConfig, AgentStep
from agent.planner import generate_plan
from core.models import DesktopState
from perception.state import capture_desktop_state
from perception.vision import verify_action_result


class ComputerUseAgent:
    """Autonomous agent that interacts with the Windows desktop to complete tasks."""

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.iteration = 0
        self.steps: List[AgentStep] = []
        self.completed: List[str] = []
        self.failed: List[str] = []
        self.state: Optional[DesktopState] = None
        self.last_screenshot: Optional[Image.Image] = None
        self.task_completed = False

    def capture_state(self) -> DesktopState:
        """Capture the current desktop state."""
        self.state = capture_desktop_state(
            use_vision=False,
            scale=self.config.screenshot_scale,
        )
        if self.state.screenshot:
            self.last_screenshot = self.state.screenshot.copy()
        return self.state

    def execute_plan(self, plan: List[Dict]) -> bool:
        """Execute a sequence of planned actions."""
        if not plan:
            return True

        all_ok = True
        for action_dict in plan:
            if not isinstance(action_dict, dict):
                continue

            action_type = action_dict.get("action", "")
            target = action_dict.get("target")
            value = action_dict.get("value", "")

            result = execute_action(action_type, target, self.state)

            self.steps.append(AgentStep(
                iteration=self.iteration,
                action=action_type,
                target=target,
                value=value,
                reasoning=action_dict.get("reasoning", ""),
                result=result,
            ))

            if result.success:
                self.completed.append(f"{action_type}:{target}")
                time.sleep(self.config.action_delay)

                if action_type in ("done", "excel_random_marks_stats"):
                    self.task_completed = True
                    break

                # Re-capture state after actions that change the screen
                if action_type in ("click", "type", "open_app", "find_window"):
                    self.capture_state()
            else:
                all_ok = False
                self.failed.append(f"{action_type}:{target}")
                if len(self.failed) > 20:
                    self.failed = self.failed[-20:]
                print(f"  Action failed: {action_type} -> {target} | {result.message}")

            if self.iteration >= self.config.max_iterations:
                break

        return all_ok

    def verify_completion(self, task: str) -> Tuple[bool, str]:
        """Use the vision model to verify whether the task succeeded."""
        if not self.state or not self.last_screenshot or not self.state.screenshot:
            return False, "No state to verify"

        try:
            return verify_action_result(
                self.last_screenshot, self.state.screenshot, "task check", task
            )
        except Exception:
            return False, "Verification failed"

    def run(self, task: str) -> Tuple[bool, List[AgentStep]]:
        """Run the observe-plan-act loop until completion or max iterations."""
        print(f"Starting agent | Task: {task}")

        empty_streak = 0

        while self.iteration < self.config.max_iterations:
            print(f"  Iteration {self.iteration + 1}/{self.config.max_iterations}")

            self.capture_state()

            if self.state and self.state.active_window:
                print(f"  Active window: {self.state.active_window.title}")

            plan, error = generate_plan(
                task, self.state, self.completed, self.failed
            )

            if error:
                print(f"  Plan error: {error}")
                self.iteration += 1
                continue

            if not plan:
                empty_streak += 1
                if empty_streak >= 2:
                    print("  Two empty plans in a row — task appears complete.")
                    break
                time.sleep(1)
                self.iteration += 1
                continue

            empty_streak = 0
            print(f"  Plan: {len(plan)} action(s)")
            self.execute_plan(plan)
            self.iteration += 1

            if self.task_completed:
                print("  Task marked complete.")
                break

        success_count = sum(1 for s in self.steps if s.result.success)
        total = len(self.steps)
        rate = (success_count / total * 100) if total else 0
        print(
            f"Agent finished | Iterations: {self.iteration} "
            f"| Steps: {total} | Success: {rate:.0f}%"
        )

        return (
            self.task_completed or self.iteration < self.config.max_iterations,
            self.steps,
        )

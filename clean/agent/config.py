"""Agent configuration and step-tracking dataclasses."""

import time
from dataclasses import dataclass, field
from typing import Any

from core.types import ActionResult


@dataclass
class AgentConfig:
    """Runtime settings for the computer-use agent."""

    max_iterations: int = 15
    action_delay: float = 1.0
    screenshot_scale: float = 0.6


@dataclass
class AgentStep:
    """Record of a single action executed during an agent run."""

    iteration: int
    action: str
    target: Any
    value: Any
    reasoning: str
    result: ActionResult
    timestamp: float = field(default_factory=time.time)

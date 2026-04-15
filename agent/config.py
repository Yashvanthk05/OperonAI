import time
from dataclasses import dataclass, field
from typing import Any

from core.types import ActionResult

@dataclass
class AgentConfig:
    max_iterations: int = 15
    action_delay: float = 1.0
    screenshot_scale: float = 0.6

@dataclass
class AgentStep:
    iteration: int
    action: str
    target: Any
    value: Any
    reasoning: str
    result: ActionResult
    timestamp: float = field(default_factory=time.time)

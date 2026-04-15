"""Shared result types for action execution."""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ActionResult:
    """Outcome of a single action execution."""

    success: bool
    message: str
    coordinates: Optional[Tuple[int, int]] = None

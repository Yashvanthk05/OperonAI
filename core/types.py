from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ActionResult:
    success: bool
    message: str
    coordinates: Optional[Tuple[int, int]] = None

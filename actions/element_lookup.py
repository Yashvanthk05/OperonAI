import re
from typing import Optional, Tuple

from core.models import BoundingBox, DesktopState, UIElement


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _token_set(value: str) -> set[str]:
    return {tok for tok in re.split(r"\W+", _normalize_text(value)) if tok}


def _score_name_match(target: str, candidate: str) -> float:
    if not target or not candidate:
        return 0.0

    if target == candidate:
        return 1.0
    if candidate.startswith(target) or target.startswith(candidate):
        return 0.92
    if target in candidate or candidate in target:
        return 0.85

    target_tokens = _token_set(target)
    candidate_tokens = _token_set(candidate)
    if not target_tokens or not candidate_tokens:
        return 0.0

    overlap = target_tokens.intersection(candidate_tokens)
    if not overlap:
        return 0.0

    precision = len(overlap) / len(target_tokens)
    recall = len(overlap) / len(candidate_tokens)
    return (precision * 0.7) + (recall * 0.3)


def find_by_index(
    state: DesktopState, index: int
) -> Optional[Tuple[UIElement, BoundingBox]]:
    if 0 <= index < len(state.interactive_elements):
        el = state.interactive_elements[index]
        return (el, el.bounding_box)
    return None


def find_by_name(
    state: DesktopState,
    name: str,
    control_type: str | None = None,
) -> Optional[Tuple[UIElement, BoundingBox]]:
    target = _normalize_text(name)
    if not target:
        return None

    requested_control = _normalize_text(control_type or "")
    active_title = (
        _normalize_text(state.active_window.title) if state.active_window else ""
    )

    best: Optional[Tuple[UIElement, BoundingBox]] = None
    best_score = 0.0

    for el in state.interactive_elements:
        el_control = _normalize_text(el.control_type)
        if requested_control and el_control != requested_control:
            continue

        name_score = _score_name_match(target, _normalize_text(el.name))
        if name_score <= 0.0:
            continue

        window_score = (
            0.05
            if active_title and active_title in _normalize_text(el.window_name)
            else 0.0
        )
        score = name_score + window_score
        if score > best_score:
            best_score = score
            best = (el, el.bounding_box)

            if score >= 0.99:
                break

    return best


def find_by_uiautomation(name: str) -> Optional[Tuple[int, int]]:
    try:
        import uiautomation as auto

        control = auto.Control(searchDepth=8, Name=name, searchWaitTime=1)
        if control.Exists(maxSearchSeconds=2):
            rect = control.BoundingRectangle
            cx = rect.left + (rect.right - rect.left) // 2
            cy = rect.top + (rect.bottom - rect.top) // 2
            return (cx, cy)
    except Exception:
        pass
    return None

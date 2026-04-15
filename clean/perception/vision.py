"""Vision-model helpers for click-target finding and action verification."""

import base64
import json
from io import BytesIO
from typing import Optional, Tuple

import requests
from PIL import Image

from config import cfg


def image_to_base64(image: Image.Image, fmt: str = "PNG") -> str:
    """Convert a PIL Image to a base64-encoded string."""
    buf = BytesIO()
    image.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _call_vision(prompt: str, images: list[str], timeout: int = 120) -> str:
    """Send a prompt with base64 images to the Ollama vision model."""
    url = f"{cfg.ollama_base_url}/api/generate"
    payload = {
        "model": cfg.vision_model,
        "prompt": prompt,
        "images": images,
        "stream": False,
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json().get("response", "")


def _extract_json_object(text: str) -> Optional[dict]:
    """Extract the first JSON object {...} from raw text."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except Exception:
            return None
    return None


def find_click_target(
    image: Image.Image, target_description: str
) -> Tuple[Optional[int], Optional[int], str]:
    """Ask the vision model to locate a named target in a screenshot.

    Returns (x, y, description) on success, or (None, None, reason) on failure.
    """
    prompt = (
        f'You are analyzing a Windows desktop screenshot.\n'
        f'Find the UI target matching: "{target_description}".\n\n'
        f'Return ONLY a JSON object:\n'
        f'{{"found": true/false, "x": int, "y": int, "description": "..."}}'
    )

    try:
        text = _call_vision(prompt, [image_to_base64(image)])
        data = _extract_json_object(text)
        if not data:
            return None, None, "Could not parse vision response"

        if data.get("found"):
            return data.get("x"), data.get("y"), data.get("description", "")
        return None, None, data.get("description", "Target not found")
    except Exception as exc:
        return None, None, str(exc)


def verify_action_result(
    before: Image.Image,
    after: Image.Image,
    action: str,
    target: str,
) -> Tuple[bool, str]:
    """Compare before/after screenshots to decide if an action succeeded."""
    prompt = (
        f'Compare two screenshots from a Windows desktop automation run.\n'
        f'Action performed: {action} on "{target}"\n\n'
        f'Return ONLY a JSON object:\n'
        f'{{"success": true/false, "description": "..."}}'
    )

    try:
        text = _call_vision(
            prompt,
            [image_to_base64(before), image_to_base64(after)],
        )
        data = _extract_json_object(text)
        if not data:
            return False, "Could not parse verification response"
        return bool(data.get("success", False)), data.get("description", "")
    except Exception as exc:
        return False, str(exc)

import base64
import json
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image

from utils.config import cfg


def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    buffer = BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _call_vision(prompt: str, images: List[str], timeout: int = 120) -> str:
    url = f"{cfg.ollama_base_url}/api/generate"
    payload = {
        "model": cfg.vision_model,
        "prompt": prompt,
        "images": images,
        "stream": False,
    }
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json().get("response", "")


def _extract_json_object(text: str) -> Optional[dict]:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except Exception:
            return None
    return None


def _extract_json_array(text: str) -> List[dict]:
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start:end])
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def describe_screen(image: Image.Image, context: str = "") -> str:
    prompt = f"""You are a Windows desktop assistant analyzing a screenshot.
{context}

Describe what you see on this screen in detail. Focus on:
1. Which app windows are visible
2. The layout and key controls
3. What likely next step should happen

Keep it concise."""

    try:
        return _call_vision(prompt, [image_to_base64(image)])
    except Exception as exc:
        print(f"Vision describe failed: {exc}")
        return ""


def detect_elements(image: Image.Image, task: str) -> List[Dict[str, Any]]:
    prompt = f"""You are analyzing a Windows desktop screenshot.
The user wants to: {task}

Find likely relevant UI targets.
Return ONLY a JSON array where each item has:
- name
- type
- reason"""

    try:
        text = _call_vision(prompt, [image_to_base64(image)])
        return _extract_json_array(text)
    except Exception as exc:
        print(f"Vision detect failed: {exc}")
        return []


def find_click_target(
    image: Image.Image, target_description: str
) -> Tuple[Optional[int], Optional[int], str]:
    prompt = f"""You are analyzing a Windows desktop screenshot.
Find the UI target matching: \"{target_description}\".

Return ONLY JSON object:
{{"found": true/false, "x": int, "y": int, "description": "..."}}

If not found:
{{"found": false, "description": "reason"}}"""

    try:
        text = _call_vision(prompt, [image_to_base64(image)])
        payload = _extract_json_object(text)
        if not payload:
            return None, None, "Could not parse vision response"

        if payload.get("found"):
            return payload.get("x"), payload.get("y"), payload.get("description", "")

        return None, None, payload.get("description", "Target not found")
    except Exception as exc:
        print(f"Vision click target failed: {exc}")
        return None, None, str(exc)


def verify_action_result(
    image_before: Image.Image,
    image_after: Image.Image,
    action: str,
    target: str,
) -> Tuple[bool, str]:
    prompt = f"""Compare two screenshots from a Windows desktop automation run.
Action performed: {action} on \"{target}\"

Return ONLY JSON object:
{{"success": true/false, "description": "..."}}"""

    try:
        text = _call_vision(
            prompt,
            [image_to_base64(image_before), image_to_base64(image_after)],
        )
        payload = _extract_json_object(text)
        if not payload:
            return False, "Could not parse verification response"
        return bool(payload.get("success", False)), payload.get("description", "")
    except Exception as exc:
        print(f"Vision verify failed: {exc}")
        return False, str(exc)

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
import google.generativeai as genai


def load_backend_env() -> None:
    backend_dir = Path(__file__).resolve().parent
    root_dir = backend_dir.parent
    # Keep backend/.env as primary source regardless of current working directory.
    load_dotenv(backend_dir / ".env", override=False)
    load_dotenv(root_dir / ".env", override=False)


def get_required_gemini_key() -> str:
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key or api_key in {"YOUR_KEY_HERE", "YOUR_GEMINI_KEY_HERE", "YOUR_REAL_KEY"}:
        raise RuntimeError("GEMINI_API_KEY is missing. Set a real key in backend/.env.")
    return api_key


def get_text_model() -> str:
    return os.getenv("GEMINI_TEXT_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"


def _extract_json_text(raw_text: str) -> Optional[str]:
    text = (raw_text or "").strip()
    if not text:
        return None

    if text.startswith("```"):
        text = text.strip("`")
        lines = [line for line in text.splitlines() if line.strip().lower() != "json"]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _generate_text(prompt: str) -> str:
    load_backend_env()
    api_key = get_required_gemini_key()
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(get_text_model())
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    )

    return getattr(response, "text", "") or ""


def generate_json_with_retry(prompt: str, strict_prompt: str) -> Optional[Dict[str, Any]]:
    for candidate_prompt in [prompt, strict_prompt]:
        try:
            raw_text = _generate_text(candidate_prompt)
        except Exception:  # noqa: BLE001
            continue
        json_text = _extract_json_text(raw_text)
        if not json_text:
            continue
        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None

"""Swappable image-to-structured-data adapters."""
from __future__ import annotations

import base64
import json
import re
from typing import Protocol
import httpx
from pydantic import ValidationError

from .contracts import Recognition


PROMPT = """You are a STRICT DOCUMENT TRANSCRIBER, not a survey analyst.
The image contains a fixed five-question form. Each question offers FOUR boxes, labeled 1, 2, 3, 4.
For each q1..q5:
 - status answered + integer value 1..4 ONLY if exactly one checkmark is visibly identifiable.
 - status no_answer + null if there is clearly no mark.
 - status multiple + null if conflicting/multiple boxes are marked.
 - status unreadable + null if uncertain, obscured, ambiguous or illegible.
NEVER infer an answer from the question text or from other answers.
Transcribe handwritten free text exactly in its original language (do not correct or polish).
Translate only the recognized text into German faithfully; preserve tone and meaning, no analysis or smoothing.
If a word or translation is unclear, indicate review_required, write only verifiable content, and add a warning.
If the text area is blank, use empty status and two empty strings.
Do not add answers, omit disclaimers, do not invent unreadable content.
Return only one JSON object with keys q1, q2, q3, q4, q5, text, warnings.
Each qN: {"value": 1|2|3|4|null, "status": "answered"|"no_answer"|"multiple"|"unreadable"}.
text: {"original_transcript": string, "source_language": language code or "unknown",
"german_translation": string, "text_status": "translated"|"empty"|"unreadable"|"review_required"}.
warnings: array of brief strings; empty if no observed issues.
A valid JSON schema is required; do not emit Markdown code fences.
"""


class ProviderError(Exception):
    pass


class ImageProvider(Protocol):
    async def recognize(self, jpeg_bytes: bytes) -> tuple[Recognition, str]: ...


def _json_from_message(message: str) -> dict:
    stripped = message.strip()
    # Keep the raw model output separately; tolerate common fenced JSON replies.
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.I)
    obj = json.loads(stripped)
    if not isinstance(obj, dict):
        raise ValueError("response must be a JSON object")
    return obj


class MockProvider:
    """Not AI. Each uploaded image deliberately returns an unverified empty draft."""

    async def recognize(self, jpeg_bytes: bytes) -> tuple[Recognition, str]:
        output = {
            **{f"q{i}": {"value": None, "status": "unreadable"} for i in range(1, 6)},
            "text": {"original_transcript": "", "source_language": "unknown",
                     "german_translation": "", "text_status": "review_required"},
            "warnings": ["DEMO-MODUS: keine KI-Erkennung – manuelle Prüfung erforderlich."],
        }
        return Recognition.model_validate(output), json.dumps(output, ensure_ascii=False)


class OpenRouterProvider:
    def __init__(self, key: str, model: str, *, endpoint: str = "https://openrouter.ai/api/v1/chat/completions"):
        self.key = key
        self.model = model
        self.endpoint = endpoint

    async def recognize(self, jpeg_bytes: bytes) -> tuple[Recognition, str]:
        encoded = base64.b64encode(jpeg_bytes).decode("ascii")
        request_data = {
            "model": self.model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
            ]}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                resp = await client.post(self.endpoint, json=request_data, headers={
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/json",
                    "X-Title": "Form Digitizer Pilot",
                })
            resp.raise_for_status()
            payload = resp.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Model returned non-text response")
            model_data = _json_from_message(content)
            parsed = Recognition.model_validate(model_data)
            return parsed, content
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
            # Never expose keys, image payloads, remote responses or stack traces to end users.
            raise ProviderError("Modellantwort konnte nicht verarbeitet werden. Bitte erneut versuchen oder Modellkonfiguration prüfen.") from exc

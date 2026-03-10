"""
parsers/llm_extractor.py
------------------------
STEP 5 — LLM Fallback Extraction

Called only when JSON-LD and DOM extraction leave critical fields (title or
description) empty.

Primary backend: Google Gemini via `google-generativeai` SDK.
    - Reads GOOGLE_API_KEY from environment.
    - If the key is absent or the SDK is not installed, returns None gracefully.

The model is instructed to return strict JSON only.
Never hallucinates — returns null for unknown fields.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("parsers.llm_extractor")

# JSON schema expected from the model
_EXPECTED_KEYS = {
    "vehicle_brand", "vehicle_model", "model_year", "engine_specs",
    "price_mention", "insurance_provider", "rating", "sentiment",
    "summary", "publication_date_raw",
}

_PROMPT_TEMPLATE = """You are an automotive and insurance market intelligence assistant.
Extract structured information from the text below.
Return ONLY valid JSON with exactly these keys:
{
  "vehicle_brand": string or null,
  "vehicle_model": string or null,
  "model_year": integer or null,
  "engine_specs": string or null,
  "price_mention": string or null,
  "insurance_provider": string or null,
  "rating": float or null,
  "sentiment": "positive" | "neutral" | "negative" | null,
  "summary": string or null,
  "publication_date_raw": string or null
}

Rules:
- Do NOT invent information that is not in the text.
- Return null for any field you cannot find.
- Return ONLY the JSON object — no markdown, no extra text.

Content text:
---
{text}
---
"""

# Max characters sent to the LLM to avoid token / cost limits
_MAX_TEXT_LEN = 8000


def _extract_json_from_response(text: str) -> Optional[Dict[str, Any]]:
    """Strip markdown fences and parse JSON from model response."""
    # Remove triple-backtick fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        # Try to pull the first JSON object with regex
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    logger.warning("LLM response was not valid JSON: %.200s", text)
    return None


def extract_with_llm(clean_text: str) -> Optional[Dict[str, Any]]:
    """
    Send cleaned text to a language model and parse the structured response.

    Args:
        clean_text: Plain text extracted from the cleaned HTML.

    Returns:
        Extraction dict with snake_case keys, or None on failure.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        logger.debug("GOOGLE_API_KEY not set — LLM extraction skipped")
        return None

    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        logger.debug("google-generativeai not installed — LLM extraction skipped")
        return None

    # Truncate to avoid excessive token usage
    text_snippet = clean_text[:_MAX_TEXT_LEN]
    prompt = _PROMPT_TEMPLATE.format(text=text_snippet)

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        raw_text: str = response.text or ""
        logger.debug(
            "LLM response (%d chars): %.200s", len(raw_text), raw_text
        )
        result = _extract_json_from_response(raw_text)
        if result is None:
            return None
        # Ensure required keys exist (fill missing with None)
        for key in _EXPECTED_KEYS:
            result.setdefault(key, None)
        return result
    except Exception as exc:
        logger.error("LLM extraction failed: %s", exc)
        return None

"""Extract salary from job description text using Gemini via OpenRouter.

Used as a fallback when regex-based salary parsing finds nothing.
"""

import json
import logging
import os

import httpx

from app.ingest.salary_parser import ParsedSalary

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-3.1-flash-lite-preview"

SYSTEM_PROMPT = """\
Extract salary information from the following job posting text.
Return a JSON object with these fields:
- "min": minimum salary as a number (no dollar signs or commas), or null
- "max": maximum salary as a number (no dollar signs or commas), or null
- "period": "yearly" or "hourly", or null

If only one salary number is mentioned, use it for both min and max.
If no salary information is found, return {"min": null, "max": null, "period": null}.
Return ONLY the JSON object, no other text."""


def extract_salary_with_llm(
    description_text: str,
    api_key: str | None = None,
) -> ParsedSalary | None:
    """Call Gemini Flash Lite to extract salary from unstructured text.

    Returns ParsedSalary if the model finds salary info, None otherwise.
    """
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set, skipping LLM salary extraction")
        return None

    # Truncate very long descriptions to save tokens
    text = description_text[:4000] if len(description_text) > 4000 else description_text

    try:
        resp = httpx.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        logger.exception("OpenRouter API call failed")
        return None

    try:
        content = resp.json()["choices"][0]["message"]["content"]
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            content = content.rsplit("```", 1)[0]
        data = json.loads(content.strip())
    except (KeyError, IndexError, json.JSONDecodeError):
        logger.warning("Failed to parse LLM salary response: %s", content[:200] if 'content' in dir() else "no content")
        return None

    min_val = data.get("min")
    max_val = data.get("max")
    period = data.get("period")

    if min_val is None and max_val is None:
        return None

    # Normalize: if only one side is set, use it for both
    if min_val is not None and max_val is None:
        max_val = min_val
    elif max_val is not None and min_val is None:
        min_val = max_val

    try:
        min_val = float(min_val)
        max_val = float(max_val)
    except (TypeError, ValueError):
        logger.warning("LLM returned non-numeric salary values: %s", data)
        return None

    # Sanity checks
    if min_val <= 0 or max_val <= 0:
        return None
    if min_val > max_val:
        min_val, max_val = max_val, min_val

    if period not in ("yearly", "hourly"):
        # Infer from value
        period = "hourly" if min_val < 200 else "yearly"

    return ParsedSalary(min_value=min_val, max_value=max_val, period=period)

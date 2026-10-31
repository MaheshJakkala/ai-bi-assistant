import json

import requests

from .config import llm_settings

SYSTEM_PROMPT = """You are an intent classifier for a sales BI assistant.
You do NOT write SQL. Map the user's question onto exactly one intent and
return STRICT JSON with this shape:
{"intent": "<intent>", "params": {...}, "include_returned": <bool>}

Allowed intents:
- total_revenue            params: {}
- top_product              params: {}
- top_region               params: {}
- monthly_trend            params: {}
- compare_months           params: {"month_a": 1-12, "year_a": YYYY, "month_b": 1-12, "year_b": YYYY}
- category_breakdown      params: {}
- channel_breakdown       params: {}
- unsupported              params: {}

Rules:
- Revenue means quantity * unit_price - discount_amount.
- Only completed orders count unless the user explicitly asks to include returned orders.
- If the question cannot be answered by these intents, use "unsupported".
- Never invent products, regions or months that are not mentioned.
- Return JSON only, no markdown, no commentary."""


def _extract_json(content):
    content = (content or "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain JSON")
    return json.loads(content[start : end + 1])


def classify_with_llm(question):
    """Ask the configured LLM for a structured intent.

    Returns a dict on success, or ``None`` when no key is configured. Network or
    parsing failures raise RuntimeError so the caller can fall back safely.
    """
    settings = llm_settings()
    if not settings["enabled"]:
        return None

    payload = {
        "model": settings["model"],
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings['api_key']}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        f"{settings['base_url']}/chat/completions",
        headers=headers,
        json=payload,
        timeout=settings["timeout"],
    )
    if response.status_code != 200:
        raise RuntimeError(f"LLM request failed with HTTP {response.status_code}")

    body = response.json()
    content = body["choices"][0]["message"]["content"]
    parsed = _extract_json(content)
    allowed = {
        "total_revenue", "top_product", "top_region", "monthly_trend",
        "compare_months", "category_breakdown", "channel_breakdown", "unsupported",
    }
    if parsed.get("intent") not in allowed:
        raise ValueError(f"LLM returned an unknown intent: {parsed.get('intent')!r}")
    parsed.setdefault("params", {})
    parsed.setdefault("include_returned", False)
    return parsed

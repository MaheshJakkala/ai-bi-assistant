import re

from .analytics import MONTH_NAMES, available_months, resolve_month_pair

INCLUDE_RETURNED_HINTS = (
    "including returned",
    "include returned",
    "all transactions",
    "all orders",
    "including returns",
    "gross revenue",
)

COMPARE_HINTS = ("compare", "comparison", "change", "between", "vs", "versus", "difference")
TREND_HINTS = ("trend", "over time", "by month", "monthly", "month by month", "progression")
TOP_HINTS = ("highest", "top", "best", "most", "largest", "maximum", "max", "leading", "biggest")
REVENUE_WORDS = ("revenue", "sales", "sale", "turnover", "income", "money", "earned")


def _wants_returned(text):
    return any(hint in text for hint in INCLUDE_RETURNED_HINTS)


def _has_month(text):
    return bool(
        re.search(
            r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*",
            text,
        )
        or re.search(r"\b\d{4}-\d{1,2}\b", text)
        or re.search(r"\b\d{1,2}/\d{4}\b", text)
    )


def heuristic_classify(question, conn=None):
    """Deterministic fallback intent classifier used when no LLM is configured.

    It maps a natural-language question onto a small, fixed set of intents so the
    SQL that actually runs is always templated and reviewed.
    """
    text = (question or "").strip().lower()
    include_returned = _wants_returned(text)
    mentions_revenue = any(word in text for word in REVENUE_WORDS)

    if not text:
        return {"intent": "unsupported", "reason": "empty question"}

    month_count = len(
        re.findall(
            r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
            r"|\b\d{4}-\d{1,2}\b|\b\d{1,2}/\d{4}\b",
            text,
        )
    )

    if any(hint in text for hint in COMPARE_HINTS) and (
        month_count >= 1 or "month" in text
    ):
        pair = resolve_month_pair(conn, text) if conn is not None else None
        params = {}
        if pair:
            (ya, ma), (yb, mb) = pair
            params = {
                "month_a": ma, "year_a": ya,
                "month_b": mb, "year_b": yb,
            }
        return {"intent": "compare_months", "params": params,
                "include_returned": include_returned}

    if any(hint in text for hint in TREND_HINTS) or (
        "month" in text and mentions_revenue and not month_count
    ):
        return {"intent": "monthly_trend", "params": {},
                "include_returned": include_returned}

    if "product" in text and any(hint in text for hint in TOP_HINTS):
        return {"intent": "top_product", "params": {},
                "include_returned": include_returned}

    if "region" in text and any(hint in text for hint in TOP_HINTS):
        return {"intent": "top_region", "params": {},
                "include_returned": include_returned}

    if "category" in text or "categories" in text:
        return {"intent": "category_breakdown", "params": {},
                "include_returned": include_returned}

    if "channel" in text or "online" in text or "retail" in text:
        return {"intent": "channel_breakdown", "params": {},
                "include_returned": include_returned}

    if mentions_revenue or "total" in text:
        return {"intent": "total_revenue", "params": {},
                "include_returned": include_returned}

    return {"intent": "unsupported", "reason": "could not map question to a supported metric"}

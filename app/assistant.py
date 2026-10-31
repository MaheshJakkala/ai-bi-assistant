import sqlite3
from datetime import datetime

from . import analytics
from .config import MAX_RESULT_ROWS
from .llm import classify_with_llm
from .nlp import heuristic_classify
from .sql_guard import UnsafeQueryError, validate_sql

INTENT_HANDLERS = {
    "total_revenue": lambda conn, p, i: analytics.total_revenue(conn, i),
    "top_product": lambda conn, p, i: analytics.revenue_by_product(conn, i),
    "top_region": lambda conn, p, i: analytics.revenue_by_region(conn, i),
    "monthly_trend": lambda conn, p, i: analytics.monthly_trend(conn, i),
    "category_breakdown": lambda conn, p, i: analytics.top_categories(conn, i),
    "channel_breakdown": lambda conn, p, i: analytics.channel_breakdown(conn, i),
}

SUPPORTED_EXAMPLES = [
    "What is the total revenue?",
    "Which product generated the highest revenue?",
    "What is the monthly revenue trend?",
    "Which region generated the highest sales?",
    "How did revenue change between January and February?",
]


class QuestionError(ValueError):
    """Raised for questions we refuse to answer (unsupported or unsafe)."""


def _validate_months(params):
    for key in ("month_a", "month_b"):
        value = params.get(key)
        if not isinstance(value, int) or not 1 <= value <= 12:
            raise QuestionError(f"Invalid month supplied for {key!r}; expected 1-12")
    for key in ("year_a", "year_b"):
        value = params.get(key)
        if not isinstance(value, int) or not 2000 <= value <= 2100:
            raise QuestionError(f"Invalid year supplied for {key!r}; expected 2000-2100")


def _classify(question, conn):
    """Try the LLM first, then fall back to deterministic rules."""
    llm_error = None
    try:
        result = classify_with_llm(question)
        if result is not None:
            intent = result.get("intent", "unsupported")
            if intent == "compare_months" and not result.get("params"):
                raise QuestionError("The comparison needs two explicit months.")
            return result, "llm"
    except Exception as exc:  # noqa: BLE001 - any LLM failure must degrade gracefully
        llm_error = str(exc)

    result = heuristic_classify(question, conn)
    result["llm_error"] = llm_error
    return result, "heuristic"


def answer_question(conn, question):
    if not isinstance(question, str) or not question.strip():
        raise QuestionError("Please enter a question.")

    question = question.strip()
    if len(question) > 500:
        raise QuestionError("Question is too long (maximum 500 characters).")

    classification, source = _classify(question, conn)
    intent = classification.get("intent", "unsupported")
    params = classification.get("params") or {}
    include_returned = bool(classification.get("include_returned", False))

    if intent == "compare_months":
        if not params or "month_a" not in params:
            pair = analytics.resolve_month_pair(conn, question)
            if not pair:
                raise QuestionError(
                    "I could not identify two months to compare. "
                    "Try: 'Compare revenue in January and February'."
                )
            (ya, ma), (yb, mb) = pair
            params = {"month_a": ma, "year_a": ya, "month_b": mb, "year_b": yb}
        _validate_months(params)
        result = analytics.compare_months(
            conn,
            params["month_a"], params["year_a"],
            params["month_b"], params["year_b"],
        )
    elif intent in INTENT_HANDLERS:
        result = INTENT_HANDLERS[intent](conn, params, include_returned)
    else:
        raise QuestionError(
            "I can only answer revenue questions about total revenue, top product, "
            "top region, monthly trend, category/channel breakdown, or month comparisons."
        )

    # Re-validate the templated SQL through the guard as a defence in depth layer.
    try:
        safe_sql = validate_sql(result["sql"], max_rows=MAX_RESULT_ROWS)
    except UnsafeQueryError as exc:
        raise QuestionError(f"Internal query rejected by safety guard: {exc}")

    return {
        "question": question,
        "intent": intent,
        "answer": result["answer"],
        "data": result.get("data", []),
        "sql": safe_sql,
        "chart": result.get("chart"),
        "meta": result.get("meta"),
        "interpreted_by": source,
        "filters": {"include_returned": include_returned},
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

import re

from .config import ALLOWED_TABLES

FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "create", "replace",
    "attach", "detach", "pragma", "vacuum", "reindex", "truncate",
    "grant", "revoke", "begin", "commit", "rollback", "savepoint",
    "load_extension", "exit", "quit",
}

ALLOWED_COLUMNS = {
    "id", "transaction_id", "order_date", "order_year", "order_month",
    "product", "category", "region", "sales_channel", "quantity",
    "unit_price", "discount_amount", "revenue", "status",
    # aggregate aliases
    "month", "total_revenue", "transactions", "units", "txn_count",
    "avg_order_value", "revenue",
    # rejected_rows
    "reason", "raw_row", "rejected_at",
}

_MULTI_STATEMENT = re.compile(r";\s*\S")
_COMMENT = re.compile(r"(--|/\*|\*/|#)")
_TABLE_REF = re.compile(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class UnsafeQueryError(ValueError):
    pass


def _strip_strings(sql):
    return re.sub(r"'(?:''|[^'])*'", "''", sql)


def _strip_literals(sql):
    sql = _strip_strings(sql)
    sql = re.sub(r"\b\d+(?:\.\d+)?\b", "0", sql)
    return sql


def validate_sql(sql, max_rows=200):
    """Validate that ``sql`` is a single, read-only SELECT over allowed tables.

    Returns the normalized SQL string with a bounded LIMIT, or raises
    UnsafeQueryError. This is the guard that stops destructive statements and
    prompt-injected SQL from reaching the database.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise UnsafeQueryError("Empty SQL query")

    cleaned = sql.strip()
    if _COMMENT.search(_strip_strings(cleaned)):
        raise UnsafeQueryError("SQL comments are not allowed")
    if _MULTI_STATEMENT.search(_strip_strings(cleaned)):
        raise UnsafeQueryError("Only a single SQL statement is allowed")
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()

    lowered = _strip_literals(cleaned).lower()

    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise UnsafeQueryError("Only SELECT queries are allowed")

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            raise UnsafeQueryError(f"Forbidden SQL keyword: {keyword.upper()}")

    for table in _TABLE_REF.findall(lowered):
        if table not in ALLOWED_TABLES:
            raise UnsafeQueryError(f"Access to table '{table}' is not allowed")

    if re.search(r"\bsqlite_(master|schema|temp_master)\b", lowered):
        raise UnsafeQueryError("System catalog access is not allowed")

    if re.search(r"\bselect\b", lowered) and not _TABLE_REF.findall(lowered) \
            and not re.search(r"\bdual\b", lowered):
        # Bare "SELECT 1" style queries are pointless for a BI answer.
        if not re.search(r"\bcount\s*\(", lowered):
            raise UnsafeQueryError("Query must read from the transactions table")

    if re.search(r"\binto\b", lowered):
        raise UnsafeQueryError("SELECT INTO is not allowed")

    if "limit" not in lowered:
        cleaned = f"{cleaned} LIMIT {int(max_rows)}"

    return cleaned

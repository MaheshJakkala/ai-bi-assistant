import re
from datetime import datetime

import sqlite3

MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

CURRENCY = "INR"


def money(value):
    return round(float(value or 0), 2)


def fmt_money(value):
    return f"{money(value):,.2f}"


def completed_filter(include_returned=False):
    if include_returned:
        return ""
    return " AND status = 'Completed'"


def total_revenue(conn, include_returned=False):
    sql = (
        "SELECT COUNT(*) AS transactions, COALESCE(SUM(revenue), 0) AS total_revenue "
        "FROM transactions WHERE 1=1" + completed_filter(include_returned)
    )
    row = conn.execute(sql).fetchone()
    return {
        "answer": f"Total revenue is {CURRENCY} {fmt_money(row['total_revenue'])} "
        f"across {row['transactions']} counted transactions.",
        "sql": sql,
        "data": [
            {"metric": "total_revenue", "value": money(row["total_revenue"])},
            {"metric": "transactions_counted", "value": row["transactions"]},
        ],
    }


def revenue_by_product(conn, include_returned=False, top_n=10):
    sql = (
        "SELECT product, COUNT(*) AS transactions, "
        "COALESCE(SUM(quantity), 0) AS units, COALESCE(SUM(revenue), 0) AS revenue "
        "FROM transactions WHERE 1=1"
        + completed_filter(include_returned)
        + " GROUP BY product ORDER BY revenue DESC"
    )
    rows = conn.execute(sql).fetchall()
    data = [
        {
            "product": r["product"],
            "transactions": r["transactions"],
            "units": r["units"],
            "revenue": money(r["revenue"]),
        }
        for r in rows
    ]
    if not data:
        return {"answer": "No transactions found.", "sql": sql, "data": []}
    top = data[0]
    return {
        "answer": f"{top['product']} generated the highest revenue: "
        f"{CURRENCY} {fmt_money(top['revenue'])} from {top['units']} units.",
        "sql": sql,
        "data": data[:top_n],
    }


def revenue_by_region(conn, include_returned=False):
    sql = (
        "SELECT region, COUNT(*) AS transactions, "
        "COALESCE(SUM(quantity), 0) AS units, COALESCE(SUM(revenue), 0) AS revenue "
        "FROM transactions WHERE 1=1"
        + completed_filter(include_returned)
        + " GROUP BY region ORDER BY revenue DESC"
    )
    rows = conn.execute(sql).fetchall()
    data = [
        {
            "region": r["region"],
            "transactions": r["transactions"],
            "units": r["units"],
            "revenue": money(r["revenue"]),
        }
        for r in rows
    ]
    if not data:
        return {"answer": "No transactions found.", "sql": sql, "data": []}
    top = data[0]
    return {
        "answer": f"{top['region']} generated the highest sales: "
        f"{CURRENCY} {fmt_money(top['revenue'])}.",
        "sql": sql,
        "data": data,
    }


def monthly_trend(conn, include_returned=False):
    sql = (
        "SELECT printf('%04d-%02d', order_year, order_month) AS month, "
        "COUNT(*) AS transactions, COALESCE(SUM(revenue), 0) AS revenue "
        "FROM transactions WHERE 1=1"
        + completed_filter(include_returned)
        + " GROUP BY order_year, order_month ORDER BY order_year, order_month"
    )
    rows = conn.execute(sql).fetchall()
    data = [
        {
            "month": r["month"],
            "transactions": r["transactions"],
            "revenue": money(r["revenue"]),
        }
        for r in rows
    ]
    if not data:
        return {"answer": "No transactions found.", "sql": sql, "data": []}
    first, last = data[0], data[-1]
    direction = "increased" if last["revenue"] >= first["revenue"] else "decreased"
    return {
        "answer": f"Monthly revenue {direction} from {CURRENCY} "
        f"{fmt_money(first['revenue'])} in {first['month']} to "
        f"{CURRENCY} {fmt_money(last['revenue'])} in {last['month']}.",
        "sql": sql,
        "data": data,
        "chart": {"type": "line", "x": [d["month"] for d in data],
                  "y": [d["revenue"] for d in data]},
    }


def month_revenue(conn, month, year):
    sql = (
        "SELECT printf('%04d-%02d', order_year, order_month) AS month, "
        "COUNT(*) AS transactions, COALESCE(SUM(revenue), 0) AS revenue "
        "FROM transactions WHERE status = 'Completed' AND order_year = ? "
        "AND order_month = ? GROUP BY month"
    )
    row = conn.execute(sql, (year, month)).fetchone()
    return {
        "month": f"{year:04d}-{month:02d}",
        "transactions": row["transactions"] if row else 0,
        "revenue": money(row["revenue"]) if row else 0.0,
    }


def compare_months(conn, month_a, year_a, month_b, year_b):
    a = month_revenue(conn, month_a, year_a)
    b = month_revenue(conn, month_b, year_b)
    change = round(b["revenue"] - a["revenue"], 2)
    pct = round((change / a["revenue"] * 100), 2) if a["revenue"] else None
    direction = "increased" if change > 0 else ("decreased" if change < 0 else "stayed flat")
    pct_text = f" ({pct:+.2f}%)" if pct is not None else " (no baseline revenue)"
    sql = (
        "SELECT printf('%04d-%02d', order_year, order_month) AS month, "
        "COALESCE(SUM(revenue), 0) AS revenue FROM transactions "
        "WHERE status = 'Completed' "
        f"AND ((order_year = {year_a} AND order_month = {month_a}) "
        f"OR (order_year = {year_b} AND order_month = {month_b})) "
        "GROUP BY month ORDER BY month"
    )
    return {
        "answer": f"Revenue {direction} by {CURRENCY} {fmt_money(abs(change))}{pct_text} "
        f"from {a['month']} to {b['month']}.",
        "sql": sql,
        "data": [
            {"month": a["month"], "revenue": a["revenue"]},
            {"month": b["month"], "revenue": b["revenue"]},
            {"metric": "change", "value": change},
            {"metric": "change_pct", "value": pct},
        ],
        "meta": {"from": a, "to": b, "change": change, "change_pct": pct},
    }


def top_categories(conn, include_returned=False):
    sql = (
        "SELECT category, COUNT(*) AS transactions, COALESCE(SUM(revenue), 0) AS revenue "
        "FROM transactions WHERE 1=1"
        + completed_filter(include_returned)
        + " GROUP BY category ORDER BY revenue DESC"
    )
    rows = conn.execute(sql).fetchall()
    return {
        "answer": "Revenue by category.",
        "sql": sql,
        "data": [
            {"category": r["category"], "transactions": r["transactions"],
             "revenue": money(r["revenue"])}
            for r in rows
        ],
    }


def channel_breakdown(conn, include_returned=False):
    sql = (
        "SELECT sales_channel, COUNT(*) AS transactions, "
        "COALESCE(SUM(revenue), 0) AS revenue FROM transactions WHERE 1=1"
        + completed_filter(include_returned)
        + " GROUP BY sales_channel ORDER BY revenue DESC"
    )
    rows = conn.execute(sql).fetchall()
    return {
        "answer": "Revenue by sales channel.",
        "sql": sql,
        "data": [
            {"sales_channel": r["sales_channel"], "transactions": r["transactions"],
             "revenue": money(r["revenue"])}
            for r in rows
        ],
    }


def available_months(conn):
    rows = conn.execute(
        "SELECT DISTINCT order_year, order_month FROM transactions "
        "ORDER BY order_year, order_month"
    ).fetchall()
    return [(r["order_year"], r["order_month"]) for r in rows]


def parse_month_reference(text, default_year=None):
    """Parse strings such as 'January', 'Jan 2026', '2026-01' or '01/2026'."""
    text = (text or "").strip().lower()
    if not text:
        return None

    m = re.search(r"(\d{4})-(\d{1,2})", text)
    if m:
        return int(m.group(1)), int(m.group(2))

    m = re.search(r"(\d{1,2})/(\d{4})", text)
    if m:
        return int(m.group(2)), int(m.group(1))

    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s*(\d{4})?", text)
    if m:
        month = MONTH_NAMES[m.group(1)]
        year = int(m.group(2)) if m.group(2) else default_year
        return (year, month) if year else None
    return None


def resolve_month_pair(conn, question):
    """Find the two months referenced in a comparison question."""
    text = question.lower()
    found = []
    for match in re.finditer(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s*(\d{4})?", text
    ):
        found.append((match.start(), MONTH_NAMES[match.group(1)], match.group(2)))
    found.sort()
    if len(found) < 2:
        return None
    first, second = found[0], found[1]
    months = available_months(conn)
    default_year = months[-1][0] if months else None

    def build(entry):
        name_month, year_text = entry[1], entry[2]
        year = int(year_text) if year_text else default_year
        if year is None:
            return None
        # If the explicit year has no data, fall back to the year that does.
        years = {y for y, _ in months}
        if year not in years and years:
            year = sorted(years)[-1]
        return year, name_month

    a = build(first)
    b = build(second)
    if not a or not b:
        return None
    return a, b

# Mini AI Business Intelligence Assistant

A small application that lets a business user ask natural-language questions about
sales transactions and returns answers backed by deterministic SQL queries over a
SQLite database. Built for the RSG "AI-Assisted Development Challenge (GET)".

## What it does

Ask things like:

- What is the total revenue?
- Which product generated the highest revenue?
- What is the monthly revenue trend?
- Which region generated the highest sales?
- How did revenue change between January and February?

Every answer comes with the **supporting rows**, the **exact SQL** that produced
them, and the **filters** applied (for example, whether returned orders are
included). Invalid rows in the source CSV are rejected and logged rather than
silently loaded.

## Key results on the supplied dataset

| Metric | Value |
| --- | --- |
| Rows in CSV | 51 |
| Valid transactions loaded | 49 |
| Rejected rows | 2 (`TXN0034` zero quantity, `TXN0051` missing unit price) |
| Completed transactions | 48 |
| Total revenue (completed) | INR 1,439,200.00 |
| Top product by revenue | Monitor — INR 473,000.00 |
| Top region by revenue | South — INR 411,200.00 |
| Jan → Feb change | +INR 24,350.00 (+11.58%) |

## Setup

```bash
# 1. Install dependencies
python3 -m pip install -r requirements.txt

# 2. Seed the SQLite database from the CSV (creates data/sales.db)
python3 -m scripts.seed

# 3. Run the server
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or use the helper script, which seeds only when the database is missing:

```bash
./run.sh
```

Then open http://localhost:8000 for the UI. The API is also documented at
http://localhost:8000/docs.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Dataset status and summary statistics |
| `GET` | `/api/examples` | Example questions for the UI |
| `POST` | `/api/ask` | Ask a natural-language question |
| `POST` | `/api/admin/reload` | Re-load the CSV from disk |

Example request:

```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Which region generated the highest sales?"}'
```

Response (abridged):

```json
{
  "question": "Which region generated the highest sales?",
  "intent": "top_region",
  "answer": "South generated the highest sales: INR 411,200.00.",
  "data": [{"region": "South", "transactions": 13, "units": 208, "revenue": 411200.0}],
  "sql": "SELECT region, COUNT(*) AS transactions, ... GROUP BY region ORDER BY revenue DESC LIMIT 200",
  "interpreted_by": "heuristic",
  "filters": {"include_returned": false}
}
```

Unsupported questions return HTTP `422` with `{"error": "unsupported_question", "detail": "..."}`.

## Data model and storage

CSV → validation → SQLite table `transactions`. A second table `rejected_rows`
stores every row that failed validation together with the reason and the raw
payload, so data quality issues are auditable.

```text
transactions(
  id, transaction_id UNIQUE, order_date, order_year, order_month,
  product, category, region, sales_channel,
  quantity, unit_price, discount_amount, revenue, status
)
rejected_rows(id, transaction_id, reason, raw_row, rejected_at)
```

- `revenue = quantity * unit_price - discount_amount` is computed once at load
  time so every query uses a consistent definition.
- Indexes exist on `status`, `product`, `region`, `(order_year, order_month)`
  and `order_date`.
- Validation rejects: missing/invalid dates, missing text fields, non-numeric or
  negative prices, zero/negative quantities, discounts larger than the gross
  amount, unknown statuses, duplicate transaction IDs, and missing headers.

## Analytics

All figures are computed with SQL against the database, never hard-coded:

| Intent | Query shape |
| --- | --- |
| `total_revenue` | `SUM(revenue)` over completed rows |
| `top_product` | `GROUP BY product ORDER BY SUM(revenue) DESC` |
| `top_region` | `GROUP BY region ORDER BY SUM(revenue) DESC` |
| `monthly_trend` | `GROUP BY order_year, order_month` |
| `compare_months` | revenue for two months + absolute/percentage change |
| `category_breakdown` | `GROUP BY category` |
| `channel_breakdown` | `GROUP BY sales_channel` |

By default only `Completed` orders count. Saying "including returned" (or
"all transactions") switches the filter.

## AI integration and safety

The question → intent step supports two paths:

1. **LLM intent classification** (optional). If `USER_LLM_API_KEY` is set, the
   app asks an OpenAI-compatible chat endpoint to map the question onto one of
   the fixed intents, using a zero-temperature prompt that forbids writing SQL.
2. **Deterministic rule-based classifier** (default/fallback). Regex and keyword
   matching map the question onto the same intents. This means the app works
   completely offline and never fails just because an API key is missing.

Safety is guaranteed by **not letting the model author SQL**:

- The LLM returns only an intent + parameters; SQL comes from reviewed templates.
- Parameters (months, years) are validated against allowed ranges.
- Every templated query is re-checked by `app/sql_guard.py`, which allows only a
  single `SELECT`/`WITH` statement, blocks comments and multi-statements, blocks
  `INSERT/UPDATE/DELETE/DROP/ALTER/PRAGMA/ATTACH/...`, restricts table access to
  an allow-list, blocks `sqlite_master`, and enforces a `LIMIT`.
- The database connection is opened read-only for query answering, so even a
  guard bypass cannot mutate data.
- Questions that do not map to a supported intent are refused with an explicit,
  human-readable message instead of a guessed answer.

This design prevents unsupported/incorrect answers by construction: the set of
questions the app can answer is small and every answer is a direct SQL result.

## Testing

```bash
python3 -m pytest -q
```

44 tests cover CSV validation and rejection rules, revenue math, every analytic
intent against known totals, month comparisons, the SQL safety guard (including
injection payloads), and the HTTP API (valid, invalid, and edge-case requests).

## Known limitations

- The intent set is fixed; genuinely open-ended questions ("why did sales drop?")
  are refused rather than guessed.
- Month comparison understands month names/`YYYY-MM`/`MM/YYYY`, but not relative
  phrasing like "last quarter" or "the previous month".
- Currency is hard-coded to INR (the dataset has no currency column).
- SQLite is a single-file database; not a production multi-user deployment.
- The LLM path only classifies intent — it never generates or executes SQL — so
  it cannot answer questions outside the supported metrics even with a key.
- No authentication on `/api/admin/reload`; acceptable for this exercise, not
  for production.

## Project layout

```text
app/
  config.py       settings + USER_LLM_* environment handling
  db.py           schema, connection helper, dataset stats
  ingest.py       CSV validation and loading (with rejection logging)
  analytics.py    deterministic SQL analytics
  nlp.py          rule-based intent classifier
  llm.py          optional LLM intent classifier
  sql_guard.py    read-only SELECT validator
  assistant.py    orchestration: intent -> safe SQL -> answer
  main.py         FastAPI app and routes
  static/         single-page UI (HTML/CSS/JS)
data/             source CSV (+ generated sales.db, git-ignored)
scripts/seed.py   database seeding CLI
tests/            pytest suite
```

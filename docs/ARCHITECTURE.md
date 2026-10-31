# Architecture

```mermaid
graph TD
    A["Browser UI (app/static)"] -->|"POST /api/ask {question}"| B["FastAPI (app/main.py)"]
    B --> C["assistant.answer_question"]
    C --> D["Intent classification"]
    D -->|"USER_LLM_API_KEY set"| E["LLM classifier (app/llm.py)"]
    D -->|"no key / LLM error"| F["Rule-based classifier (app/nlp.py)"]
    E --> G["Validated intent + params"]
    F --> G
    G --> H["Analytics templates (app/analytics.py)"]
    H --> I["SQL safety guard (app/sql_guard.py)"]
    I --> J["SQLite read-only connection"]
    J --> K["Answer + supporting rows + SQL"]
    K --> A
    L["Sales CSV"] --> M["Validation + ingestion (app/ingest.py)"]
    M --> N[("transactions")]
    M --> O[("rejected_rows")]
    N --> J
```

## Request flow

1. The UI sends the user's question to `POST /api/ask`.
2. `assistant.answer_question` turns the question into an **intent** plus
   parameters. It prefers the LLM classifier when a user key is configured and
   silently falls back to the deterministic rule-based classifier otherwise.
3. The intent selects a **pre-reviewed SQL template** from `analytics.py`. The
   LLM never writes SQL and user text never reaches the database.
4. `sql_guard.validate_sql` re-checks the resulting statement: single
   `SELECT`/`WITH` only, no comments, no multi-statements, no
   `INSERT/UPDATE/DELETE/DROP/ALTER/PRAGMA/ATTACH`, allow-listed tables only, and
   a forced `LIMIT`.
5. The query runs on a **read-only** SQLite connection. The answer, the
   supporting rows, the SQL, and the filters applied are returned together so
   the figure is always traceable.

## Load flow (offline, one-off)

`app/ingest.py` reads the CSV, validates every row, computes
`revenue = quantity * unit_price - discount_amount`, and writes valid rows to
`transactions`. Every invalid row is written to `rejected_rows` with a reason and
the raw payload instead of being dropped silently. The database is seeded at
startup if empty, or explicitly via `python3 -m scripts.seed`.

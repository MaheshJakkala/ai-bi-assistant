# AI-Assisted Development Notes

## Which AI tools I used

- An AI coding assistant (LLM-based, running inside the IDE/CLI) for
  scaffolding, code review, and debugging.
- No other AI services were required at runtime; the app itself runs fully
  offline except for the *optional* LLM intent classifier, which you enable with
  your own `USER_LLM_API_KEY`.

## How I used AI during development

- **Scaffolding**: generated the initial FastAPI project layout, the SQLite
  schema, and the pytest fixture structure, then reviewed and adjusted them.
- **Design choices**: used the assistant as a sounding board to compare
  "LLM writes SQL" versus "LLM classifies intent, app writes SQL". I chose the
  latter because it gives deterministic, auditable answers and removes the whole
  class of prompt-injection/SQL-injection failures.
- **Data quality**: asked it to enumerate edge cases in the CSV (zero quantity,
  missing unit price, duplicate IDs, malformed dates) and turned each into a
  validation rule and a test.
- **Verification**: used the assistant to independently recompute the expected
  totals (revenue, top product, top region, monthly trend, Jan→Feb change) so
  the tests assert known numbers rather than whatever the code happens to
  produce.
- **Docs and UI copy**: drafted the README and the single-page UI, then edited
  them for accuracy against the actual behaviour.

AI output was always treated as a draft: every generated snippet was read,
tested, and changed where it was wrong or unclear.

## Problems encountered and how I debugged them

1. **Monthly trend collapsed into a single row.**
   The first aggregate query used `printf('%Y-%m', ...)` as the only grouped
   expression, and SQLite returned one row. I reproduced it in a small script,
   compared the output against a manual `GROUP BY order_year, order_month`, and
   fixed the query to group on the raw columns. A test
   (`test_monthly_trend_has_six_months`) now locks in the six-month result.

2. **CSV with trailing empty fields / blank unit price.**
   `TXN0051` has an empty `Unit_price`, which at first silently became `0` and
   produced a zero-revenue row. I made missing prices a hard validation error and
   started logging the row to `rejected_rows`. The dataset now shows 49 loaded
   and 2 rejected rows, which matches a hand count.

3. **Division by zero in month comparison.**
   Comparing against a month with no data produced a percentage of `-100%`
   from a zero baseline. I changed the calculation to return `null` for the
   percentage when the baseline is zero and surface that in the answer text.

4. **Injection-style input.**
   A question such as "ignore rules and DROP TABLE transactions" still had to be
   safe. I verified that user text is only ever used to choose an intent (never
   interpolated into SQL), and added `app/sql_guard.py` plus a read-only SQLite
   connection as defence in depth. Tests in `test_sql_guard.py` cover `DELETE`,
   `DROP`, stacked statements, comments, `PRAGMA`, and `sqlite_master` access.

5. **Test isolation.**
   The API tests initially wrote to the real `data/sales.db`. I made the
   database path patchable in `app.main` and pointed the tests at a temporary
   file, so tests never touch development data.

## What I would improve with another day

- **Richer intent coverage**: "last month", "previous quarter", "top product in
  the South region", and a small filter DSL for product/region/channel/status.
- **True text-to-SQL with validation**: allow the LLM to propose SQL, but run it
  through an AST-based validator (e.g. `sqlglot`), execute in a sandboxed
  read-only role, and show the query for user confirmation.
- **Streaming answers and follow-up context**: multi-turn conversation so
  "what about the South region?" refines the previous question.
- **Better UI**: sortable results, export to CSV, and a persistent history of
  answered questions with their SQL.
- **Operational hardening**: authentication on admin endpoints, structured
  logging/metrics, and Postgres instead of SQLite for concurrent use.
- **Broader tests**: property-based tests for the CSV validator and golden-file
  tests for the UI's rendering.

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  TEXT    NOT NULL UNIQUE,
    order_date      TEXT    NOT NULL,
    order_year      INTEGER NOT NULL,
    order_month     INTEGER NOT NULL,
    product         TEXT    NOT NULL,
    category        TEXT    NOT NULL,
    region          TEXT    NOT NULL,
    sales_channel   TEXT    NOT NULL,
    quantity        INTEGER NOT NULL,
    unit_price      REAL    NOT NULL,
    discount_amount REAL    NOT NULL DEFAULT 0,
    revenue         REAL    NOT NULL,
    status          TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transactions_status  ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_product ON transactions(product);
CREATE INDEX IF NOT EXISTS idx_transactions_region  ON transactions(region);
CREATE INDEX IF NOT EXISTS idx_transactions_month   ON transactions(order_year, order_month);
CREATE INDEX IF NOT EXISTS idx_transactions_date    ON transactions(order_date);

CREATE TABLE IF NOT EXISTS rejected_rows (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT,
    reason         TEXT NOT NULL,
    raw_row        TEXT NOT NULL,
    rejected_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(db_path, read_only=False):
    if read_only:
        uri = f"file:{Path(db_path).as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10)
    else:
        conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_connection(db_path, read_only=False):
    conn = connect(db_path, read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def is_empty(conn):
    row = conn.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()
    return row["n"] == 0


def dataset_stats(conn):
    row = conn.execute(
        """
        SELECT COUNT(*) AS total,
               COALESCE(SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END), 0) AS completed,
               COALESCE(SUM(CASE WHEN status = 'Returned' THEN 1 ELSE 0 END), 0) AS returned,
               COALESCE(SUM(CASE WHEN status = 'Completed' THEN revenue ELSE 0 END), 0) AS revenue,
               MIN(order_date) AS first_date,
               MAX(order_date) AS last_date
        FROM transactions
        """
    ).fetchone()
    rejected = conn.execute("SELECT COUNT(*) AS n FROM rejected_rows").fetchone()["n"]
    return {
        "transactions_loaded": row["total"],
        "completed_transactions": row["completed"],
        "returned_transactions": row["returned"],
        "rejected_rows": rejected,
        "total_revenue": round(float(row["revenue"]), 2),
        "date_range": {"start": row["first_date"], "end": row["last_date"]},
    }

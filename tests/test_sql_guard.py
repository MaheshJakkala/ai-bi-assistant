import pytest

from app.sql_guard import UnsafeQueryError, validate_sql


def test_allows_plain_select():
    sql = "SELECT region, SUM(revenue) FROM transactions GROUP BY region"
    out = validate_sql(sql)
    assert out.lower().startswith("select")
    assert "limit" in out.lower()


def test_adds_limit_when_missing():
    out = validate_sql("SELECT * FROM transactions", max_rows=50)
    assert out.strip().endswith("LIMIT 50")


def test_keeps_existing_limit():
    out = validate_sql("SELECT * FROM transactions LIMIT 5", max_rows=50)
    assert out.strip().endswith("LIMIT 5")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM transactions",
        "DROP TABLE transactions",
        "UPDATE transactions SET revenue = 0",
        "INSERT INTO transactions (transaction_id) VALUES ('x')",
        "SELECT * FROM transactions; DROP TABLE transactions",
        "SELECT * FROM transactions -- comment",
        "PRAGMA table_info(transactions)",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM users",
        "ATTACH DATABASE 'evil.db' AS evil",
        "SELECT * FROM transactions UNION SELECT name FROM sqlite_master",
    ],
)
def test_blocks_unsafe_sql(sql):
    with pytest.raises(UnsafeQueryError):
        validate_sql(sql)


def test_blocks_empty_query():
    with pytest.raises(UnsafeQueryError):
        validate_sql("   ")

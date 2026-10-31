import csv

import pytest

from app.db import get_connection
from app.ingest import CsvValidationError, load_csv, normalize_row

HEADERS = [
    "Transaction_Id", "Order_date", "Product", "Category", "Region",
    "Sales_channel", "Quantity", "Unit_price", "Discount_amount", "Status",
]


def write_csv(path, rows, headers=HEADERS):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def valid_row(**overrides):
    row = {
        "Transaction_Id": "TXN9001",
        "Order_date": "03-01-2026",
        "Product": "Monitor",
        "Category": "Electronics",
        "Region": "North",
        "Sales_channel": "Online",
        "Quantity": "2",
        "Unit_price": "1000",
        "Discount_amount": "100",
        "Status": "Completed",
    }
    row.update(overrides)
    return row


def test_dataset_loads_and_rejects_invalid_rows(seeded_db):
    with get_connection(seeded_db) as conn:
        total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        rejected = conn.execute("SELECT COUNT(*) FROM rejected_rows").fetchone()[0]
    assert total == 49
    assert rejected == 2


def test_revenue_is_computed_from_quantity_price_discount(seeded_db):
    with get_connection(seeded_db) as conn:
        row = conn.execute(
            "SELECT quantity, unit_price, discount_amount, revenue "
            "FROM transactions WHERE transaction_id = 'TXN0022'"
        ).fetchone()
    assert row["revenue"] == pytest.approx(4 * 12500 - 2500)


def test_zero_quantity_row_is_rejected(tmp_path, db_path):
    csv_path = write_csv(tmp_path / "rows.csv", [valid_row(Quantity="0")])
    report = load_csv(csv_path, db_path)
    assert report["rows_loaded"] == 0
    assert report["rows_rejected"] == 1
    assert "quantity" in report["rejected"][0]["reason"].lower()


def test_missing_unit_price_is_rejected(tmp_path, db_path):
    csv_path = write_csv(tmp_path / "rows.csv", [valid_row(**{"Unit_price": ""})])
    report = load_csv(csv_path, db_path)
    assert report["rows_loaded"] == 0
    assert "unit_price" in report["rejected"][0]["reason"].lower()


def test_duplicate_transaction_ids_are_rejected(tmp_path, db_path):
    csv_path = write_csv(
        tmp_path / "rows.csv",
        [valid_row(), valid_row(Product="Keyboard")],
    )
    report = load_csv(csv_path, db_path)
    assert report["rows_loaded"] == 1
    assert report["rows_rejected"] == 1
    assert "duplicate" in report["rejected"][0]["reason"].lower()


def test_invalid_date_is_rejected(tmp_path, db_path):
    csv_path = write_csv(tmp_path / "rows.csv", [valid_row(**{"Order_date": "2026-13-45"})])
    report = load_csv(csv_path, db_path)
    assert report["rows_rejected"] == 1


def test_missing_columns_raise(tmp_path, db_path):
    csv_path = write_csv(
        tmp_path / "rows.csv", [valid_row()], headers=HEADERS[:-1]
    )
    with pytest.raises(CsvValidationError):
        load_csv(csv_path, db_path)


def test_normalize_row_uppercases_status():
    row = normalize_row(valid_row(Status="completed"))
    assert row["status"] == "Completed"

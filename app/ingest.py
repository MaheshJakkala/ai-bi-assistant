import csv
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .db import get_connection, init_db, is_empty

REQUIRED_COLUMNS = [
    "Transaction_Id",
    "Order_date",
    "Product",
    "Category",
    "Region",
    "Sales_channel",
    "Quantity",
    "Unit_price",
    "Discount_amount",
    "Status",
]

DATE_FORMAT = "%d-%m-%Y"


class CsvValidationError(ValueError):
    pass


def _parse_date(value):
    value = (value or "").strip()
    if not value:
        raise ValueError("missing order date")
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError:
        raise ValueError(f"invalid order date: {value!r}")


def _parse_int(value, field):
    raw = (value or "").strip()
    if raw == "":
        raise ValueError(f"missing {field}")
    try:
        number = int(Decimal(raw))
    except (InvalidOperation, ValueError):
        raise ValueError(f"invalid {field}: {raw!r}")
    return number


def _parse_decimal(value, field, required=True):
    raw = (value or "").strip()
    if raw == "":
        if required:
            raise ValueError(f"missing {field}")
        return Decimal("0")
    try:
        number = Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"invalid {field}: {raw!r}")
    if number < 0:
        raise ValueError(f"negative {field}: {raw!r}")
    return number


def _clean_text(value, field):
    text = (value or "").strip()
    if not text:
        raise ValueError(f"missing {field}")
    return text


def validate_headers(fieldnames):
    if not fieldnames:
        raise CsvValidationError("CSV has no header row")
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        raise CsvValidationError(f"CSV is missing required columns: {', '.join(missing)}")


def normalize_row(raw):
    """Validate a single CSV row and return a normalized dict.

    Raises ValueError with a human-readable reason for invalid rows.
    """
    transaction_id = _clean_text(raw.get("Transaction_Id"), "transaction id")
    if not re.fullmatch(r"[A-Za-z0-9\-_]+", transaction_id):
        raise ValueError(f"invalid transaction id: {transaction_id!r}")

    order_date = _parse_date(raw.get("Order_date"))
    product = _clean_text(raw.get("Product"), "product")
    category = _clean_text(raw.get("Category"), "category")
    region = _clean_text(raw.get("Region"), "region")
    sales_channel = _clean_text(raw.get("Sales_channel"), "sales channel")

    quantity = _parse_int(raw.get("Quantity"), "quantity")
    if quantity <= 0:
        raise ValueError(f"quantity must be greater than zero (got {quantity})")

    unit_price = _parse_decimal(raw.get("Unit_price"), "unit_price", required=True)
    if unit_price <= 0:
        raise ValueError(f"unit_price must be greater than zero (got {unit_price})")

    discount = _parse_decimal(raw.get("Discount_amount"), "discount_amount", required=False)
    gross = unit_price * quantity
    if discount > gross:
        raise ValueError(f"discount {discount} exceeds gross amount {gross}")

    status = _clean_text(raw.get("Status"), "status")
    status = status[:1].upper() + status[1:].lower()
    if status not in {"Completed", "Returned", "Cancelled", "Pending", "Refunded"}:
        raise ValueError(f"unknown status: {status!r}")

    revenue = gross - discount
    return {
        "transaction_id": transaction_id,
        "order_date": order_date.isoformat(),
        "order_year": order_date.year,
        "order_month": order_date.month,
        "product": product,
        "category": category,
        "region": region,
        "sales_channel": sales_channel,
        "quantity": quantity,
        "unit_price": float(unit_price),
        "discount_amount": float(discount),
        "revenue": float(revenue),
        "status": status,
    }


def load_csv(csv_path, db_path, replace=True):
    """Load and validate the sales CSV into SQLite.

    Invalid rows are skipped and recorded in ``rejected_rows`` with the reason,
    so they remain auditable instead of silently disappearing.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    init_db(db_path)

    accepted = []
    rejected = []
    seen_ids = set()

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        validate_headers(reader.fieldnames)
        for line_number, raw in enumerate(reader, start=2):
            try:
                row = normalize_row(raw)
                if row["transaction_id"] in seen_ids:
                    raise ValueError(f"duplicate transaction id: {row['transaction_id']}")
                seen_ids.add(row["transaction_id"])
                accepted.append(row)
            except ValueError as exc:
                rejected.append(
                    {
                        "transaction_id": (raw.get("Transaction_Id") or "").strip() or None,
                        "reason": str(exc),
                        "raw_row": json.dumps(raw),
                        "line_number": line_number,
                    }
                )

    with get_connection(db_path) as conn:
        if replace:
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM rejected_rows")
        elif not is_empty(conn):
            raise CsvValidationError(
                "Database already contains transactions; use replace=True to reload"
            )

        conn.executemany(
            """
            INSERT OR IGNORE INTO transactions (
                transaction_id, order_date, order_year, order_month, product,
                category, region, sales_channel, quantity, unit_price,
                discount_amount, revenue, status
            ) VALUES (
                :transaction_id, :order_date, :order_year, :order_month, :product,
                :category, :region, :sales_channel, :quantity, :unit_price,
                :discount_amount, :revenue, :status
            )
            """,
            accepted,
        )
        conn.executemany(
            """
            INSERT INTO rejected_rows (transaction_id, reason, raw_row)
            VALUES (:transaction_id, :reason, :raw_row)
            """,
            rejected,
        )
        conn.commit()

    return {
        "rows_read": len(accepted) + len(rejected),
        "rows_loaded": len(accepted),
        "rows_rejected": len(rejected),
        "rejected": [
            {
                "line": r["line_number"],
                "transaction_id": r["transaction_id"],
                "reason": r["reason"],
            }
            for r in rejected
        ],
    }

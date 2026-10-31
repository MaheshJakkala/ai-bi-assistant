"""Seed the SQLite database from the sales CSV.

Usage:
    python -m scripts.seed             # uses default data/sales_transactions.csv
    python -m scripts.seed <csv_path>  # uses an explicit CSV file
"""

import json
import sys

from app.config import DEFAULT_CSV_PATH, DEFAULT_DB_PATH
from app.ingest import load_csv


def main(argv):
    csv_path = argv[1] if len(argv) > 1 else DEFAULT_CSV_PATH
    report = load_csv(csv_path, DEFAULT_DB_PATH, replace=True)
    print(json.dumps(report, indent=2))
    if report["rows_rejected"]:
        print(f"\nRejected {report['rows_rejected']} invalid row(s):")
        for row in report["rejected"]:
            print(f"  line {row['line']} ({row['transaction_id']}): {row['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

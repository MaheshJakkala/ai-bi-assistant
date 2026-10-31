#!/usr/bin/env bash
# Seed the database and start the development server.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f data/sales.db ]; then
  echo "Seeding database from data/sales_transactions.csv ..."
  python3 -m scripts.seed
fi

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload

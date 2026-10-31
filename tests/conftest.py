import pytest

from app.config import DEFAULT_CSV_PATH
from app.db import get_connection, init_db
from app.ingest import load_csv


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test_sales.db"


@pytest.fixture()
def seeded_db(db_path):
    load_csv(DEFAULT_CSV_PATH, db_path, replace=True)
    return db_path


@pytest.fixture()
def conn(seeded_db):
    with get_connection(seeded_db) as connection:
        yield connection

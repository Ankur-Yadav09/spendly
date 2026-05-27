import pytest
import database.db as db_module
from database.db import init_db, seed_db


@pytest.fixture
def db_path(tmp_path):
    """Redirect DB_PATH to a temp file for the duration of the test."""
    test_db = str(tmp_path / "test_spendly.db")
    original = db_module.DB_PATH
    db_module.DB_PATH = test_db
    yield test_db
    db_module.DB_PATH = original


@pytest.fixture
def initialized_db(db_path):
    """Provide an initialized (tables created) temp database."""
    init_db()
    return db_path


@pytest.fixture
def seeded_db(initialized_db):
    """Provide an initialized and seeded temp database."""
    seed_db()
    return initialized_db

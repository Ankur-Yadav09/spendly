import re
import sqlite3
import pytest
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db


class TestGetDb:
    def test_returns_connection(self, initialized_db):
        conn = get_db()
        assert conn is not None
        conn.close()

    def test_row_factory_is_sqlite_row(self, initialized_db):
        conn = get_db()
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Test", "t@t.com", "hash")
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", ("t@t.com",)
        ).fetchone()
        assert row["email"] == "t@t.com"
        assert row["name"] == "Test"
        conn.close()

    def test_foreign_keys_enforced(self, initialized_db):
        conn = get_db()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date) VALUES (?, ?, ?, ?)",
                (9999, 100.0, "Food", "2026-05-01")
            )
            conn.commit()
        conn.close()


class TestInitDb:
    def test_creates_users_table(self, initialized_db):
        conn = get_db()
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        assert result is not None
        conn.close()

    def test_creates_expenses_table(self, initialized_db):
        conn = get_db()
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'"
        ).fetchone()
        assert result is not None
        conn.close()

    def test_idempotent_safe_to_call_twice(self, initialized_db):
        # Calling init_db() a second time must not raise
        init_db()

    def test_users_table_has_correct_columns(self, initialized_db):
        conn = get_db()
        info = conn.execute("PRAGMA table_info(users)").fetchall()
        col_names = [row["name"] for row in info]
        for expected in ["id", "name", "email", "password_hash", "created_at"]:
            assert expected in col_names
        conn.close()

    def test_expenses_table_has_correct_columns(self, initialized_db):
        conn = get_db()
        info = conn.execute("PRAGMA table_info(expenses)").fetchall()
        col_names = [row["name"] for row in info]
        for expected in ["id", "user_id", "amount", "category", "date", "description", "created_at"]:
            assert expected in col_names
        conn.close()

    def test_email_unique_constraint(self, initialized_db):
        conn = get_db()
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("A", "dup@test.com", "hash")
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("B", "dup@test.com", "hash")
            )
            conn.commit()
        conn.close()


class TestSeedDb:
    def test_creates_demo_user(self, seeded_db):
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        assert user is not None
        assert user["name"] == "Demo User"
        conn.close()

    def test_demo_password_is_hashed(self, seeded_db):
        conn = get_db()
        user = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        assert user["password_hash"] != "demo123"
        assert check_password_hash(user["password_hash"], "demo123")
        conn.close()

    def test_creates_eight_expenses(self, seeded_db):
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        assert count == 8
        conn.close()

    def test_all_expenses_belong_to_demo_user(self, seeded_db):
        conn = get_db()
        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()
        orphaned = conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id != ?", (user["id"],)
        ).fetchone()[0]
        assert orphaned == 0
        conn.close()

    def test_all_required_categories_present(self, seeded_db):
        conn = get_db()
        rows = conn.execute("SELECT DISTINCT category FROM expenses").fetchall()
        found_categories = {row["category"] for row in rows}
        required = {"Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"}
        assert required == found_categories
        conn.close()

    def test_dates_are_yyyy_mm_dd_format(self, seeded_db):
        conn = get_db()
        rows = conn.execute("SELECT date FROM expenses").fetchall()
        pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for row in rows:
            assert pattern.match(row["date"]), f"Bad date format: {row['date']}"
        conn.close()

    def test_amounts_are_positive_floats(self, seeded_db):
        conn = get_db()
        rows = conn.execute("SELECT amount FROM expenses").fetchall()
        for row in rows:
            assert isinstance(row["amount"], float)
            assert row["amount"] > 0
        conn.close()

    def test_idempotent_no_duplicate_on_second_call(self, seeded_db):
        seed_db()  # Call a second time — must be a no-op
        conn = get_db()
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        expense_count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        assert user_count == 1
        assert expense_count == 8
        conn.close()

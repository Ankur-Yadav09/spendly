import pytest
from werkzeug.security import generate_password_hash

import database.db as db_module
from database.db import get_db, create_user
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)
from app import app as flask_app


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def app(seeded_db):
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def empty_user_id(initialized_db):
    """Insert a user with no expenses; return their id."""
    create_user("Empty User", "empty@test.com", generate_password_hash("pass1234"))
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("empty@test.com",)
    ).fetchone()
    conn.close()
    return row["id"]


def seed_user_id(seeded_db):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()
    conn.close()
    return row["id"]


# ------------------------------------------------------------------ #
# get_user_by_id                                                      #
# ------------------------------------------------------------------ #

class TestGetUserById:

    def test_valid_id_returns_dict(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_user_by_id(uid)
        assert result is not None
        assert result["name"] == "Demo User"
        assert result["email"] == "demo@spendly.com"

    def test_member_since_format(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_user_by_id(uid)
        parts = result["member_since"].split()
        assert len(parts) == 2
        assert parts[1].isdigit()

    def test_nonexistent_id_returns_none(self, initialized_db):
        assert get_user_by_id(99999) is None


# ------------------------------------------------------------------ #
# get_summary_stats                                                   #
# ------------------------------------------------------------------ #

class TestGetSummaryStats:

    def test_with_expenses_returns_correct_total(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_summary_stats(uid)
        assert result["total_spent"] == "5,910.00"

    def test_with_expenses_returns_correct_count(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_summary_stats(uid)
        assert result["transaction_count"] == 8

    def test_with_expenses_top_category_is_shopping(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_summary_stats(uid)
        assert result["top_category"] == "Shopping"

    def test_no_expenses_returns_zeros(self, empty_user_id):
        result = get_summary_stats(empty_user_id)
        assert result["total_spent"] == "0.00"
        assert result["transaction_count"] == 0
        assert result["top_category"] == "—"


# ------------------------------------------------------------------ #
# get_recent_transactions                                             #
# ------------------------------------------------------------------ #

class TestGetRecentTransactions:

    def test_with_expenses_returns_list(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_recent_transactions(uid)
        assert isinstance(result, list)
        assert len(result) == 8

    def test_each_item_has_required_keys(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_recent_transactions(uid)
        for tx in result:
            assert "date" in tx
            assert "description" in tx
            assert "category" in tx
            assert "amount" in tx

    def test_ordered_newest_first(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_recent_transactions(uid)
        assert result[0]["description"] == "Restaurant dinner"
        assert result[-1]["description"] == "Grocery run"

    def test_no_expenses_returns_empty_list(self, empty_user_id):
        result = get_recent_transactions(empty_user_id)
        assert result == []

    def test_limit_is_respected(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_recent_transactions(uid, limit=3)
        assert len(result) == 3


# ------------------------------------------------------------------ #
# get_category_breakdown                                              #
# ------------------------------------------------------------------ #

class TestGetCategoryBreakdown:

    def test_with_expenses_returns_all_categories(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_category_breakdown(uid)
        assert len(result) == 7

    def test_ordered_by_amount_desc(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_category_breakdown(uid)
        assert result[0]["name"] == "Shopping"

    def test_percentages_sum_to_100(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_category_breakdown(uid)
        assert sum(cat["percentage"] for cat in result) == 100

    def test_each_item_has_required_keys(self, seeded_db):
        conn = get_db()
        uid = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
        ).fetchone()["id"]
        conn.close()

        result = get_category_breakdown(uid)
        for cat in result:
            assert "name" in cat
            assert "amount" in cat
            assert "percentage" in cat
            assert isinstance(cat["percentage"], int)

    def test_no_expenses_returns_empty_list(self, empty_user_id):
        result = get_category_breakdown(empty_user_id)
        assert result == []


# ------------------------------------------------------------------ #
# GET /profile route                                                  #
# ------------------------------------------------------------------ #

class TestProfileRoute:

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def _login_as_demo(self, client):
        client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})

    def test_authenticated_returns_200(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert response.status_code == 200

    def test_shows_real_user_name(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert b"Demo User" in response.data

    def test_shows_real_user_email(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert b"demo@spendly.com" in response.data

    def test_shows_rupee_symbol(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert "₹".encode() in response.data

    def test_shows_correct_total_spent(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert b"5,910.00" in response.data

    def test_shows_correct_transaction_count(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert b"8" in response.data

    def test_shows_correct_top_category(self, client):
        self._login_as_demo(client)
        response = client.get("/profile")
        assert b"Shopping" in response.data

    def test_new_user_shows_zero_spent(self, app, initialized_db):
        create_user("New User", "new@test.com", generate_password_hash("newpass1"))
        client = app.test_client()
        client.post("/login", data={"email": "new@test.com", "password": "newpass1"})
        response = client.get("/profile")
        assert response.status_code == 200
        assert b"0.00" in response.data

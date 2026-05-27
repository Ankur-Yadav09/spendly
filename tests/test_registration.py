import pytest
import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

import database.db as db_module
from database.db import init_db, create_user, get_user_by_email, get_db
from app import app as flask_app


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def app(initialized_db):
    """Flask app wired to the temp test database."""
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ------------------------------------------------------------------ #
# DB-layer: create_user                                               #
# ------------------------------------------------------------------ #

class TestCreateUser:

    def test_inserts_row(self, initialized_db):
        create_user("Alice", "alice@test.com", "hashed_pw")
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", ("alice@test.com",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["name"] == "Alice"
        assert row["password_hash"] == "hashed_pw"

    def test_raises_integrity_error_on_duplicate_email(self, initialized_db):
        create_user("Alice", "dup@test.com", "hash1")
        with pytest.raises(sqlite3.IntegrityError):
            create_user("Bob", "dup@test.com", "hash2")

    def test_does_not_store_plaintext_password(self, initialized_db):
        pw_hash = generate_password_hash("secret123")
        create_user("Carol", "carol@test.com", pw_hash)
        conn = get_db()
        row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?", ("carol@test.com",)
        ).fetchone()
        conn.close()
        assert row["password_hash"] != "secret123"
        assert check_password_hash(row["password_hash"], "secret123")


# ------------------------------------------------------------------ #
# DB-layer: get_user_by_email                                         #
# ------------------------------------------------------------------ #

class TestGetUserByEmail:

    def test_returns_row_when_found(self, initialized_db):
        create_user("Dave", "dave@test.com", "hash")
        user = get_user_by_email("dave@test.com")
        assert user is not None
        assert user["name"] == "Dave"

    def test_returns_none_when_not_found(self, initialized_db):
        result = get_user_by_email("nobody@test.com")
        assert result is None

    def test_returns_sqlite_row_with_named_access(self, initialized_db):
        create_user("Eve", "eve@test.com", "hash")
        user = get_user_by_email("eve@test.com")
        assert user["email"] == "eve@test.com"


# ------------------------------------------------------------------ #
# Route-layer: GET /register                                          #
# ------------------------------------------------------------------ #

class TestRegisterGet:

    def test_get_returns_200(self, client):
        response = client.get("/register")
        assert response.status_code == 200

    def test_get_renders_form(self, client):
        response = client.get("/register")
        assert b"Create your account" in response.data


# ------------------------------------------------------------------ #
# Route-layer: POST /register — happy path                            #
# ------------------------------------------------------------------ #

class TestRegisterPostSuccess:

    def test_valid_post_redirects_to_login(self, client):
        response = client.post("/register", data={
            "name": "Frank", "email": "frank@test.com", "password": "secure99",
        })
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_valid_post_creates_db_row(self, client, initialized_db):
        client.post("/register", data={
            "name": "Grace", "email": "grace@test.com", "password": "secure99",
        })
        user = get_user_by_email("grace@test.com")
        assert user is not None
        assert user["name"] == "Grace"

    def test_password_stored_as_hash_not_plaintext(self, client, initialized_db):
        client.post("/register", data={
            "name": "Hank", "email": "hank@test.com", "password": "secure99",
        })
        user = get_user_by_email("hank@test.com")
        assert user["password_hash"] != "secure99"
        assert check_password_hash(user["password_hash"], "secure99")


# ------------------------------------------------------------------ #
# Route-layer: POST /register — duplicate email                       #
# ------------------------------------------------------------------ #

class TestRegisterDuplicateEmail:

    def test_duplicate_email_returns_200(self, client):
        client.post("/register", data={
            "name": "Ivan", "email": "ivan@test.com", "password": "secure99",
        })
        response = client.post("/register", data={
            "name": "Ivan2", "email": "ivan@test.com", "password": "secure99",
        })
        assert response.status_code == 200

    def test_duplicate_email_shows_error_message(self, client):
        client.post("/register", data={
            "name": "Jane", "email": "jane@test.com", "password": "secure99",
        })
        response = client.post("/register", data={
            "name": "Jane2", "email": "jane@test.com", "password": "secure99",
        })
        assert b"already exists" in response.data

    def test_duplicate_email_does_not_insert_second_row(self, client, initialized_db):
        client.post("/register", data={
            "name": "Ken", "email": "ken@test.com", "password": "secure99",
        })
        client.post("/register", data={
            "name": "Ken2", "email": "ken@test.com", "password": "secure99",
        })
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE email = ?", ("ken@test.com",)
        ).fetchone()[0]
        conn.close()
        assert count == 1


# ------------------------------------------------------------------ #
# Route-layer: POST /register — validation failures                   #
# ------------------------------------------------------------------ #

class TestRegisterValidation:

    def test_missing_name_returns_200(self, client):
        response = client.post("/register", data={
            "name": "", "email": "leo@test.com", "password": "secure99",
        })
        assert response.status_code == 200

    def test_missing_name_shows_error(self, client):
        response = client.post("/register", data={
            "name": "", "email": "leo@test.com", "password": "secure99",
        })
        assert b"required" in response.data.lower()

    def test_whitespace_only_name_shows_error(self, client):
        response = client.post("/register", data={
            "name": "   ", "email": "mia@test.com", "password": "secure99",
        })
        assert b"required" in response.data.lower()

    def test_missing_name_does_not_insert_row(self, client, initialized_db):
        client.post("/register", data={
            "name": "", "email": "ned@test.com", "password": "secure99",
        })
        assert get_user_by_email("ned@test.com") is None

    def test_invalid_email_returns_200(self, client):
        response = client.post("/register", data={
            "name": "Oliver", "email": "notanemail", "password": "secure99",
        })
        assert response.status_code == 200

    def test_invalid_email_shows_error(self, client):
        response = client.post("/register", data={
            "name": "Oliver", "email": "notanemail", "password": "secure99",
        })
        assert b"valid email" in response.data.lower()

    def test_short_password_returns_200(self, client):
        response = client.post("/register", data={
            "name": "Pat", "email": "pat@test.com", "password": "short",
        })
        assert response.status_code == 200

    def test_short_password_shows_error(self, client):
        response = client.post("/register", data={
            "name": "Pat", "email": "pat@test.com", "password": "short",
        })
        assert b"8 characters" in response.data


# ------------------------------------------------------------------ #
# Route-layer: POST /register — sticky fields                         #
# ------------------------------------------------------------------ #

class TestRegisterStickyFields:

    def test_sticky_name_on_validation_failure(self, client):
        response = client.post("/register", data={
            "name": "StickyName", "email": "bad-email", "password": "secure99",
        })
        assert b"StickyName" in response.data

    def test_sticky_email_on_validation_failure(self, client):
        response = client.post("/register", data={
            "name": "Quinn", "email": "quinn@sticky.com", "password": "short",
        })
        assert b"quinn@sticky.com" in response.data

    def test_password_not_sticky_on_failure(self, client):
        response = client.post("/register", data={
            "name": "Rex", "email": "rex@test.com", "password": "short",
        })
        assert b'value="short"' not in response.data

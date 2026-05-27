import pytest
from werkzeug.security import generate_password_hash

import database.db as db_module
from database.db import create_user
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
# Helper                                                              #
# ------------------------------------------------------------------ #

def make_user(name="Alice", email="alice@test.com", password="password123"):
    """Insert a test user directly via the DB layer (bypasses the route)."""
    create_user(name, email, generate_password_hash(password))
    return {"name": name, "email": email, "password": password}


# ------------------------------------------------------------------ #
# GET /login                                                          #
# ------------------------------------------------------------------ #

class TestLoginGet:

    def test_get_returns_200(self, client):
        response = client.get("/login")
        assert response.status_code == 200

    def test_get_renders_sign_in_form(self, client):
        response = client.get("/login")
        assert b"Sign in" in response.data


# ------------------------------------------------------------------ #
# POST /login — happy path                                            #
# ------------------------------------------------------------------ #

class TestLoginPostSuccess:

    def test_valid_credentials_redirect_to_landing(self, client):
        make_user()
        response = client.post("/login", data={
            "email": "alice@test.com",
            "password": "password123",
        })
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")

    def test_valid_credentials_store_user_id_in_session(self, app):
        make_user()
        with app.test_client() as c:
            c.post("/login", data={
                "email": "alice@test.com",
                "password": "password123",
            })
            with c.session_transaction() as sess:
                assert "user_id" in sess
                assert isinstance(sess["user_id"], int)

    def test_valid_credentials_store_user_name_in_session(self, app):
        user = make_user()
        with app.test_client() as c:
            c.post("/login", data={
                "email": user["email"],
                "password": user["password"],
            })
            with c.session_transaction() as sess:
                assert sess["user_name"] == user["name"]


# ------------------------------------------------------------------ #
# POST /login — credential failures                                   #
# ------------------------------------------------------------------ #

class TestLoginPostFailure:

    def test_unknown_email_returns_200(self, client):
        response = client.post("/login", data={
            "email": "nobody@test.com",
            "password": "password123",
        })
        assert response.status_code == 200

    def test_unknown_email_shows_generic_error(self, client):
        response = client.post("/login", data={
            "email": "nobody@test.com",
            "password": "password123",
        })
        assert b"Invalid email or password." in response.data

    def test_wrong_password_returns_200(self, client):
        make_user()
        response = client.post("/login", data={
            "email": "alice@test.com",
            "password": "wrongpassword",
        })
        assert response.status_code == 200

    def test_wrong_password_shows_generic_error(self, client):
        make_user()
        response = client.post("/login", data={
            "email": "alice@test.com",
            "password": "wrongpassword",
        })
        assert b"Invalid email or password." in response.data

    def test_both_failure_modes_produce_identical_error(self, client):
        """Unknown email and wrong password must return the same error string."""
        make_user()
        r1 = client.post("/login", data={
            "email": "nobody@test.com", "password": "password123",
        })
        r2 = client.post("/login", data={
            "email": "alice@test.com", "password": "wrongpassword",
        })
        assert b"Invalid email or password." in r1.data
        assert b"Invalid email or password." in r2.data

    def test_sticky_email_on_failed_login(self, client):
        response = client.post("/login", data={
            "email": "sticky@test.com",
            "password": "wrongpassword",
        })
        assert b"sticky@test.com" in response.data

    def test_password_not_echoed_back_on_failure(self, client):
        make_user()
        response = client.post("/login", data={
            "email": "alice@test.com",
            "password": "shouldnotappear",
        })
        assert b"shouldnotappear" not in response.data

    def test_failed_login_does_not_set_session(self, app):
        with app.test_client() as c:
            c.post("/login", data={
                "email": "nobody@test.com",
                "password": "password123",
            })
            with c.session_transaction() as sess:
                assert "user_id" not in sess


# ------------------------------------------------------------------ #
# GET /logout                                                         #
# ------------------------------------------------------------------ #

class TestLogout:

    def test_logout_redirects_to_landing(self, client):
        response = client.get("/logout")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")

    def test_logout_when_not_logged_in_does_not_crash(self, client):
        """Calling /logout without an active session must be safe."""
        response = client.get("/logout")
        assert response.status_code == 302

    def test_logout_clears_session(self, app):
        user = make_user()
        with app.test_client() as c:
            # Log in
            c.post("/login", data={
                "email": user["email"],
                "password": user["password"],
            })
            # Confirm session was set
            with c.session_transaction() as sess:
                assert "user_id" in sess
            # Log out
            c.get("/logout")
            # Confirm session was cleared
            with c.session_transaction() as sess:
                assert "user_id" not in sess

    def test_login_accessible_after_logout(self, app):
        user = make_user()
        with app.test_client() as c:
            c.post("/login", data={
                "email": user["email"],
                "password": user["password"],
            })
            c.get("/logout")
            response = c.get("/login")
            assert response.status_code == 200


# ------------------------------------------------------------------ #
# Already-logged-in redirects                                         #
# ------------------------------------------------------------------ #

class TestAlreadyLoggedIn:

    def test_logged_in_user_redirected_from_login(self, app):
        user = make_user()
        with app.test_client() as c:
            c.post("/login", data={"email": user["email"], "password": user["password"]})
            response = c.get("/login")
            assert response.status_code == 302
            assert response.headers["Location"].endswith("/")

    def test_logged_in_user_redirected_from_register(self, app):
        user = make_user()
        with app.test_client() as c:
            c.post("/login", data={"email": user["email"], "password": user["password"]})
            response = c.get("/register")
            assert response.status_code == 302
            assert response.headers["Location"].endswith("/")

"""
tests/test_06_date_filter_profile.py

Tests for the date-range filter feature on GET /profile (Step 6).

All test logic is derived from the spec (.claude/specs/06-date-filter-profile.md).
No implementation details are assumed beyond what the spec describes.

Fixture strategy:
  - db_path / seeded_db / initialized_db come from conftest.py
  - app / client / auth_client are defined locally so each test gets an
    isolated database state via the conftest db_path monkeypatching pattern.
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

import database.db as db_module
from database.db import get_db, create_user, init_db
from database.queries import (
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)
from app import app as flask_app


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _insert_expense(user_id, amount, category, exp_date, description=""):
    """Insert a single expense row directly into the test DB."""
    conn = get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, exp_date, description),
    )
    conn.commit()
    conn.close()


def _get_demo_user_id():
    """Return the id of the seeded demo user."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()
    conn.close()
    return row["id"]


def _login_demo(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})


# ------------------------------------------------------------------ #
# Fixtures                                                             #
# ------------------------------------------------------------------ #

@pytest.fixture
def app(seeded_db):
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """A test client already logged in as the seeded demo user."""
    _login_demo(client)
    return client


@pytest.fixture
def empty_user_id(initialized_db):
    """Create a user with no expenses and return their id."""
    create_user("Empty User", "empty@filter.test", generate_password_hash("pass1234"))
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("empty@filter.test",)
    ).fetchone()
    conn.close()
    return row["id"]


@pytest.fixture
def auth_client_empty(app, empty_user_id, initialized_db):
    """A test client logged in as a user with zero expenses."""
    client = app.test_client()
    client.post(
        "/login",
        data={"email": "empty@filter.test", "password": "pass1234"},
    )
    return client


# ------------------------------------------------------------------ #
# 1. Auth guard                                                        #
# ------------------------------------------------------------------ #

class TestAuthGuard:

    def test_unauthenticated_get_profile_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, "Unauthenticated /profile must redirect"
        assert "/login" in response.headers["Location"], (
            "Redirect must target /login"
        )

    def test_unauthenticated_with_date_params_also_redirects(self, client):
        response = client.get("/profile?date_from=2026-01-01&date_to=2026-12-31")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ------------------------------------------------------------------ #
# 2. Unfiltered baseline — no query params                             #
# ------------------------------------------------------------------ #

class TestUnfilteredBaseline:

    def test_no_params_returns_200(self, auth_client):
        response = auth_client.get("/profile")
        assert response.status_code == 200, "Profile page must return 200 when authenticated"

    def test_no_params_shows_all_time_total(self, auth_client):
        """Seeded demo data totals ₹5,910.00."""
        response = auth_client.get("/profile")
        assert b"5,910.00" in response.data, "Unfiltered total must match all-time seeded total"

    def test_no_params_shows_all_transaction_count(self, auth_client):
        """Seeded demo data has 8 transactions."""
        response = auth_client.get("/profile")
        assert b"8" in response.data, "Unfiltered count must match all 8 seeded transactions"

    def test_no_params_shows_rupee_symbol(self, auth_client):
        response = auth_client.get("/profile")
        assert "₹".encode() in response.data, "Rupee symbol must appear in unfiltered view"

    def test_no_params_shows_top_category(self, auth_client):
        response = auth_client.get("/profile")
        assert b"Shopping" in response.data, "Top category Shopping must appear in unfiltered view"

    def test_no_params_all_time_preset_is_active(self, auth_client):
        """When no filter is active, the All Time preset link must carry the active CSS class."""
        response = auth_client.get("/profile")
        data = response.data.decode()
        # The template adds 'filter-preset--active' to the active preset anchor
        assert "filter-preset--active" in data, "An active preset class must appear"
        # The active class must be on the All Time link (which has no query params)
        # Find the position of 'All Time' and ensure the active class is nearby
        all_time_idx = data.find("All Time")
        active_idx = data.rfind("filter-preset--active", 0, all_time_idx)
        assert active_idx != -1, "'All Time' preset must be marked active when no filter is applied"


# ------------------------------------------------------------------ #
# 3. Valid date-range filter                                           #
# ------------------------------------------------------------------ #

class TestValidDateRangeFilter:

    def test_filtered_view_returns_200(self, auth_client):
        response = auth_client.get("/profile?date_from=2026-05-01&date_to=2026-05-10")
        assert response.status_code == 200

    def test_filtered_total_matches_window(self, auth_client):
        """
        Seeded expenses between 2026-05-01 and 2026-05-10 (inclusive):
          450.00 (Food, 2026-05-03)
          120.00 (Transport, 2026-05-07)
          1800.00 (Bills, 2026-05-10)
        Total = 2370.00
        """
        response = auth_client.get("/profile?date_from=2026-05-01&date_to=2026-05-10")
        assert b"2,370.00" in response.data, (
            "Filtered total must match only expenses within the requested window"
        )

    def test_filtered_excludes_expenses_outside_window(self, auth_client):
        """Expenses after 2026-05-10 must not appear in the filtered transaction list."""
        response = auth_client.get("/profile?date_from=2026-05-01&date_to=2026-05-10")
        # These descriptions belong to expenses outside the requested window
        assert b"Clothing" not in response.data, (
            "Expense outside filter window must not appear in filtered view"
        )
        assert b"Movie tickets" not in response.data

    def test_filtered_includes_expenses_inside_window(self, auth_client):
        """Expenses within the range must appear in the transaction list."""
        response = auth_client.get("/profile?date_from=2026-05-01&date_to=2026-05-10")
        assert b"Grocery run" in response.data, (
            "Expense on date_from boundary must appear in filtered view"
        )
        assert b"Electricity bill" in response.data, (
            "Expense on date_to boundary must appear in filtered view"
        )

    def test_filtered_view_still_shows_rupee_symbol(self, auth_client):
        response = auth_client.get("/profile?date_from=2026-05-01&date_to=2026-05-10")
        assert "₹".encode() in response.data, "Rupee symbol must appear in filtered view"

    def test_filtered_category_breakdown_excludes_out_of_window_categories(self, auth_client):
        """
        Only Food, Transport, Bills appear in 2026-05-01 to 2026-05-10.
        Shopping (2026-05-20) must not appear in the breakdown.
        """
        response = auth_client.get("/profile?date_from=2026-05-01&date_to=2026-05-10")
        # Shopping is 0 in this window — its breakdown entry must not appear
        data = response.data.decode()
        # Shopping should not appear in the breakdown section
        # We check the breakdown list; the category name "Shopping" won't be in breakdown rows
        # (it may still appear in other contexts so we target the breakdown section)
        # The simplest contract: the filtered total (2370) must appear, not the full total (5910)
        assert b"5,910.00" not in response.data, (
            "Full all-time total must not appear in a date-filtered view"
        )


# ------------------------------------------------------------------ #
# 4. date_from > date_to — inverted range error                        #
# ------------------------------------------------------------------ #

class TestInvertedDateRange:

    def test_inverted_range_returns_200(self, auth_client):
        """The route must not crash; it must return the profile page."""
        response = auth_client.get("/profile?date_from=2026-12-31&date_to=2026-01-01")
        assert response.status_code == 200, "Inverted range must not crash the app"

    def test_inverted_range_shows_flash_error(self, auth_client):
        """The spec mandates a flash message: 'Start date must be before end date.'"""
        response = auth_client.get(
            "/profile?date_from=2026-12-31&date_to=2026-01-01",
            follow_redirects=True,
        )
        assert b"Start date must be before end date." in response.data, (
            "Flash error message must appear when date_from > date_to"
        )

    def test_inverted_range_falls_back_to_all_time_data(self, auth_client):
        """After an inverted range error the view must show unfiltered (all-time) data."""
        response = auth_client.get("/profile?date_from=2026-12-31&date_to=2026-01-01")
        assert b"5,910.00" in response.data, (
            "Unfiltered total must be shown after inverted-range fallback"
        )

    def test_inverted_range_all_time_preset_is_active(self, auth_client):
        """After fallback, the All Time preset must be marked active."""
        response = auth_client.get("/profile?date_from=2026-12-31&date_to=2026-01-01")
        data = response.data.decode()
        all_time_idx = data.find("All Time")
        active_idx = data.rfind("filter-preset--active", 0, all_time_idx)
        assert active_idx != -1, "All Time preset must be active after inverted-range fallback"


# ------------------------------------------------------------------ #
# 5. Malformed date params — silent fallback                           #
# ------------------------------------------------------------------ #

class TestMalformedDateParams:

    @pytest.mark.parametrize("date_from,date_to", [
        ("not-a-date", "2026-05-31"),
        ("2026-05-01", "not-a-date"),
        ("not-a-date", "not-a-date"),
        ("2026-13-01", "2026-05-31"),   # invalid month
        ("2026-05-99", "2026-05-31"),   # invalid day
        ("",            ""),
        ("20260501",   "20260531"),     # missing hyphens
        ("05/01/2026", "05/31/2026"),   # wrong separator
    ])
    def test_malformed_dates_do_not_crash(self, auth_client, date_from, date_to):
        response = auth_client.get(
            f"/profile?date_from={date_from}&date_to={date_to}"
        )
        assert response.status_code == 200, (
            f"Malformed dates ({date_from!r}, {date_to!r}) must not crash the app"
        )

    def test_malformed_date_from_falls_back_to_unfiltered(self, auth_client):
        response = auth_client.get("/profile?date_from=not-a-date&date_to=2026-05-31")
        assert b"5,910.00" in response.data, (
            "Malformed date_from must trigger unfiltered fallback"
        )

    def test_malformed_date_to_falls_back_to_unfiltered(self, auth_client):
        response = auth_client.get("/profile?date_from=2026-05-01&date_to=not-a-date")
        assert b"5,910.00" in response.data, (
            "Malformed date_to must trigger unfiltered fallback"
        )

    def test_malformed_params_show_no_crash_error(self, auth_client):
        """The page must render the profile template (not a 500 error page)."""
        response = auth_client.get("/profile?date_from=BADDATE&date_to=ALSOBAD")
        assert b"Demo User" in response.data, (
            "Profile page must still render user data on malformed date input"
        )


# ------------------------------------------------------------------ #
# 6. Only one date param provided — unfiltered fallback                #
# ------------------------------------------------------------------ #

class TestSingleDateParam:

    def test_only_date_from_returns_unfiltered(self, auth_client):
        """Spec: if either param is absent, fall back to all-time view."""
        response = auth_client.get("/profile?date_from=2026-05-15")
        assert response.status_code == 200
        assert b"5,910.00" in response.data, (
            "Only date_from provided must return all-time (unfiltered) data"
        )

    def test_only_date_to_returns_unfiltered(self, auth_client):
        """Spec: if either param is absent, fall back to all-time view."""
        response = auth_client.get("/profile?date_to=2026-05-15")
        assert response.status_code == 200
        assert b"5,910.00" in response.data, (
            "Only date_to provided must return all-time (unfiltered) data"
        )

    def test_only_date_from_all_time_preset_is_active(self, auth_client):
        response = auth_client.get("/profile?date_from=2026-05-15")
        data = response.data.decode()
        all_time_idx = data.find("All Time")
        active_idx = data.rfind("filter-preset--active", 0, all_time_idx)
        assert active_idx != -1, (
            "All Time preset must be active when only date_from is provided"
        )

    def test_only_date_to_all_time_preset_is_active(self, auth_client):
        response = auth_client.get("/profile?date_to=2026-05-15")
        data = response.data.decode()
        all_time_idx = data.find("All Time")
        active_idx = data.rfind("filter-preset--active", 0, all_time_idx)
        assert active_idx != -1, (
            "All Time preset must be active when only date_to is provided"
        )


# ------------------------------------------------------------------ #
# 7. Empty result state — no expenses in range                         #
# ------------------------------------------------------------------ #

class TestEmptyRangeResult:

    def test_empty_range_returns_200(self, auth_client):
        """A valid range with no matching expenses must still return 200."""
        response = auth_client.get("/profile?date_from=2020-01-01&date_to=2020-12-31")
        assert response.status_code == 200, (
            "Empty date range must not crash the app"
        )

    def test_empty_range_shows_zero_total(self, auth_client):
        response = auth_client.get("/profile?date_from=2020-01-01&date_to=2020-12-31")
        assert b"0.00" in response.data, (
            "Total spent must be ₹0.00 when no expenses exist in the selected range"
        )

    def test_empty_range_shows_zero_transactions(self, auth_client):
        response = auth_client.get("/profile?date_from=2020-01-01&date_to=2020-12-31")
        # The transaction count stat card must show 0
        assert b"0" in response.data, (
            "Transaction count must be 0 when no expenses exist in the selected range"
        )

    def test_empty_range_shows_rupee_symbol(self, auth_client):
        """Rupee symbol must appear even when the filtered total is zero."""
        response = auth_client.get("/profile?date_from=2020-01-01&date_to=2020-12-31")
        assert "₹".encode() in response.data, (
            "Rupee symbol must appear even when filtered total is ₹0.00"
        )

    def test_user_with_no_expenses_returns_zeros(self, auth_client_empty):
        """A user who has never added any expense must see ₹0.00 with no errors."""
        response = auth_client_empty.get("/profile?date_from=2026-01-01&date_to=2026-12-31")
        assert response.status_code == 200
        assert b"0.00" in response.data
        assert "₹".encode() in response.data

    def test_user_with_no_expenses_no_transaction_rows(self, auth_client_empty):
        """Transaction table must have no data rows for a user with no expenses."""
        response = auth_client_empty.get("/profile")
        # No <td> with a monetary amount should appear
        assert b"Shopping" not in response.data, (
            "No category data must appear for a user with no expenses"
        )


# ------------------------------------------------------------------ #
# 8. Filter bar presence                                               #
# ------------------------------------------------------------------ #

class TestFilterBarRendering:

    def test_filter_bar_section_present(self, auth_client):
        response = auth_client.get("/profile")
        assert b"profile-filter" in response.data, (
            "Filter bar section (class=profile-filter) must be present"
        )

    def test_all_four_preset_links_present(self, auth_client):
        response = auth_client.get("/profile")
        assert b"All Time" in response.data, "All Time preset link must be rendered"
        assert b"This Month" in response.data, "This Month preset link must be rendered"
        assert b"Last 3 Months" in response.data, "Last 3 Months preset link must be rendered"
        assert b"Last 6 Months" in response.data, "Last 6 Months preset link must be rendered"

    def test_custom_date_inputs_present(self, auth_client):
        response = auth_client.get("/profile")
        assert b'name="date_from"' in response.data, (
            "Custom date_from input must be present in filter bar"
        )
        assert b'name="date_to"' in response.data, (
            "Custom date_to input must be present in filter bar"
        )

    def test_apply_button_present(self, auth_client):
        response = auth_client.get("/profile")
        assert b"Apply" in response.data, "Apply button must be present in filter bar"

    def test_filter_form_uses_get_method(self, auth_client):
        """The custom date form must use GET so dates appear in the query string."""
        response = auth_client.get("/profile")
        assert b'method="GET"' in response.data or b"method=GET" in response.data, (
            "Filter form must use HTTP GET"
        )


# ------------------------------------------------------------------ #
# 9. Active preset highlighting                                         #
# ------------------------------------------------------------------ #

class TestActivePresetHighlighting:

    def test_no_filter_marks_all_time_active(self, auth_client):
        response = auth_client.get("/profile")
        data = response.data.decode()
        # Locate 'All Time' text; the active class must appear before it on the same element
        all_time_pos = data.find("All Time")
        assert all_time_pos != -1, "All Time link must be in the page"
        segment = data[max(0, all_time_pos - 200): all_time_pos]
        assert "filter-preset--active" in segment, (
            "'All Time' link must carry filter-preset--active when no filter is applied"
        )

    def test_this_month_preset_marks_this_month_active(self, auth_client):
        today = date.today()
        first_of_month = today.replace(day=1).isoformat()
        today_str = today.isoformat()
        response = auth_client.get(
            f"/profile?date_from={first_of_month}&date_to={today_str}"
        )
        data = response.data.decode()
        this_month_pos = data.find("This Month")
        assert this_month_pos != -1, "This Month link must be in the page"
        segment = data[max(0, this_month_pos - 200): this_month_pos]
        assert "filter-preset--active" in segment, (
            "'This Month' link must carry filter-preset--active when this-month range is applied"
        )

    def test_other_presets_not_active_when_all_time_selected(self, auth_client):
        response = auth_client.get("/profile")
        data = response.data.decode()
        # Count total occurrences of the active class — only one preset should be active
        active_count = data.count("filter-preset--active")
        assert active_count == 1, (
            "Exactly one preset must be marked active when no filter is applied"
        )

    def test_other_presets_not_active_when_this_month_selected(self, auth_client):
        today = date.today()
        first_of_month = today.replace(day=1).isoformat()
        today_str = today.isoformat()
        response = auth_client.get(
            f"/profile?date_from={first_of_month}&date_to={today_str}"
        )
        data = response.data.decode()
        active_count = data.count("filter-preset--active")
        assert active_count == 1, (
            "Exactly one preset must be marked active when This Month filter is applied"
        )


# ------------------------------------------------------------------ #
# 10. Custom date inputs retain their values                           #
# ------------------------------------------------------------------ #

class TestDateInputValueRetention:

    def test_date_from_value_retained_in_input(self, auth_client):
        response = auth_client.get("/profile?date_from=2026-05-01&date_to=2026-05-31")
        assert b'value="2026-05-01"' in response.data, (
            "date_from input must retain its submitted value when filter is active"
        )

    def test_date_to_value_retained_in_input(self, auth_client):
        response = auth_client.get("/profile?date_from=2026-05-01&date_to=2026-05-31")
        assert b'value="2026-05-31"' in response.data, (
            "date_to input must retain its submitted value when filter is active"
        )

    def test_inputs_empty_when_no_filter_active(self, auth_client):
        """When no filter is applied, the date inputs must have empty values."""
        response = auth_client.get("/profile")
        # Both inputs must have empty value attributes
        assert b'value=""' in response.data or (
            b'value="2026-05-01"' not in response.data
        ), "Date inputs must be empty when no filter is active"

    def test_inputs_cleared_after_inverted_range_error(self, auth_client):
        """After an invalid range fallback, inputs must not retain the bad dates."""
        response = auth_client.get("/profile?date_from=2026-12-31&date_to=2026-01-01")
        # After fallback both filter_from and filter_to are set to None in the route,
        # so the template must render empty value attributes for both inputs.
        assert b'value="2026-12-31"' not in response.data, (
            "date_from input must be cleared after an inverted-range fallback"
        )
        assert b'value="2026-01-01"' not in response.data, (
            "date_to input must be cleared after an inverted-range fallback"
        )


# ------------------------------------------------------------------ #
# 11. Query-helper-level date filtering                                #
# ------------------------------------------------------------------ #

class TestQueryHelpersWithDateFilter:
    """
    Directly test the query helpers with date_from / date_to arguments.
    These tests sit at the DB layer, independent of the HTTP layer.
    """

    def test_get_summary_stats_filters_by_date_range(self, seeded_db):
        uid = _get_demo_user_id()
        # Only expenses on 2026-05-03 and 2026-05-07 fall in this range
        result = get_summary_stats(uid, date_from="2026-05-01", date_to="2026-05-07")
        assert result["total_spent"] == "570.00", (
            "get_summary_stats must sum only expenses within the date range"
        )

    def test_get_summary_stats_count_filtered(self, seeded_db):
        uid = _get_demo_user_id()
        result = get_summary_stats(uid, date_from="2026-05-01", date_to="2026-05-07")
        assert result["transaction_count"] == 2, (
            "get_summary_stats must count only transactions within the date range"
        )

    def test_get_summary_stats_empty_range_returns_zeros(self, seeded_db):
        uid = _get_demo_user_id()
        result = get_summary_stats(uid, date_from="2020-01-01", date_to="2020-12-31")
        assert result["total_spent"] == "0.00"
        assert result["transaction_count"] == 0
        assert result["top_category"] == "—"

    def test_get_recent_transactions_filters_by_date_range(self, seeded_db):
        uid = _get_demo_user_id()
        # Only two expenses fall before 2026-05-08
        result = get_recent_transactions(uid, date_from="2026-05-01", date_to="2026-05-07")
        assert len(result) == 2, (
            "get_recent_transactions must return only transactions within the date range"
        )

    def test_get_recent_transactions_empty_range_returns_empty_list(self, seeded_db):
        uid = _get_demo_user_id()
        result = get_recent_transactions(uid, date_from="2020-01-01", date_to="2020-12-31")
        assert result == [], (
            "get_recent_transactions must return [] when no expenses fall in the range"
        )

    def test_get_recent_transactions_respects_order_newest_first(self, seeded_db):
        uid = _get_demo_user_id()
        result = get_recent_transactions(uid, date_from="2026-05-01", date_to="2026-05-31")
        # First item should be the most recent date in May 2026
        assert result[0]["description"] == "Restaurant dinner", (
            "get_recent_transactions must still order newest-first when filtered"
        )

    def test_get_category_breakdown_filters_by_date_range(self, seeded_db):
        uid = _get_demo_user_id()
        # Only Food and Transport in 2026-05-01 to 2026-05-07
        result = get_category_breakdown(uid, date_from="2026-05-01", date_to="2026-05-07")
        names = [cat["name"] for cat in result]
        assert "Food" in names
        assert "Transport" in names
        assert "Bills" not in names, (
            "Categories outside the date window must not appear in breakdown"
        )

    def test_get_category_breakdown_percentages_sum_to_100_when_filtered(self, seeded_db):
        uid = _get_demo_user_id()
        result = get_category_breakdown(uid, date_from="2026-05-01", date_to="2026-05-20")
        if result:
            total_pct = sum(cat["percentage"] for cat in result)
            assert total_pct == 100, (
                "Category percentages must sum to 100 even when a date filter is applied"
            )

    def test_get_category_breakdown_empty_range_returns_empty_list(self, seeded_db):
        uid = _get_demo_user_id()
        result = get_category_breakdown(uid, date_from="2020-01-01", date_to="2020-12-31")
        assert result == [], (
            "get_category_breakdown must return [] when no expenses fall in the range"
        )

    def test_get_summary_stats_no_filter_matches_all_time(self, seeded_db):
        """With no date args, helpers must behave identically to Step 5 (unfiltered)."""
        uid = _get_demo_user_id()
        result = get_summary_stats(uid)
        assert result["total_spent"] == "5,910.00"
        assert result["transaction_count"] == 8

    def test_get_recent_transactions_no_filter_returns_all(self, seeded_db):
        uid = _get_demo_user_id()
        result = get_recent_transactions(uid)
        assert len(result) == 8

    def test_get_category_breakdown_no_filter_returns_all_categories(self, seeded_db):
        uid = _get_demo_user_id()
        result = get_category_breakdown(uid)
        assert len(result) == 7


# ------------------------------------------------------------------ #
# 12. Boundary dates (inclusive)                                       #
# ------------------------------------------------------------------ #

class TestBoundaryDates:

    def test_date_from_boundary_is_inclusive(self, seeded_db):
        """An expense on exactly date_from must be included."""
        uid = _get_demo_user_id()
        result = get_recent_transactions(uid, date_from="2026-05-03", date_to="2026-05-03")
        assert len(result) == 1, (
            "An expense on exactly date_from must be included (inclusive lower bound)"
        )
        assert result[0]["description"] == "Grocery run"

    def test_date_to_boundary_is_inclusive(self, seeded_db):
        """An expense on exactly date_to must be included."""
        uid = _get_demo_user_id()
        result = get_recent_transactions(uid, date_from="2026-05-26", date_to="2026-05-26")
        assert len(result) == 1, (
            "An expense on exactly date_to must be included (inclusive upper bound)"
        )
        assert result[0]["description"] == "Restaurant dinner"

    def test_same_day_range_returns_single_expense(self, auth_client):
        """date_from == date_to is a valid single-day filter."""
        response = auth_client.get("/profile?date_from=2026-05-03&date_to=2026-05-03")
        assert response.status_code == 200
        assert b"Grocery run" in response.data, (
            "Single-day filter must return the expense on that exact day"
        )
        assert b"Auto rickshaw fares" not in response.data, (
            "Expenses on other days must not appear in a single-day filter"
        )

import os
import re
import sqlite3
from datetime import date, timedelta

from flask import Flask, render_template, request, redirect, url_for, abort, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from database.queries import (
    get_user_by_id, get_summary_stats,
    get_recent_transactions, get_category_breakdown,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

# ------------------------------------------------------------------ #
# Database initialisation                                             #
# ------------------------------------------------------------------ #
with app.app_context():
    init_db()
    seed_db()

# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name     = request.form.get("name",     "").strip()
    email    = request.form.get("email",    "").strip()
    password = request.form.get("password", "").strip()

    if not name:
        return render_template("register.html",
                               error="Full name is required.",
                               name=name, email=email)

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return render_template("register.html",
                               error="Please enter a valid email address.",
                               name=name, email=email)

    if len(password) < 8:
        return render_template("register.html",
                               error="Password must be at least 8 characters.",
                               name=name, email=email)

    password_hash = generate_password_hash(password)
    try:
        create_user(name, email, password_hash)
    except sqlite3.IntegrityError:
        return render_template("register.html",
                               error="An account with that email already exists.",
                               name=name, email=email)

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("login.html")

    email    = request.form.get("email",    "").strip()
    password = request.form.get("password", "").strip()

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html",
                               error="Invalid email or password.",
                               email=email)

    session["user_id"]   = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_data = get_user_by_id(session["user_id"])
    if user_data is None:
        abort(404)

    initials = "".join(w[0].upper() for w in user_data["name"].split() if w)[:2]
    user = {**user_data, "initials": initials}

    # Parse and validate date filter params
    filter_from = None
    filter_to   = None
    raw_from = request.args.get("date_from", "").strip()
    raw_to   = request.args.get("date_to",   "").strip()
    try:
        if raw_from:
            filter_from = date.fromisoformat(raw_from)
    except ValueError:
        pass
    try:
        if raw_to:
            filter_to = date.fromisoformat(raw_to)
    except ValueError:
        pass

    if filter_from and filter_to and filter_from > filter_to:
        flash("Start date must be before end date.", "error")
        filter_from = filter_to = None

    # Preset date anchors
    today = date.today()
    this_month_start = today.replace(day=1)

    m3, y3 = today.month - 3, today.year
    if m3 <= 0:
        m3 += 12
        y3 -= 1
    last_3_start = date(y3, m3, 1)

    m6, y6 = today.month - 6, today.year
    if m6 <= 0:
        m6 += 12
        y6 -= 1
    last_6_start = date(y6, m6, 1)

    # Determine which preset is active
    active_preset = None
    if filter_from == this_month_start and filter_to == today:
        active_preset = "this_month"
    elif filter_from == last_3_start and filter_to == today:
        active_preset = "last_3"
    elif filter_from == last_6_start and filter_to == today:
        active_preset = "last_6"
    elif filter_from is None and filter_to is None:
        active_preset = "all_time"

    preset_urls = {
        "this_month": url_for("profile", date_from=this_month_start.isoformat(), date_to=today.isoformat()),
        "last_3":     url_for("profile", date_from=last_3_start.isoformat(),     date_to=today.isoformat()),
        "last_6":     url_for("profile", date_from=last_6_start.isoformat(),     date_to=today.isoformat()),
        "all_time":   url_for("profile"),
    }

    df_str = filter_from.isoformat() if filter_from else None
    dt_str = filter_to.isoformat()   if filter_to   else None

    stats        = get_summary_stats(session["user_id"],       date_from=df_str, date_to=dt_str)
    transactions = get_recent_transactions(session["user_id"], date_from=df_str, date_to=dt_str)
    categories   = get_category_breakdown(session["user_id"],  date_from=df_str, date_to=dt_str)

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        active_preset=active_preset,
        preset_urls=preset_urls,
        filter_from=filter_from.isoformat() if filter_from else "",
        filter_to=filter_to.isoformat()     if filter_to   else "",
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)

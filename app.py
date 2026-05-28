import os
import re
import sqlite3

from flask import Flask, render_template, request, redirect, url_for, abort, session
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import get_db, init_db, seed_db, create_user, get_user_by_email

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

    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "January 2026",
        "initials": "DU",
    }

    stats = {
        "total_spent": "5,910.00",
        "transaction_count": 8,
        "top_category": "Shopping",
    }

    transactions = [
        {"date": "26 May 2026", "description": "Restaurant dinner",  "category": "Food",          "amount": "310.00"},
        {"date": "23 May 2026", "description": "Miscellaneous",       "category": "Other",         "amount": "80.00"},
        {"date": "20 May 2026", "description": "Clothing",            "category": "Shopping",      "amount": "2,200.00"},
        {"date": "16 May 2026", "description": "Movie tickets",       "category": "Entertainment", "amount": "350.00"},
        {"date": "12 May 2026", "description": "Pharmacy",            "category": "Health",        "amount": "600.00"},
        {"date": "10 May 2026", "description": "Electricity bill",    "category": "Bills",         "amount": "1,800.00"},
        {"date": "07 May 2026", "description": "Auto rickshaw fares", "category": "Transport",     "amount": "120.00"},
        {"date": "03 May 2026", "description": "Grocery run",         "category": "Food",          "amount": "450.00"},
    ]

    categories = [
        {"name": "Shopping",      "amount": "2,200.00", "percentage": 37},
        {"name": "Bills",         "amount": "1,800.00", "percentage": 30},
        {"name": "Food",          "amount": "760.00",   "percentage": 13},
        {"name": "Health",        "amount": "600.00",   "percentage": 10},
        {"name": "Entertainment", "amount": "350.00",   "percentage": 6},
        {"name": "Transport",     "amount": "120.00",   "percentage": 2},
        {"name": "Other",         "amount": "80.00",    "percentage": 1},
    ]

    return render_template("profile.html", user=user, stats=stats,
                           transactions=transactions, categories=categories)


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

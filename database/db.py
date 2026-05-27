# database/db.py
import os
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "spendly.db"
)


def get_db():
    """Return a SQLite connection with Row factory and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables. Safe to call multiple times (IF NOT EXISTS)."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT,
            created_at  TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


def seed_db():
    """Insert sample data once. No-op if users table already has rows."""
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        conn.close()
        return

    pw = generate_password_hash("demo123")
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", pw)
    )
    conn.commit()

    user_id = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()["id"]

    expenses = [
        (user_id, 450.00,  "Food",          "2026-05-03", "Grocery run"),
        (user_id, 120.00,  "Transport",     "2026-05-07", "Auto rickshaw fares"),
        (user_id, 1800.00, "Bills",         "2026-05-10", "Electricity bill"),
        (user_id, 600.00,  "Health",        "2026-05-12", "Pharmacy"),
        (user_id, 350.00,  "Entertainment", "2026-05-16", "Movie tickets"),
        (user_id, 2200.00, "Shopping",      "2026-05-20", "Clothing"),
        (user_id, 80.00,   "Other",         "2026-05-23", "Miscellaneous"),
        (user_id, 310.00,  "Food",          "2026-05-26", "Restaurant dinner"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses
    )
    conn.commit()
    conn.close()

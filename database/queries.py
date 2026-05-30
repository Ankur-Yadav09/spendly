from datetime import datetime

from database.db import get_db


def get_user_by_id(user_id):
    """Return dict with name, email, member_since for the given user id, or None."""
    db = get_db()
    try:
        cursor = db.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        try:
            parsed = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
            member_since = parsed.strftime("%B %Y")
        except (ValueError, TypeError):
            member_since = row["created_at"] or ""
        return {
            "name": row["name"],
            "email": row["email"],
            "member_since": member_since,
        }
    finally:
        db.close()


def get_summary_stats(user_id):
    """Return dict with total_spent, transaction_count, top_category."""
    db = get_db()
    try:
        cursor = db.execute(
            "SELECT SUM(amount), COUNT(*) FROM expenses WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        total_raw = row[0] if row[0] is not None else 0.0
        count = row[1] if row[1] is not None else 0

        top_cursor = db.execute(
            "SELECT category FROM expenses WHERE user_id = ?"
            " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,),
        )
        top_row = top_cursor.fetchone()
        top_category = top_row["category"] if top_row is not None else "—"

        return {
            "total_spent": "{:,.2f}".format(total_raw),
            "transaction_count": count,
            "top_category": top_category,
        }
    except Exception:
        return {
            "total_spent": "0.00",
            "transaction_count": 0,
            "top_category": "—",
        }
    finally:
        db.close()


def get_recent_transactions(user_id, limit=10):
    """Return list of dicts ordered newest-first: date, description, category, amount."""
    db = get_db()
    try:
        cursor = db.execute(
            "SELECT date, description, category, amount FROM expenses"
            " WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit),
        )
        rows = cursor.fetchall()
        results = []
        for row in rows:
            raw_date = row["date"]
            try:
                from datetime import datetime
                parsed = datetime.strptime(raw_date, "%Y-%m-%d")
                formatted_date = "{} {} {}".format(parsed.day, parsed.strftime("%B"), parsed.year)
            except (ValueError, TypeError):
                formatted_date = raw_date or ""
            results.append({
                "date": formatted_date,
                "description": row["description"] if row["description"] is not None else "",
                "category": row["category"],
                "amount": "{:,.2f}".format(row["amount"]),
            })
        return results
    except Exception:
        return []
    finally:
        db.close()


def get_category_breakdown(user_id):
    """Return list of dicts ordered by amount desc: name, amount, percentage."""
    db = get_db()
    try:
        cursor = db.execute(
            "SELECT category, SUM(amount) AS total FROM expenses"
            " WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
        )
        rows = cursor.fetchall()
        if not rows:
            return []

        grand_total = sum(row["total"] for row in rows)

        raw_pcts = [(row["total"] / grand_total * 100) if grand_total else 0.0 for row in rows]
        rounded = [round(p) for p in raw_pcts]

        remainder = 100 - sum(rounded)
        if remainder != 0 and rounded:
            rounded[0] += remainder

        results = []
        for i, row in enumerate(rows):
            results.append({
                "name": row["category"],
                "amount": "{:,.2f}".format(row["total"]),
                "percentage": rounded[i],
            })
        return results
    except Exception:
        return []
    finally:
        db.close()

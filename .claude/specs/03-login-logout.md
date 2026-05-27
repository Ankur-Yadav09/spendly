# Spec: Login and Logout

## Overview
This step makes authentication functional in Spendly. It wires up a `POST /login` route that verifies submitted credentials against the hashed password in the `users` table and stores the authenticated user's ID in a Flask session. It also implements the `GET /logout` stub, which clears the session and redirects to the landing page. The navbar in `base.html` is made session-aware so that logged-in users see a logout link instead of the Sign in / Get started buttons.

## Depends on
- **Step 1 — Database Setup**: requires the `users` table and `get_db()` helper.
- **Step 2 — Registration**: requires `get_user_by_email()` already in `database/db.py`; the login route reuses this function directly.

## Routes
- `POST /login` — accepts email/password form fields, verifies password hash, stores `user_id` in session, redirects to `/profile` on success — **public**
- `GET /logout` — clears the session, redirects to `/` — **public** (no login required to call it)

The existing `GET /login` route only needs to be extended to accept both methods; no separate function is needed.

## Database changes
No new tables or columns. No new DB helper functions — `get_user_by_email(email)` already exists in `database/db.py` from Step 2 and is sufficient for login lookup.

## Templates
- **Modify:** `templates/login.html`
  - Add sticky email field: `value="{{ email or '' }}"` on the email input so the address is preserved on failed login.
  - Password input stays empty on re-render (never echo passwords back).
  - The form already has `method="POST"` and `action="/login"` — no changes needed there.

- **Modify:** `templates/base.html`
  - Make the navbar session-aware using `{% if session.user_id %}` (Flask exposes `session` in templates automatically):
    - **Logged in**: hide "Sign in" and "Get started"; show the user's name (from `session.user_name`) and a "Sign out" link pointing to `url_for('logout')`.
    - **Not logged in**: keep the current "Sign in" and "Get started" links.

## Files to change
- `app.py` — add `session` to Flask imports; add `check_password_hash` to werkzeug imports; add `os` stdlib import; set `app.secret_key`; upgrade `/login` to handle POST; implement `/logout`
- `database/db.py` — no changes needed
- `templates/login.html` — add sticky `value` on email input
- `templates/base.html` — conditional navbar based on `session.user_id`

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is already available via Flask's Werkzeug dependency.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Passwords verified with `werkzeug.security.check_password_hash` — never compare plaintext
- Use CSS variables — never hardcode hex values in any new styles
- All templates extend `base.html`
- DB logic belongs in `database/db.py` — the route may only call `get_user_by_email()`; no inline queries
- `app.secret_key` must be set before any session use; read from environment with a fallback: `app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")`
- On successful login store **only** `session['user_id']` (integer) and `session['user_name']` (string) — never store the password hash in the session
- On failed login (wrong email or wrong password) show a **single generic error** — "Invalid email or password." — never reveal which field was wrong (prevents user enumeration)
- Re-render `login.html` with the submitted `email` on any failure (sticky field); never pass `password` back
- On logout: `session.clear()` then `redirect(url_for('landing'))`
- Use `abort(400)` only for truly malformed requests; credential failures re-render the form

## Definition of done
- [ ] Submitting valid credentials logs the user in and redirects to `/profile`
- [ ] After login, the navbar shows the user's name and a "Sign out" link instead of "Sign in" / "Get started"
- [ ] Clicking "Sign out" clears the session and returns to the landing page; the navbar reverts to the logged-out state
- [ ] Submitting an email that does not exist re-renders the form with "Invalid email or password." and does not expose which field was wrong
- [ ] Submitting a correct email with the wrong password re-renders the form with the same generic error
- [ ] The email field is pre-populated with the submitted value on a failed login attempt
- [ ] The password field is empty on re-render (not echoed back)
- [ ] Direct navigation to `/logout` without being logged in does not crash — it simply redirects to the landing page
- [ ] `pytest` passes with no errors (all existing tests remain green)

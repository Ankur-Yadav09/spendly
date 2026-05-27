# Spec: Registration

## Overview
This step wires up the user registration flow so that new visitors can create a Spendly account. It adds a `POST /register` route that validates the submitted form, hashes the password, and inserts the user into the `users` table. The existing `GET /register` route already renders the form; this step makes the form functional. On success the user is redirected to the login page. On failure the form is re-rendered with a meaningful inline error message.

## Depends on
- **Step 1 — Database Setup**: requires the `users` table, `get_db()` helper, and FK enforcement already in place.

## Routes
- `POST /register` — accepts name/email/password form fields, validates input, hashes password, inserts user, redirects to `/login` on success — **public**

The existing `GET /register` route is already implemented; it only needs minor template updates to display errors.

## Database changes
No new tables or columns. The `users` table already has the correct schema (`id`, `name`, `email`, `password_hash`, `created_at`).

A new helper function must be added to `database/db.py`:
- `create_user(name, email, password_hash)` — inserts a row into `users`; raises an `IntegrityError` when the email is already taken (relies on the UNIQUE constraint).
- `get_user_by_email(email)` — returns the user row for a given email, or `None`; used by the route to check for duplicates before attempting the insert (and reused in later login steps).

## Templates
- **Modify:** `templates/register.html`
  - Add `method="POST"` and `action="{{ url_for('register') }}"` to the `<form>` tag (or confirm these are already present).
  - Display a server-side error message when `error` is passed in the template context (e.g. `{% if error %}<p class="form-error">{{ error }}</p>{% endif %}`).
  - Preserve user-entered `name` and `email` values on validation failure so the user does not have to retype them (pass them back via template context).

## Files to change
- `app.py` — add `POST /register` logic to the existing `register` route function (convert it from GET-only to accept both methods)
- `database/db.py` — add `create_user()` and `get_user_by_email()` helper functions
- `templates/register.html` — add POST action, error display, and sticky field values

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.generate_password_hash` is already available via Flask's dependency on Werkzeug.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` — never store plaintext
- Use CSS variables — never hardcode hex values in any new styles
- All templates extend `base.html`
- DB logic belongs in `database/db.py` — the route function may only call helper functions, never build queries inline
- Duplicate email must be caught gracefully — catch `sqlite3.IntegrityError` in `create_user()` or check via `get_user_by_email()` before inserting; return a user-friendly message, never expose raw DB errors
- After successful registration redirect to `url_for('login')` — do not render a template directly
- Validate on the server side (not just the browser): name non-empty, valid email format, password at least 8 characters; return the form with an `error` string on any failure
- Use `abort(400)` only for truly malformed requests; validation failures should re-render the form with an error message

## Definition of done
- [ ] Submitting the registration form with valid data creates a new row in the `users` table with a non-plaintext `password_hash`
- [ ] After successful registration the browser is redirected to `/login`
- [ ] Submitting with a duplicate email re-renders the form with an error message and does not insert a duplicate row
- [ ] Submitting with a missing name, invalid email format, or password shorter than 8 characters re-renders the form with a descriptive error message
- [ ] The name and email fields are pre-populated with the user's input when the form is re-rendered after a validation failure
- [ ] `pytest` passes with no errors (existing tests remain green)
- [ ] The `users` table contains exactly one new row per successful registration (confirmed via a quick DB check or test)

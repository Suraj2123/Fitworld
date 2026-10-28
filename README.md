# Fitworld

A fitness app that helps people start exercising, build a routine, and track their progress.

Team: Soham Mohapatra, Francis Sunga, David Vayntrub, Suraj Yarrapathruni.

## David's contribution: onboarding and database schema

Branch: `codex/david-onboarding-schema`

This contribution includes a responsive four-step onboarding flow (account → baseline → preferences → review), sign-in/sign-out, resumable setup, and a persistent SQLite database. Account creation collects name, email, and password; the baseline collects age, body weight, experience, and current exercise habits. Preferences collect a fitness goal, workout location, days per week, and session length. The final screen confirms the real saved profile and provides an entry point for the team's future Home page.

The frontend uses plain HTML, CSS, and JavaScript. The backend uses Python/Flask and parameterized SQLite queries. This follows the proposal's web/Python/SQL direction without requiring a frontend build or external database service. The initial schema also supports future workout, routine, nutrition, photo, goal, and progress features; their interfaces and services are not implemented here.

## Run locally

Requires Python 3.10 or newer. From this repository directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app fitworld init-db
python -m flask --app fitworld run --port 5001
```

Open [Fitworld locally](http://127.0.0.1:5001). Stop the server with Ctrl+C. `init-db` applies pending migrations without clearing existing data. Sign in again to resume saved steps or revisit a completed profile.

`instance/fitworld.sqlite3` holds local data and `instance/session-secret` holds the generated local signing key. Neither is committed. No credentials or database accounts are preloaded. Nothing needs to be put in `.env` for local development; the app reads environment variables directly.

## Verify

With the virtual environment activated:

```bash
python -m unittest discover -s tests -v
```

Tests cover registration, password hashing, authentication and CSRF, invalid input, unit conversion, saved drafts, completion, account isolation, migrations, foreign keys, routine ownership, and cascading deletion. Tests use temporary databases and leave local user data alone.

For a manual check, create an account, submit the baseline in kg or lb, choose preferences, review, and finish. Reload and verify the saved profile. Edit your baseline, sign out, and sign back in. Try a duplicate email, empty required fields, and the flow on a small phone viewport.

## Team integration

- [Database diagram, table contract, API, and example queries](docs/database.md)
- [Initial SQL migration](fitworld/migrations/001_initial.sql)
- `fitworld/api.py`: authenticated account/onboarding endpoints
- `fitworld/templates/index.html`, `fitworld/static/`: onboarding interface
- `fitworld/db.py`: shared connection and migration helpers

Future backend features should use `get_db()` inside the Flask application context, derive ownership from the authenticated session, and validate private child records through their owner. Add new numbered migrations once this schema is shared. The database documentation identifies supported entities and the remaining integration work.

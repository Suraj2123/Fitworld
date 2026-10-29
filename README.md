# Fitworld

A fitness app for starting a routine, recording movement and food, and seeing progress over time.

Team: Soham Mohapatra, Francis Sunga, David Vayntrub, Suraj Yarrapathruni.

## Run locally

Requires Python 3.10 or newer and a modern browser. From this repository directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app fitworld init-db
python -m flask --app fitworld run --port 5001
```

Open [Fitworld locally](http://127.0.0.1:5001). Create an account, complete onboarding, and continue to Home. Existing accounts can sign in. Stop the server with Ctrl+C.

`init-db` applies pending numbered migrations without clearing existing accounts or history, then inserts missing starter catalog entries. It can be run again safely. The starter catalog contains example exercises and four-week routines; user activity starts empty. Existing catalog descriptions and prescriptions are preserved when seeding is repeated.

The backend is Python/Flask with parameterized SQLite queries. The frontend is HTML, CSS, and native JavaScript modules; it requires no Node installation, frontend build, database service, or external API credentials. Node is only an optional development tool for JavaScript syntax checks.

## Pages

| Page | Behavior |
| --- | --- |
| Onboarding `/` | Account creation, age/weight, current exercise habits, experience, goals, preferences, saved-step resume, and review. Completed accounts are directed to Home. |
| Home `/home` | Daily completed/partial workouts, muscle groups, recorded calorie estimates, persistent food logging with servings and optional nutrients, workout suggestions, upcoming sessions, and recent activity. Choose another date to record past activity. |
| Suggested Workouts `/workouts` | Search workouts, exercises, and routines; inspect workout descriptions, intensity, duration, and prescriptions; explore high/low intensity and recovery; choose or replace a routine and view 7/28-day schedules. |
| Personal Progress `/progress` | Monthly completed/partial totals, weekly average, exercise improvements, keyboard-accessible daily calendar, workout and nutrition details, private weight check-ins and history, and saved milestones. Month/day URLs can be bookmarked. |
| Settings `/settings` | View account details, update personal stats and workout preferences, and sign out. |

Workout logging supports optional actual exercise reps, loads, and timed sets. Unfilled sets and calorie estimates remain unknown rather than becoming fabricated performance data. Food calories and nutrients are entered per serving and multiplied by the servings eaten. Unknown nutrients remain distinguishable from a known zero.

Automated food-photo analysis and progress-photo upload are future extensions. Their schema support remains available; this branch records nutrition manually and does not send personal data to external services.

## Branch integration

`codex/integrate-pages-progress` starts from `main` after onboarding PR #1 was merged. It merges `origin/feature/home-page` through `a34351a` before the application integration. That Home contribution includes food logging, free-text workout logging, separate calorie/time totals, and entry removal with accessible labels and focus restoration. Those flows are moved into the Flask app and extended with authenticated SQLite persistence, serving-based nutrition, catalog workouts, routines, and Progress. The latest Home functionality is retained alongside the additions.

At integration time, `origin/suggested-workouts` points to the initial commit (`95a4000`) and contains only the README. The Suggested Workouts implementation is therefore built from the proposal, using the existing catalog/routine tables. Other contributors' remote branches are unchanged.

## Verify

With the virtual environment activated:

```bash
python -m unittest discover -s tests -v
```

Tests use temporary databases. They cover onboarding, authentication/CSRF, account isolation, migration compatibility, serving calculations, unknown nutrients, workout sets, calendar dates and leap years, monthly averages, performance comparisons, routine replacement, scheduled completion, deletion, and weight history. They leave local user data alone.

For a manual check, create an account; add a food with two servings; log a completed or partial workout; select a routine; then open Progress and choose the logged day. Reload, change months, record a weight, and sign back in. Check both an empty account and a populated month, and use the calendar with Tab and arrow keys.

## Team development

- [Module structure, endpoint contract, and extension guide](docs/integration.md)
- [Database diagram, ownership rules, and queries](docs/database.md)
- [Initial schema](fitworld/migrations/001_initial.sql) and [additive schedule-link migration](fitworld/migrations/002_scheduled_workout_logs.sql)

Local data lives in `instance/fitworld.sqlite3`; the generated local session signing key lives in `instance/session-secret`. Both are ignored by Git, as are virtual environments and credentials. Environment variables are read directly; a `.env` loader is not required. Public hosting still requires the production configuration described in the database guide.

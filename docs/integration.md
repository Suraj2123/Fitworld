# Application integration and extension guide

## Structure

The pages share authenticated navigation, data contracts, and UI primitives. Page controllers do not contain SQL; report modules do not format HTML or depend on a particular screen. A Home entry and a Progress calendar entry read the same stored activity through the same daily report.

| Module | Responsibility |
| --- | --- |
| `fitworld/api.py` | Account sessions, onboarding, CSRF token creation, and the shared authentication decorator. |
| `fitworld/app_api.py` | HTTP adapters: validate request shape, obtain the account from the session, call a domain module, return JSON. App endpoints also require completed onboarding. |
| `fitworld/catalog.py` | Shared workout/routine definitions, starter seeding, recommendation ordering, routine replacement, and schedules. |
| `fitworld/activity.py` | Validate and persist workout sets and meals, check scheduled-session ownership, and delete private activity atomically. |
| `fitworld/reports.py` | Daily workout/nutrition read model used by both Home and Progress. Nutrient totals preserve unknown values. |
| `fitworld/progress.py` | Month boundaries, complete/partial calendar counts, weekly averages, exercise comparisons, and weight history. |
| `fitworld/validation.py` | Shared typed form validation and canonical kg conversion for body weight. |
| `fitworld/views.py` | Page access control and server-rendered routes. |
| `templates/app_base.html`, `static/app.css` | Navigation, dialogs, shared layouts, form controls, typography, and color tokens. Page styles add composition rather than replacing these controls. |
| `static/js/client.js` | JSON requests, CSRF handling, local calendar dates, number/unit formatting, safe DOM creation, and form feedback. |
| `static/js/activity-ui.js` | Render saved workout, food, and nutrition details consistently across pages. |
| `static/js/workout-ui.js` | Shared workout cards, details, actual-set logging, and schedule rendering. |
| `static/home.js`, `static/js/workouts.js`, `static/js/progress.js` | Page-specific state and composition. Each page loads its own module. |

## Compatibility rules

1. Preserve existing migrations after sharing them. Add a new numbered migration; test it against a database populated using the previous schema. `002` adds a nullable scheduled-session link, preserving IDs, old logs, and their snapshots. It does not rebuild the original tables.
2. Use the authenticated account as the owner for every private query and write. Never accept an acting `user_id` from a body or query. Follow parent ownership when adding nested exercise, food, or photo features.
3. Keep public JSON fields stable. Add optional response fields instead of renaming existing ones; browser readers access the fields they need and ignore extra keys. Use a new endpoint or an explicit version for incompatible changes. Unknown display status labels fall back to their stored value.
4. Keep kilograms and seconds canonical in storage. Body-weight conversion and bounds live in one Python validator. Browser display formatting lives in `client.js`. New forms should use those functions rather than changing stored units.
5. Keep calendar dates explicit `YYYY-MM-DD` strings. The browser sends its local date; do not turn calendar labels into UTC midnight timestamps. Timestamps remain UTC. Date controls support 1900–2100. The server allows at most UTC tomorrow for historical entries to accommodate users ahead of UTC; the UI caps entries at the browser's local today.
6. Keep writes transactional. Selecting a routine replaces the active enrollment and creates its schedule together. A completed scheduled workout and its log are saved together. Removing that log reopens the session if no completed log remains. Database ownership/date/workout triggers protect linked logs, and a partial unique index prevents two completed logs for the same session.
7. Keep recorded history separate from the mutable catalog. Workout and exercise logs store names and actual values. New catalog content belongs in `workouts`, `exercises`, and routine prescriptions; no personal history is seeded.
8. Extend the existing modules where behavior already lives. For a new screen, reuse `app_base.html` and the daily report. Introduce another adapter only when there is an actual second implementation to support; the app does not require a repository framework or plugin system.

The seed catalog uses names as its current natural keys because the initial schema has no slug column. Re-running `init-db` inserts missing starter definitions and does not overwrite existing definitions. For larger catalog import/versioning work, add stable slugs in a migration before supporting renames as identifiers. Callers already use numeric IDs, so that change stays within catalog administration.

## Endpoints

All app endpoints require an authenticated, onboarded user. Writes require the session's `X-CSRF-Token`, obtained from `GET /api/session`. Existing account/onboarding endpoints are documented in [database.md](database.md).

| Method and endpoint | Contract |
| --- | --- |
| `GET /api/workouts?q=…` | `{workouts: [...]}` ordered by active routine, goal, experience, duration, and workout-space preferences. Each entry includes ordered prescriptions and equipment. Search covers workout names/descriptions and exercise names. |
| `GET /api/workouts/<id>` | `{workout: {...}}` with descriptions, intensity, minutes, and exercises. |
| `GET /api/routines?q=…` | `{routines: [...], current: object or null}`. Each routine includes its explicit week/day schedule. |
| `POST /api/routines/<id>/select` | `{starts_on}`. Returns `{current}`. The same routine/start is safe to select again. Replacing a plan preserves earlier sessions and skips future planned sessions from the old enrollment. |
| `GET /api/schedule?from=YYYY-MM-DD&to=YYYY-MM-DD` | `{schedule: [...]}` scoped to the account. Maximum range: 366 days. |
| `GET /api/activity?date=YYYY-MM-DD` | `{date, workouts, meals, nutrition, summary}`. Used by Home and the Progress day detail. |
| `GET /api/activity/recent` | `{workouts: [...]}` with the eight most recent completed/partial logs, ordered by performed date. |
| `POST /api/activity/workouts` | `performed_on`, `duration_minutes`, `status` (`completed` or `partial`), and either a catalog `workout_id` or a free-text `workout_name`. Manual workouts require a whole duration of at least one minute. Catalog workouts also support optional `estimated_calories`, `notes`, `scheduled_workout_id`, and `exercises`. Returns `{id}` with HTTP 201. Each actual set supplies `exercise_id`, `set_number`, and reps or duration; optional load is `load_kg`. An unrecorded set must be omitted. |
| `POST /api/activity/meals` | `meal_name`, `consumed_on`, and 1–50 `items`. Each item supplies `food_name`, `serving_description`, `servings`, `calories_per_serving`, and optional per-serving nutrients. Returns `{id}` with HTTP 201. Source is manual. |
| `DELETE /api/activity/workouts/<id>` | Remove an owned log and its sets, updating the linked schedule. Returns `{deleted: true}`. |
| `DELETE /api/activity/meals/<id>` | Remove an owned meal and its food items. Returns `{deleted: true}`. |
| `GET /api/progress?month=YYYY-MM&today=YYYY-MM-DD` | `{month, starts_on, ends_on, summary, days, records, measurements, milestones}`. `today` supplies the browser's local calendar date for the monthly-average denominator. |
| `POST /api/progress/measurements` | `measured_on`, `weight`, `unit_system` (`metric` or `imperial`). Upserts that day's measurement. Returns `{measurement}` with HTTP 201. Backdating does not replace the latest profile weight. |

Validation returns HTTP 422 with `{error, fields}`. Unknown private records return 404, including attempts to access another account's entry. Missing authentication returns 401, unfinished onboarding and conflicting scheduled completion return 409, malformed JSON returns 400, and missing CSRF returns 403. The browser never automatically retries a write after a timeout; it asks the user to refresh and check whether it saved.

## Progress calculations

- Calendar days show completed and partial workouts independently. A partial workout contributes actual time and an active day, but does not count as a completed workout or establish a personal benchmark.
- The weekly average is `completed × 7 / calendar days`: elapsed days in the current month, all days in a past month. The UI shows the denominator explicitly. An empty month has zero totals.
- Exercise benchmarks compare the best recorded load or longest recorded set duration in the chosen month with the best from completed workouts before that month. A first benchmark is labeled as a baseline, with no invented improvement. Longer duration is not interpreted as faster performance.
- Meals and workout totals are read independently, so adding food cannot multiply workout counts or calories burned. Calories burned are recorded estimates; blank values remain unknown.
- Nutrition multiplies per-serving values by servings. Each nutrient returns `known_total` and `missing_items`; an unknown protein value is distinct from zero protein. Partial totals are labeled.
- Weight history returns the last 30 measurements up to the selected month's end. Graphs are accompanied by an accessible table with the exact dates and preferred-unit values. There is no claim that every user should change weight in one direction.

## Adding the next feature

- **New workout/routine:** insert catalog rows and ordered prescriptions; existing cards, search, and details use the database records. New categories require a schema migration and a corresponding illustration/filter decision.
- **New progress metric:** add a field to the report and a renderer on Progress. Daily logs and other pages keep their existing contracts.
- **Editing logged activity:** add owned update operations to `activity.py` and use the existing transaction/schedule relationship. Existing removal plus re-entry is available for correcting a log now.
- **Goals/milestone generation:** existing `goals` and `milestones` remain available. The page reads real stored milestones; a later achievement writer can create them without changing the calendar or nutrition logic.
- **Photos or food analysis:** use the existing private photo/storage-key tables, add authorization on every read, and place analysis behind a server-side module with an explicit provider. The current UI uses manual nutrition and local vector catalog illustrations.

Public deployment needs the managed session key, HTTPS, production WSGI server, login rate limiting, and account recovery/verification described in the database guide. This contribution is the local course-project application.

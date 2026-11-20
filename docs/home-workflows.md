# Home logging workflows — November 19, 2026

This follow-up implements nine focused improvements on `improve-home-logging`,
based on integrated `main` at `9e4aa8d`. Each feature has its own commit. Existing
Home, Progress, account, and workout APIs remain compatible.

## Features and how to explain them

| Feature | What changed | Demo |
| --- | --- | --- |
| Save protection | Manual workout inputs are disabled while saving and restored after failure. | Slow or reject a save; values remain intact. |
| Independent loading | Daily activity, weekly goals, schedule, recent activity, suggestions, and routine load separately. Failed sections have retry controls. | Fail a schedule request; daily food and workouts still load. |
| Meal editing | Edit a saved meal using the composer. Server validation and a transaction replace its food items while preserving the meal ID. | Change two servings at 150 kcal into one; 300 becomes 150 on Home and Progress. |
| Recent foods | The twenty most recently used food/serving pairs provide one-serving draft shortcuts, using the most recent logged-date values. | Add oats again without typing its nutrition. |
| Manual workout editing | Correct name, duration, status, notes, or estimate on an owned manual log. The original date and ID remain unchanged. | Change a 20-minute completed walk into 10 minutes stopped early; totals and weekly goals recalculate. |
| Draft recovery | An account-specific session-storage draft survives reloads in the current tab. Clear/save removes it; app sign-out clears drafts. | Enter food and category, reload, and review the restored draft. |
| Favorite meals | Copy a saved meal into a private, independent template. Reuse fills the composer without logging anything automatically. | Favorite a meal, edit its source, and show that the template retains its original values. |
| Meal search | Search meal or food names, date ranges, and category across saved history, ten entries per page. | Find an older meal, reuse it, or edit it without navigating day by day. |
| Categories | Breakfast, lunch, dinner, snacks, and uncategorized organize daily entries. | Assign breakfast and filter history to breakfast. |

“Use as new meal” creates a separate draft. “Edit meal” changes the original entry.
Both refuse to overwrite an existing draft. Editing keeps the original date even
if the displayed day changes; the form states that date. Canceling edits leaves
the database unchanged. Unknown nutrients stay unknown rather than becoming zero.

Favorite names are unique per account, with a maximum of 100 favorites. To replace
a favorite, remove its template and favorite the updated saved meal. Removing a
template leaves daily logs unchanged. Recent foods come from saved logs; favorites
remain available even when their source log is deleted.

## Local setup

From the repository, with the existing environment available:

```sh
.venv/bin/python -m flask --app fitworld init-db
.venv/bin/python -m flask --app fitworld run --port 5001
```

`008_favorite_meals.sql` creates private templates. `009_meal_categories.sql` adds
category fields to logs and templates. Existing records stay `uncategorized`,
even if their names happen to contain “Breakfast” or “Lunch.” Applied migrations
are unchanged. Re-running `init-db` is safe. The implementation/testing did not
migrate or modify the developer's real local database.

## Code map

- `static/home.js`: page orchestration, independent loading, and save requests.
- `static/js/meal-composer.js`: editable food draft, preview, reuse, edit state.
- `static/js/manual-workout.js`: manual workout edit/cancel state.
- `static/js/meal-library.js`: recent-food and favorite controls.
- `static/js/meal-search.js`: filters, pagination, and search results.
- `static/js/meal-recovery.js`: account-scoped browser-tab recovery.
- `activity.py`: validation and atomic owned activity writes.
- `meal_library.py`: private favorite snapshots and deletion.
- `reports.py`: account-scoped search, recent foods, and daily aggregates.
- `app_api.py`: authenticated HTTP adapters; owners come from the session.

## Checks and demo sequence

Run the required checks in CONTRIBUTING.md. The final Python suite contains 85
tests and the Node suite contains 7 tests. Browser scripts cover the interactions
that backend unit tests cannot observe.

For the optional browser checks, install the development-only browser driver:

```sh
npm install --no-save --package-lock=false playwright@1.65.1
.venv/bin/python tests/run_browser_server.py
# In a second terminal:
node tests/home-browser.cjs
node tests/home-features.cjs
```

The server uses a temporary database on port 5057 and a separate cookie name.
The scripts use test accounts and installed Chrome. Screenshots are saved under
`/tmp/fitworld-home*.png`. Stop the server with Ctrl+C after testing.

A short presentation sequence:

1. Save two servings of oats at 150 calories each, in the breakfast category.
2. Edit the meal to one serving; explain that its ID remains the same and totals
   are read again from the server.
3. Favorite the meal. Reuse it on another date and adjust servings before saving.
4. Enter an unfinished snack, reload, then clear the recovered draft.
5. Search for oats across dates and show category filtering and pagination.
6. Log and edit a manual walk. Open Progress to show the shared updated data.
7. Explain the failed-save and failed-section checks using the automated browser
   cases rather than claiming a successful network request proves error handling.

## Limits

Recovery is browser-tab storage, not a synchronized or permanent meal backup.
Browsers can clear or disallow storage. Ordinary logging remains usable if recovery
is unavailable. Catalog/scheduled workout edits, automatic nutrition targets,
custom-workout building, and photo analysis are outside this change. Updates use
the last submitted valid values; there is no multi-device conflict-resolution UI.


## November 20: reuse manual workouts

Home's manual workout cards now offer **Use as new workout**. This copies the
name, duration, completion status, notes, and optional calorie estimate into the
manual form. Choose a destination with the existing day controls, adjust the
values, then select **Add workout**. The request creates a new log; the source ID,
original date, and schedule associations are not copied. Blank calorie estimates
stay unknown. Nothing is saved until the form is submitted.

An unfinished draft or active edit cannot be overwritten by reuse. Clear the
workout form before loading another. Failed saves retain the copied draft. Catalog
and scheduled workouts do not offer this manual shortcut. No migration is needed.

Demo: copy a ten-minute partial walk from yesterday, choose today, change it to
25 minutes and mark it completed, then save. Yesterday's partial walk remains
unchanged while today's new entry contributes to today's totals and weekly goal.

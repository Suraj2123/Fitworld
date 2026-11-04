# Home logging update — November 4, 2026

## What changed and why

This update focuses on Suraj's Home page responsibility: recording food and workouts accurately, with behavior that is straightforward to explain in a demo. The merged application already had accounts, database persistence, workouts, routines, and Progress. This work extends that implementation rather than creating a separate logging system.

| Change | Before | Now / reason |
| --- | --- | --- |
| Multiple foods per meal | Home saved one food per entry. | Add or remove food rows and save them together under an optional meal name. Breakfast can contain oats and milk in one entry. The form supports up to 50 foods, matching the existing API limit. |
| Live nutrition preview | Calculations were visible after saving. | Preview calories, protein, carbs, fat, and sodium before saving. Each value is multiplied by servings eaten. This helps catch serving mistakes. |
| Meal reuse | Repeated meals required retyping. | “Use as new meal” copies a logged meal into an editable draft. Choose another day, change servings, and save. The original entry stays intact. |
| Draft protection | No reuse workflow existed. | Reuse refuses to overwrite an unfinished draft. Inputs are locked during a meal save, and failed saves retain the entered values. |
| Daily nutrition | Home emphasized calories alone. | Home also displays the day's protein, carbs, fat, and sodium totals, labeling partial totals when some values are unknown. |
| Date navigation | Only the date picker was available. | Previous day, next day, and Today controls make history easier to navigate. Labels beside both forms clearly state the save date. Future-day navigation is disabled. |
| Workout details | Manual logging exposed name, duration, and completion. | Optional notes and calorie estimates now use the existing backend fields. Leaving an estimate blank preserves “unknown.” |
| Loading feedback | Old entries could stay visible while a different date loaded. | Old daily entries and totals are cleared during loading. A failed load shows a retry instruction rather than presenting old entries under a new date. |

## How it works

1. **HTML defines the form.** `home.html` includes a reusable food-row template, date buttons, workout details, and a nutrition summary area.
2. **The meal composer manages the draft.** `meal-composer.js` adds and removes rows, gives each field a unique label association, restores keyboard focus, and copies meal data into the form. Drafts live in browser memory; they are not saved until Save meal is selected.
3. **A small calculation module produces the preview.** `meal-draft.js` multiplies each per-serving nutrient by servings and counts missing values. A blank protein field is unknown; an explicit zero is known zero.
4. **Home sends the data to the existing API.** `home.js` sends one `POST /api/activity/meals` request with the meal name, selected date, and an array of foods. The existing backend validates all foods and saves the meal atomically in SQLite.
5. **The page reloads authoritative totals.** After a successful save, Home requests the day's data again. Progress uses the same stored records. The frontend preview does not replace server validation.

Example: two servings of oats at 150 kcal each plus half a serving of milk at 100 kcal per serving equals **350 kcal**. Copy that meal to another date and reduce oats to one serving: the copied meal becomes **200 kcal**, while the original remains 350.

No database migration or new runtime dependency was needed. The existing meal schema already supported several food items, and manual workouts already supported notes and estimated calories.

## Demo walkthrough

1. Open Home and choose a past date. Point out the date shown beside both save buttons.
2. Enter “Breakfast” as the meal name. Add oats: serving size “cup,” servings 2, calories per serving 150, and protein per serving 5.
3. Add a second food: milk, serving size “cup,” servings 0.5, and calories per serving 100. Leave its protein blank.
4. Explain the preview: 350 kcal and 10 g known protein, with protein marked partial because the milk value is unknown.
5. Save the meal and reload. The entry remains because it is stored in the database.
6. Select “Use as new meal,” move to the next day, reduce oats to one serving, and save. Show that the first day's meal is unchanged.
7. Log a 25-minute walk with an optional note and calorie estimate. Show the separate workout-time and food-calorie totals.
8. Open Progress for that date to show that Home and Progress share the same records.

A useful explanation in your own words: “I extended the Home form to collect an array of foods. JavaScript calculates a preview, but Flask validates and saves the data. I reused the existing database design so Home and Progress stay consistent.”

## Verification

- **43 Python tests passed**, including new checks for multi-food totals, reuse across dates without altering the original, preservation of unknown versus zero nutrients, and manual workout notes/estimates.
- **2 JavaScript calculation tests passed**, covering fractional servings, partial totals, and invalid or incomplete draft values.
- **Chrome browser checks passed** for multi-food creation, persistence after reload, meal reuse across dates, protection of unfinished drafts, workout details, row removal and focus, rejected-save recovery, mobile overflow, and Today navigation. No browser JavaScript errors were observed.
- Desktop (1440 px) and mobile (390 px) layouts were captured and inspected.
- Tests used temporary databases and test accounts, leaving real user data untouched.

Run the automated tests from the repository:

```sh
.venv/bin/python -m unittest discover -s tests -v
node --test tests/meal-draft.test.mjs
```

Optional browser regression check (requires Chrome and the Playwright development package):

```sh
npm install --no-save --package-lock=false playwright
.venv/bin/python tests/run_browser_server.py
# In another terminal, from the repository:
node tests/home-browser.cjs
```

The browser server uses a temporary database on port 5057. Stop it with Ctrl+C when finished. Browser screenshots are written to `/tmp/fitworld-home-desktop.png` and `/tmp/fitworld-home-mobile.png`.

## Scope and remaining limits

Changes are local on `feature/home-page`; they have not been committed, pushed, or merged. Meal reuse is available from the currently viewed day's entries: open the source date first, copy the meal, and then change to the destination date. Drafts survive date changes but do not survive a full page reload. Editing an already saved meal in place and a searchable favorite-food library remain separate future improvements. Nutrition and calorie estimates are manually entered, not automatically inferred.

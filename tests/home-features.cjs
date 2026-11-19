const { chromium } = require("playwright");
const assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const base = "http://127.0.0.1:5057";
  async function write(path, data, method = "POST") {
    const session = await (await context.request.get(base + "/api/session")).json();
    const r = await context.request.fetch(base + "/api/" + path, {
      method,
      data,
      headers: { "X-CSRF-Token": session.csrf_token },
    });
    assert(r.ok(), await r.text());
  }
  await write("register", {
    display_name: "Home Demo",
    email: `demo${Date.now()}@example.com`,
    password: "test-only-long-password",
  });
  await write(
    "onboarding/profile",
    {
      age: 25,
      weight: 70,
      unit_system: "metric",
      experience_level: "beginner",
      current_workouts_per_week: 0,
    },
    "PUT",
  );
  await write(
    "onboarding/preferences",
    {
      primary_goal: "build_strength",
      training_location: "home",
      target_days_per_week: 3,
      session_minutes: 30,
    },
    "PUT",
  );
  await write("onboarding/complete", {});
  await page.goto(base + "/home?date=2026-01-05");
  await page.waitForSelector("#today-stats:not([aria-busy])");
  await write("activity/meals", {
    meal_name: "Breakfast",
    consumed_on: "2026-01-05",
    items: [
      { food_name: "Oats", serving_description: "cup", servings: 2, calories_per_serving: 150 },
    ],
  });
  await page.reload();
  await page.getByRole("button", { name: "Edit Breakfast", exact: true }).click();
  await page.locator('[data-field="servings"]').fill("1");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("#calorie-total").textContent === "150");
  assert.equal(await page.locator("#food-list .entry-card").count(), 1);
  assert.equal(await page.locator('#food-form [type="submit"]').innerText(), "Save meal");
  // Favorites are snapshots and copying one must preserve an existing draft.
  await page
    .locator("#food-list")
    .getByRole("button", { name: "Favorite Breakfast", exact: true })
    .click();
  await page.getByText("Favorite meals", { exact: true }).click();
  await page
    .locator("#favorite-meals")
    .getByRole("button", { name: "Use Breakfast", exact: true })
    .click();
  assert.equal(await page.locator('[data-field="servings"]').inputValue(), "1");
  await page.locator("#clear-meal").click();
  await page.getByText("Recent foods", { exact: true }).click();
  await page
    .locator("#recent-foods")
    .getByRole("button", { name: "Oats · cup", exact: true })
    .click();
  await page.locator("#meal-category").selectOption("snack");
  await page.locator("#previous-day").click();
  await page.reload();
  await page.waitForFunction(
    () => document.querySelector('[data-field="food_name"]').value === "Oats",
  );
  assert.equal(await page.locator("#home-date").inputValue(), "2026-01-04");
  assert.equal(await page.locator("#meal-category").inputValue(), "snack");
  await page.locator("#clear-meal").click();
  await page.reload();
  await page.waitForSelector("#today-stats .stat-card");
  assert.equal(await page.locator('[data-field="food_name"]').inputValue(), "");

  // Editing a search result keeps its original date even while viewing a different day.
  await page.getByText("Find previous meals", { exact: true }).click();
  await page.locator("#meal-query").fill("oats");
  await page.getByRole("button", { name: "Search meals", exact: true }).click();
  await page
    .locator("#meal-search-results")
    .getByRole("button", { name: "Edit Breakfast", exact: true })
    .click();
  await page.locator('[data-field="servings"]').fill("3");
  await page.locator("#meal-category").selectOption("breakfast");
  await page.reload();
  await page.waitForFunction(() => document.querySelector('[data-field="servings"]').value === "3");
  assert((await page.locator("#food-date-note").innerText()).includes("Jan 5"));
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await page.waitForFunction(
    () =>
      document.querySelector('#food-form [type="submit"]').textContent === "Save meal" &&
      document.querySelector("#food-form").dataset.busy === "false",
  );
  const corrected = await (
    await context.request.get(base + "/api/activity?date=2026-01-05")
  ).json();
  assert.equal(corrected.nutrition.calories.known_total, 450);
  assert.equal(corrected.meals[0].meal_category, "breakfast");
  const favorite = await (await context.request.get(base + "/api/meals/favorites")).json();
  assert.equal(favorite.meals[0].items[0].servings, 1);

  await page.locator("#workout-name").fill("Walk");
  await page.locator("#workout-minutes").fill("20");
  await page.locator('#workout-form [type="submit"]').click();
  await page
    .locator("#today-workouts")
    .getByRole("button", { name: "Edit Walk", exact: true })
    .click();
  await page.locator("#workout-minutes").fill("10");
  await page.locator("#manual-workout-status").selectOption("partial");
  await page.locator("#manual-notes").fill("Stopped for rain");
  await page.getByRole("button", { name: "Save workout changes", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("#workout-total").textContent === "10");
  assert((await page.locator("#today-workouts").innerText()).includes("Stopped for rain"));
  assert.equal(await page.locator("#today-workouts .entry-card").count(), 1);

  await page.getByText("Find previous meals", { exact: true }).click();
  await page.locator("#meal-search-category").selectOption("breakfast");
  await page.getByRole("button", { name: "Search meals", exact: true }).click();
  await page.waitForFunction(() =>
    document.querySelector("#meal-search-count").textContent.includes("1 meal ·"),
  );
  await page.locator("#meal-search-category").selectOption("dinner");
  await page.getByRole("button", { name: "Search meals", exact: true }).click();
  await page.waitForFunction(
    () => document.querySelector("#meal-search-count").textContent === "No matching meals.",
  );
  await page.getByText("Favorite meals", { exact: true }).click();
  await page
    .locator("#favorite-meals")
    .getByRole("button", { name: "Remove favorite Breakfast", exact: true })
    .click();
  await page
    .locator("#delete-dialog")
    .getByRole("button", { name: "Remove entry", exact: true })
    .click();
  await page.waitForFunction(
    () => !document.querySelector("#favorite-meals").textContent.includes("Use Breakfast"),
  );
  assert.equal(
    (await (await context.request.get(base + "/api/activity?date=2026-01-05")).json()).meals.length,
    1,
  );

  // Pagination remains usable with keyboard navigation and filters reset the page.
  for (let index = 0; index < 11; index++) {
    await write("activity/meals", {
      meal_name: `Lunch ${index}`,
      consumed_on: "2026-01-03",
      meal_category: "lunch",
      items: [
        { food_name: "Rice", serving_description: "cup", servings: 1, calories_per_serving: 200 },
      ],
    });
  }
  await page.locator("#meal-search-category").selectOption("lunch");
  await page.locator("#meal-query").fill("Rice");
  await page.getByRole("button", { name: "Search meals", exact: true }).click();
  await page.waitForFunction(() =>
    document.querySelector("#meal-search-count").textContent.includes("Page 1 of 2"),
  );
  await page.locator("#meal-search-next").focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() =>
    document.querySelector("#meal-search-count").textContent.includes("Page 2 of 2"),
  );
  assert.equal(await page.locator("#meal-search-results .entry-card").count(), 1);
  await page.locator("#meal-query").fill("Breakfast");
  await page.locator("#meal-search-category").selectOption("");
  await page.getByRole("button", { name: "Search meals", exact: true }).click();
  await page
    .locator("#meal-search-results")
    .getByRole("button", { name: "Edit Breakfast", exact: true })
    .click();
  await page.locator('[data-field="servings"]').fill("4");
  await page.route("**/api/activity/meals/*", (route) =>
    route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify({ error: "Test rejected edit" }),
    }),
  );
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await page.waitForSelector("#food-form .form-error:not([hidden])");
  assert.equal(await page.locator('[data-field="servings"]').inputValue(), "4");
  assert.equal(await page.locator("#meal-category").isEnabled(), true);
  await page.unroute("**/api/activity/meals/*");
  await page.locator("#clear-meal").click();
  assert.equal(
    (await (await context.request.get(base + "/api/activity?date=2026-01-05")).json()).nutrition
      .calories.known_total,
    450,
  );

  await page.setViewportSize({ width: 375, height: 812 });
  assert(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    "Mobile overflow",
  );
  await page.screenshot({
    path: "/tmp/fitworld-home-features-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "/tmp/fitworld-home-features-desktop.png",
    fullPage: true,
  });

  // A different account in the same browser tab cannot recover this account's draft.
  await page.locator('[data-field="food_name"]').fill("Private unfinished meal");
  await write("logout", {});
  await write("register", {
    display_name: "Second",
    email: `second${Date.now()}@example.com`,
    password: "test-only-long-password",
  });
  await write(
    "onboarding/profile",
    {
      age: 25,
      weight: 70,
      unit_system: "metric",
      experience_level: "beginner",
      current_workouts_per_week: 0,
    },
    "PUT",
  );
  await write(
    "onboarding/preferences",
    {
      primary_goal: "build_strength",
      training_location: "home",
      target_days_per_week: 3,
      session_minutes: 30,
    },
    "PUT",
  );
  await write("onboarding/complete", {});
  await page.reload();
  await page.waitForSelector("#today-stats .stat-card");
  assert.equal(await page.locator('[data-field="food_name"]').inputValue(), "");
  await page.locator('[data-field="food_name"]').fill("Second draft");
  await page.locator("#app-signout").click();
  await page.waitForURL("**/?login=1");
  assert.equal(
    await page.evaluate(() =>
      Object.keys(sessionStorage).some((key) => key.startsWith("fitworld:meal-draft:")),
    ),
    false,
  );

  assert.deepEqual(errors, []);
  await browser.close();
  console.log("PASS: Home editing and shortcuts");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

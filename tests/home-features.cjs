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
  // MORE_FEATURES
  assert.deepEqual(errors, []);
  await browser.close();
  console.log("PASS: Home editing and shortcuts");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

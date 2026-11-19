import test from "node:test";
import assert from "node:assert/strict";
import { mealTotals } from "../fitworld/static/js/meal-draft.js";

test("meal preview multiplies fractional servings and separates unknown from zero", () => {
  const totals = mealTotals([
    { servings: "2", calories_per_serving: "150", protein_g_per_serving: "5", sodium_mg_per_serving: "0" },
    { servings: "0.5", calories_per_serving: "100", protein_g_per_serving: "", sodium_mg_per_serving: null },
  ]);
  assert.equal(totals[0].total, 350);
  assert.equal(totals[0].missing, 0);
  assert.equal(totals[1].total, 10);
  assert.equal(totals[1].missing, 1);
  assert.equal(totals[4].total, 0);
  assert.equal(totals[4].missing, 1);
});
test("incomplete and invalid draft fields do not invent nutrition values", () => {
  for (const servings of ["", "0", "-1", "NaN", "Infinity"]) {
    assert.equal(mealTotals([{ servings, calories_per_serving: "150" }])[0].missing, 1);
  }
  for (const calories_per_serving of ["", null, undefined, "NaN", "Infinity", "-1"]) {
    const total = mealTotals([{ servings: "1", calories_per_serving }])[0];
    assert.equal(total.total, 0);
    assert.equal(total.missing, 1);
  }
});

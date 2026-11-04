// Pure calculation shared by the meal preview and its regression tests.
export const nutrients = [
  ["calories_per_serving", "kcal"], ["protein_g_per_serving", "g protein"],
  ["carbs_g_per_serving", "g carbs"], ["fat_g_per_serving", "g fat"],
  ["sodium_mg_per_serving", "mg sodium"],
];
export function mealTotals(items) {
  return nutrients.map(([key, unit]) => {
    let total = 0, missing = 0;
    for (const item of items) {
      const value = item[key], servings = Number(item.servings);
      if (value === "" || value == null || !Number.isFinite(Number(value)) || Number(value) < 0 || !Number.isFinite(servings) || servings <= 0) missing++;
      else total += Number(value) * servings;
    }
    return { key, unit, total, missing };
  });
}

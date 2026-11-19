import { $, el, number, notify } from "./client.js";
import { mealTotals } from "./meal-draft.js";

export function initMealComposer() {
  const container = $("#meal-items"), form = $("#food-form");
  let serial = 0;
  function items() {
    return [...container.children].map((row) => Object.fromEntries(
      [...row.querySelectorAll("[data-field]")].map((input) => [input.dataset.field, input.value.trim()]),
    ));
  }
  function update() {
    [...container.children].forEach((row, index) => {
      row.querySelector("legend").textContent = `Food ${index + 1}`;
      const remove = row.querySelector(".remove-draft-food");
      remove.hidden = container.children.length === 1;
      remove.setAttribute("aria-label", `Remove food ${index + 1} from draft`);
    });
    $("#add-meal-item").disabled = container.children.length >= 50;
    const preview = $("#meal-preview");
    preview.replaceChildren(el("strong", "", "Meal preview"));
    const totals = mealTotals(items());
    preview.append(el("p", "", totals.map(({ unit, total, missing }) => `${number(total)} ${unit}${missing ? " (partial)" : ""}`).join(" · ")));
    preview.append(el("span", "small muted", "Not saved yet. Totals use servings eaten; blank nutrients remain unknown."));
  }
  function add(item = {}, focus = true) {
    if (container.children.length >= 50) return;
    const row = $("#meal-item-template").content.firstElementChild.cloneNode(true);
    const id = ++serial;
    row.querySelectorAll("[data-field]").forEach((input) => {
      const key = input.dataset.field;
      input.id = key === "food_name" && !container.children.length ? "food-name" : `food-${id}-${key}`;
      input.name = `food_${id}_${key}`;
      row.querySelector(`[data-label="${key}"]`).htmlFor = input.id;
      input.value = item[key] ?? (key === "servings" ? "1" : "");
    });
    row.querySelector(".remove-draft-food").addEventListener("click", () => {
      const next = row.nextElementSibling || row.previousElementSibling;
      row.remove(); update(); next?.querySelector("input").focus();
    });
    row.addEventListener("input", update);
    container.append(row); update();
    if (focus) row.querySelector("input").focus();
  }
  function reset() {
    form.reset(); container.replaceChildren(); add({}, false);
    form.querySelector(".form-error").hidden = true;
  }
  $("#add-meal-item").addEventListener("click", () => add());
  $("#clear-meal").addEventListener("click", () => { reset(); container.querySelector("input").focus(); });
  reset();
  return {
    items, reset,
    reuse(meal) {
      if (form.dataset.busy === "true") return;
      // Preserve an existing draft rather than silently replacing entered food.
      const hasDraft = $("#meal-name").value.trim() || items().some((item) =>
        Object.entries(item).some(([key, value]) => key === "servings" ? value !== "1" : value !== ""));
      if (hasDraft) { notify("Save or clear your current meal draft before reusing a meal."); form.scrollIntoView({ block: "center" }); return; }
      container.replaceChildren(); $("#meal-name").value = meal.meal_name;
      meal.items.forEach((item) => add(item, false));
      container.querySelector("input").focus();
      notify("Meal copied to your draft. Choose a date, adjust servings, then save.");
    },
  };
}

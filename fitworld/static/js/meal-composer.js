import { $, el, number, notify } from "./client.js";
import { mealTotals } from "./meal-draft.js";

export function initMealComposer() {
  const container = $("#meal-items"),
    form = $("#food-form");
  let serial = 0,
    editing = null;
  function items() {
    return [...container.children].map((row) =>
      Object.fromEntries(
        [...row.querySelectorAll("[data-field]")].map((input) => [
          input.dataset.field,
          input.value.trim(),
        ]),
      ),
    );
  }
  function changed() {
    form.dispatchEvent(new Event("meal:draft"));
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
    preview.append(
      el(
        "p",
        "",
        totals
          .map(
            ({ unit, total, missing }) => `${number(total)} ${unit}${missing ? " (partial)" : ""}`,
          )
          .join(" · "),
      ),
    );
    preview.append(
      el(
        "span",
        "small muted",
        "Not saved yet. Totals use servings eaten; blank nutrients remain unknown.",
      ),
    );
    changed();
  }
  function add(item = {}, focus = true) {
    if (container.children.length >= 50) return;
    const row = $("#meal-item-template").content.firstElementChild.cloneNode(true);
    const id = ++serial;
    row.querySelectorAll("[data-field]").forEach((input) => {
      const key = input.dataset.field;
      input.id =
        key === "food_name" && !container.children.length ? "food-name" : `food-${id}-${key}`;
      input.name = `food_${id}_${key}`;
      row.querySelector(`[data-label="${key}"]`).htmlFor = input.id;
      input.value = item[key] ?? (key === "servings" ? "1" : "");
    });
    row.querySelector(".remove-draft-food").addEventListener("click", () => {
      const next = row.nextElementSibling || row.previousElementSibling;
      row.remove();
      update();
      next?.querySelector("input").focus();
    });
    row.addEventListener("input", update);
    container.append(row);
    update();
    if (focus) row.querySelector("input").focus();
  }
  function reset() {
    editing = null;
    form.dataset.submitLabel = "Save meal";
    form.querySelector('[type="submit"]').textContent = "Save meal";
    $("#clear-meal").textContent = "Clear draft";
    $("#meal-edit-status").textContent = "";
    form.reset();
    container.replaceChildren();
    add({}, false);
    form.querySelector(".form-error").hidden = true;
  }
  $("#add-meal-item").addEventListener("click", () => add());
  $("#clear-meal").addEventListener("click", () => {
    reset();
    container.querySelector("input").focus();
  });
  reset();
  function hasDraft() {
    return (
      editing ||
      $("#meal-name").value.trim() ||
      $("#meal-category").value !== "uncategorized" ||
      items().some((item) =>
        Object.entries(item).some(([key, value]) =>
          key === "servings" ? value !== "1" : value !== "",
        ),
      )
    );
  }
  function load(meal, edit = false) {
    if (form.dataset.busy === "true") return false;
    if (hasDraft()) {
      notify("Save or clear your current meal draft before opening another meal.");
      form.scrollIntoView({ block: "center" });
      return false;
    }
    container.replaceChildren();
    $("#meal-name").value = meal.meal_name;
    $("#meal-category").value = meal.meal_category || "uncategorized";
    meal.items.forEach((item) => add(item, false));
    container.querySelector("input").focus();
    if (edit) {
      editing = { id: meal.id, date: meal.consumed_on };
      form.dataset.submitLabel = "Save changes";
      form.querySelector('[type="submit"]').textContent = "Save changes";
      $("#clear-meal").textContent = "Cancel editing";
      $("#meal-edit-status").textContent =
        `Editing ${meal.meal_name} from ${meal.consumed_on}. Changes stay on that date.`;
    }
    notify(
      edit
        ? "Meal ready to edit. Save changes when finished."
        : "Meal copied to your draft. Choose a date, adjust servings, then save.",
    );
    changed();
    return true;
  }
  return {
    items,
    hasDraft,
    snapshot: () => ({
      meal_name: $("#meal-name").value,
      meal_category: $("#meal-category").value,
      items: items(),
      editing,
    }),
    restore(draft) {
      return load(
        { ...draft, id: draft.editing?.id, consumed_on: draft.editing?.date },
        Boolean(draft.editing),
      );
    },
    addFood(food) {
      if (form.dataset.busy === "true") return;
      const draft = items();
      if (
        draft.length === 1 &&
        Object.entries(draft[0]).every(([key, value]) =>
          key === "servings" ? value === "1" : value === "",
        )
      )
        container.replaceChildren();
      if (container.children.length >= 50) {
        notify("A meal can contain up to 50 foods.");
        return;
      }
      add({ ...food, servings: 1 });
      notify("Food added to your draft. Adjust servings before saving.");
    },
    reset,
    editing: () => editing,
    reuse: (meal) => load(meal),
    edit: (meal) => load(meal, true),
  };
}

import { $, notify } from "./client.js";

// Session storage survives reloads, but stays inside this browser tab and account.
export function initMealRecovery(composer, userId, getDate, selectDate) {
  const key = `fitworld:meal-draft:${userId}`;
  let restoring = false,
    unavailable = false;
  function save() {
    if (restoring || unavailable) return;
    try {
      if (composer.hasDraft())
        sessionStorage.setItem(key, JSON.stringify({ ...composer.snapshot(), date: getDate() }));
      else sessionStorage.removeItem(key);
    } catch {
      unavailable = true;
      notify("Draft recovery is unavailable in this browser. Keep this tab open until you save.");
    }
  }
  try {
    const raw = sessionStorage.getItem(key);
    if (raw && !composer.hasDraft()) {
      const draft = JSON.parse(raw);
      if (
        !draft ||
        !/^\d{4}-\d{2}-\d{2}$/.test(draft.date) ||
        typeof draft.meal_name !== "string" ||
        (draft.editing &&
          (!Number.isSafeInteger(draft.editing.id) ||
            draft.editing.id < 1 ||
            !/^\d{4}-\d{2}-\d{2}$/.test(draft.editing.date))) ||
        !Array.isArray(draft.items) ||
        !draft.items.length ||
        draft.items.length > 50 ||
        draft.items.some(
          (item) =>
            !item ||
            typeof item !== "object" ||
            Object.values(item).some(
              (value) => value !== null && typeof value !== "string" && typeof value !== "number",
            ),
        )
      ) {
        sessionStorage.removeItem(key);
      } else {
        restoring = true;
        selectDate(draft.date);
        composer.restore(draft);
        restoring = false;
        notify("Your unfinished meal was restored. Review it before saving.");
      }
    }
  } catch {
    // Malformed or unavailable storage must never prevent ordinary logging.
    try {
      sessionStorage.removeItem(key);
    } catch {
      unavailable = true;
    }
    restoring = false;
  }
  $("#food-form").addEventListener("input", save);
  $("#food-form").addEventListener("meal:draft", save);
  $("#home-date").addEventListener("change", save);
  document.addEventListener("fitworld:date", save);
  return { save };
}

// Latest team Home flow: food, free-text workouts, separate totals, and removal.
// Shared modules add persistence, catalog sessions, and personal progress.
import {
  $,
  el,
  api,
  session,
  localDate,
  dateLabel,
  addDays,
  number,
  empty,
  stat,
  badge,
  saveForm,
  notify,
  showError,
} from "./js/client.js";
import { renderWorkouts, renderMeals, renderNutrition } from "./js/activity-ui.js";
import { initWorkoutLogging, renderCards, renderSchedule } from "./js/workout-ui.js";
import { renderWeeklyGoal } from "./js/weekly-goal-ui.js";

import { initMealComposer } from "./js/meal-composer.js";

const mealComposer = initMealComposer();
const dateInput = $("#home-date");
dateInput.value = new URLSearchParams(location.search).get("date") || localDate();
if (!dateInput.value || dateInput.value > localDate() || dateInput.value < "1900-01-01")
  dateInput.value = localDate();
dateInput.max = localDate();
let revision = 0;
function updateDateLabels() {
  const label = dateLabel(dateInput.value, { month: "long", day: "numeric", year: "numeric" });
  $("#logging-date").textContent = `Food and manual workouts will be saved for ${label}.`;
  $("#food-date-note").textContent = `Saving this meal for ${label}.`;
  $("#workout-date-note").textContent = `Saving this workout for ${label}.`;
  $("#next-day").disabled = dateInput.value >= localDate();
  $("#previous-day").disabled = dateInput.value <= "1900-01-01";
  $("#today-button").disabled = dateInput.value === localDate();
}
updateDateLabels();

function sectionError(container, message, retry) {
  container.removeAttribute("aria-busy");
  empty(container, message);
  const button = el("button", "secondary-button", "Retry");
  button.type = "button";
  button.addEventListener("click", retry);
  container.append(button);
}

async function refresh() {
  const current = ++revision,
    selected = dateInput.value || localDate();
  updateDateLabels();
  async function section(selector, load, render, failure) {
    const container = $(selector);
    async function run() {
      if (current !== revision) return;
      container.setAttribute("aria-busy", "true");
      empty(container, "Loading…");
      try {
        const data = await load();
        if (current !== revision) return;
        render(data);
      } catch {
        if (current !== revision) return;
        failure?.();
        sectionError(container, "This section couldn’t load. Try again.", run);
      } finally {
        if (current === revision) container.removeAttribute("aria-busy");
      }
    }
    return run();
  }
  $("#today-muscles").textContent = "";
  $("#daily-nutrition").replaceChildren();
  $("#calorie-total").textContent = "—";
  $("#workout-total").textContent = "—";
  empty($("#food-list"), "Loading food entries…");
  empty($("#today-workouts"), "Loading workouts…");
  await Promise.all([
    section(
      "#today-stats",
      () => api(`activity?date=${selected}`),
      renderDay,
      () => {
        empty($("#food-list"), "Food entries could not be loaded. Retry your daily check-in.");
        empty($("#today-workouts"), "Workouts could not be loaded. Retry your daily check-in.");
      },
    ),
    section(
      "#weekly-goal",
      () => api(`progress/weekly?date=${selected}&today=${localDate()}`),
      (data) => renderWeeklyGoal($("#weekly-goal"), data),
    ),
    section(
      "#home-schedule",
      () => api(`schedule?from=${localDate()}&to=${addDays(localDate(), 6)}`),
      (data) => renderSchedule($("#home-schedule"), data.schedule),
    ),
    section("#recent-workouts", () => api("activity/recent"), renderRecent),
  ]);
}

function renderDay(day) {
  const summary = day.summary,
    stats = $("#today-stats");
  stats.replaceChildren(
    stat(
      "Workouts completed",
      number(summary.completed),
      summary.partial
        ? `${summary.partial} stopped early · ${number(summary.duration_minutes)} min total`
        : `${number(summary.duration_minutes)} minutes of movement`,
      true,
    ),
    stat(
      "Calories consumed",
      number(day.nutrition.calories.known_total, 0),
      "kcal from your food log",
    ),
    stat(
      "Estimated calories burned",
      summary.workouts_missing_calories === day.workouts.length && day.workouts.length
        ? "—"
        : number(summary.estimated_calories_burned, 0),
      summary.workouts_missing_calories
        ? "Some workouts have no estimate"
        : "kcal from your recorded estimates",
    ),
  );
  stats.removeAttribute("aria-busy");
  $("#today-muscles").textContent = summary.muscle_groups.length
    ? `Muscle groups: ${summary.muscle_groups.join(" · ")}`
    : "Every starting point is welcome. Choose a workout when you’re ready.";
  renderNutrition($("#daily-nutrition"), day.nutrition);
  $("#calorie-total").textContent = number(day.nutrition.calories.known_total, 0);
  $("#workout-total").textContent = number(summary.duration_minutes);
  renderWorkouts($("#today-workouts"), day);
  renderMeals($("#food-list"), day, mealComposer.reuse);
}

function renderRecent(recent) {
  const container = $("#recent-workouts");
  container.replaceChildren();
  if (!recent.workouts.length)
    empty(
      container,
      "Your story starts here. Try a workout and your recent movement will appear here.",
    );
  recent.workouts.forEach((workout) => {
    const card = el("a", "recent-card");
    card.href = `/progress?month=${workout.performed_on.slice(0, 7)}&date=${workout.performed_on}`;
    card.append(
      el("h3", "", workout.workout_name),
      badge(workout.status),
      el(
        "p",
        "",
        `${dateLabel(workout.performed_on)} · ${number(workout.duration_seconds / 60)} min`,
      ),
    );
    container.append(card);
  });
}

function selectDate(value) {
  if (!value || value < "1900-01-01" || value > localDate()) value = localDate();
  dateInput.value = value;
  history.replaceState({}, "", `/home?date=${value}`);
  refresh().catch(showError);
}
dateInput.addEventListener("change", () => selectDate(dateInput.value));
$("#previous-day").addEventListener("click", () => selectDate(addDays(dateInput.value, -1)));
$("#next-day").addEventListener("click", () => selectDate(addDays(dateInput.value, 1)));
$("#today-button").addEventListener("click", () => selectDate(localDate()));
$("#jump-food").addEventListener("click", () => {
  $("#meal-items input").focus();
});
$("#food-form").addEventListener("submit", (event) =>
  saveForm(event, async (data) => {
    const items = mealComposer.items(),
      selected = dateInput.value;
    if (items.some((item) => !item.food_name)) throw new Error("Enter a name for every food.");
    const controls = [...$("#food-form").querySelectorAll("input, button, textarea")];
    const disabled = controls.map((control) => control.disabled);
    controls.forEach((control) => {
      control.disabled = true;
    });
    try {
      await api("activity/meals", "POST", {
        meal_name: data.meal_name.trim() || items[0].food_name,
        consumed_on: selected,
        items,
      });
    } finally {
      controls.forEach((control, index) => {
        control.disabled = disabled[index];
      });
    }
    mealComposer.reset();
    $("#meal-items input").focus();
    notify(`Meal saved for ${dateLabel(selected)}.`);
    refresh().catch(showError);
  }),
);
$("#workout-form").addEventListener("submit", (event) =>
  saveForm(event, async (data) => {
    if (!data.workout_name.trim()) throw new Error("Enter a workout name.");
    const selected = dateInput.value;
    const controls = [...$("#workout-form").querySelectorAll("input, select, textarea, button")];
    const disabled = controls.map((control) => control.disabled);
    controls.forEach((control) => {
      control.disabled = true;
    });
    try {
      await api("activity/workouts", "POST", { ...data, performed_on: selected });
    } finally {
      controls.forEach((control, index) => {
        control.disabled = disabled[index];
      });
    }
    $("#workout-form").reset();
    $("#workout-name").focus();
    notify(`Workout saved for ${dateLabel(selected)}.`);
    refresh().catch(showError);
  }),
);
document.addEventListener("fitworld:activity", (event) => {
  dateInput.value = event.detail.date;
  history.replaceState({}, "", `/home?date=${dateInput.value}`);
  refresh().catch(showError);
});

async function loadCatalog() {
  $("#open-workout-log").disabled = true;
  try {
    const data = await api("workouts");
    initWorkoutLogging(data.workouts);
    renderCards($("#home-suggestions"), data.workouts.slice(0, 4));
  } catch {
    sectionError($("#home-suggestions"), "Workout suggestions couldn’t load.", loadCatalog);
  }
}
async function loadRoutine() {
  try {
    const routines = await api(`routines?today=${localDate()}`);
    $("#home-routine").textContent = routines.current
      ? routines.current.is_finished
        ? "Your last plan is complete. Find your next rhythm."
        : `Your rhythm: ${routines.current.name}. Keep showing up for you.`
      : "Your next chapter can start with a single session.";
  } catch {
    sectionError($("#home-routine"), "Your routine couldn’t load.", loadRoutine);
  }
}
async function boot() {
  await session;
  await Promise.all([loadCatalog(), loadRoutine(), refresh()]);
}
boot().catch(showError);

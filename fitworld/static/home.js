// Latest team Home flow: food, free-text workouts, separate totals, and removal.
// Shared modules add persistence, catalog sessions, and personal progress.
import { $, el, api, session, localDate, dateLabel, addDays, number, empty, stat, badge, saveForm, notify, showError } from "./js/client.js";
import { renderWorkouts, renderMeals } from "./js/activity-ui.js";
import { initWorkoutLogging, renderCards, renderSchedule } from "./js/workout-ui.js";

const dateInput = $("#home-date");
dateInput.value = new URLSearchParams(location.search).get("date") || localDate();
if (!dateInput.value) dateInput.value = localDate();
dateInput.max = localDate();
let revision = 0;

async function refresh() {
  const current = ++revision, selected = dateInput.value || localDate();
  const [day, recent, upcoming] = await Promise.all([api(`activity?date=${selected}`), api("activity/recent"), api(`schedule?from=${localDate()}&to=${addDays(localDate(), 6)}`)]);
  if (current !== revision) return;
  const summary = day.summary, stats = $("#today-stats");
  stats.replaceChildren(
    stat("Workouts completed", number(summary.completed), summary.partial ? `${summary.partial} stopped early · ${number(summary.duration_minutes)} min total` : `${number(summary.duration_minutes)} minutes of movement`, true),
    stat("Calories consumed", number(day.nutrition.calories.known_total, 0), "kcal from your food log"),
    stat("Estimated calories burned", summary.workouts_missing_calories === day.workouts.length && day.workouts.length ? "—" : number(summary.estimated_calories_burned, 0), summary.workouts_missing_calories ? "Some workouts have no estimate" : "kcal from your recorded estimates"),
  );
  stats.removeAttribute("aria-busy");
  $("#today-muscles").textContent = summary.muscle_groups.length ? `Muscle groups: ${summary.muscle_groups.join(" · ")}` : "Every starting point is welcome. Choose a workout when you’re ready.";
  $("#food-date-note").textContent = `Saving food for ${dateLabel(selected, { month: "long", day: "numeric", year: "numeric" })}.`;
  $("#calorie-total").textContent = number(day.nutrition.calories.known_total, 0);
  $("#workout-total").textContent = number(summary.duration_minutes);
  renderWorkouts($("#today-workouts"), day); renderMeals($("#food-list"), day); renderSchedule($("#home-schedule"), upcoming.schedule);
  const container = $("#recent-workouts"); container.replaceChildren();
  if (!recent.workouts.length) empty(container, "Your story starts here. Try a workout and your recent movement will appear here.");
  recent.workouts.forEach((workout) => {
    const card = el("a", "recent-card"); card.href = `/progress?month=${workout.performed_on.slice(0, 7)}&date=${workout.performed_on}`;
    card.append(el("h3", "", workout.workout_name), badge(workout.status), el("p", "", `${dateLabel(workout.performed_on)} · ${number(workout.duration_seconds / 60)} min`)); container.append(card);
  });
  $("#page-error").hidden = true;
}

dateInput.addEventListener("change", () => {
  if (!dateInput.value) return;
  history.replaceState({}, "", `/home?date=${dateInput.value}`); refresh().catch(showError);
});
$("#jump-food").addEventListener("click", () => { $("#food-name").focus(); });
$("#food-form").addEventListener("submit", (event) => saveForm(event, async (data) => {
  const name = data.food_name.trim();
  if (!name) throw new Error("Enter a food name.");
  await api("activity/meals", "POST", { meal_name: name, consumed_on: dateInput.value, items: [{ ...data, food_name: name }] });
  $("#food-form").reset(); $("#food-name").focus(); notify("Food saved to your day."); refresh().catch(showError);
}));
$("#workout-form").addEventListener("submit", (event) => saveForm(event, async (data) => {
  if (!data.workout_name.trim()) throw new Error("Enter a workout name.");
  await api("activity/workouts", "POST", { ...data, performed_on: dateInput.value });
  $("#workout-form").reset(); $("#workout-name").focus(); notify("Workout saved to your day."); refresh().catch(showError);
}));
document.addEventListener("fitworld:activity", (event) => {
  dateInput.value = event.detail.date; history.replaceState({}, "", `/home?date=${dateInput.value}`); refresh().catch(showError);
});

async function boot() {
  await session;
  const [workouts, routines] = await Promise.all([api("workouts"), api("routines")]);
  initWorkoutLogging(workouts.workouts); renderCards($("#home-suggestions"), workouts.workouts.slice(0, 4));
  $("#home-routine").textContent = routines.current ? `Your rhythm: ${routines.current.name}. Keep showing up for you.` : "Your next chapter can start with a single session.";
  await refresh();
}
boot().catch(showError);

import { $, el, api, session, localDate, addDays, empty, saveForm, notify, showError, dateLabel } from "./client.js";
import { initWorkoutLogging, renderCards, renderSchedule } from "./workout-ui.js";

let allWorkouts = [], plans = [], active = null, selectedRoutine = null;
const weekdays = ["", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const search = $("#workout-search"); search.value = new URLSearchParams(location.search).get("q") || "";

function render() {
  const query = search.value.trim().toLowerCase();
  const workouts = allWorkouts.filter((item) => [item.name, item.description, ...item.exercises.map((exercise) => exercise.name)].join(" ").toLowerCase().includes(query));
  const groups = {
    recommended: workouts.slice(0, 6), high: workouts.filter((item) => item.intensity >= 6),
    low: workouts.filter((item) => item.intensity <= 4 && !["recovery", "mobility"].includes(item.category)),
    recovery: workouts.filter((item) => ["recovery", "mobility"].includes(item.category)),
  };
  Object.entries(groups).forEach(([key, items]) => renderCards($(`#${key}-cards`), items));
  const container = $("#routine-cards"); container.replaceChildren();
  const routines = plans.filter((plan) => [plan.name, plan.description, ...plan.schedule.map((item) => item.name)].join(" ").toLowerCase().includes(query));
  if (!routines.length) empty(container, "No routines match. Try another term or clear your search.");
  routines.forEach((plan) => {
    const card = el("article", "panel-card routine-card");
    const week = plan.schedule.filter((item) => item.week_number === 1);
    card.append(el("p", "eyebrow", `${plan.experience_level} · ${plan.duration_weeks} weeks`), el("h3", "", plan.name), el("p", "", plan.description));
    const details = el("details"); details.append(el("summary", "", `${week.length} sessions / week · View schedule`));
    const list = el("ul", "row-list"); week.forEach((item) => list.append(el("li", "small list-row", `${weekdays[item.day_of_week]} · ${item.name} · ${item.estimated_minutes} min`))); details.append(list); card.append(details);
    const button = el("button", active?.routine_id === plan.id ? "secondary-button" : "primary-button", active?.routine_id === plan.id ? "Your current routine" : "Choose routine ↗"); button.type = "button";
    button.disabled = active?.routine_id === plan.id;
    button.addEventListener("click", () => {
      selectedRoutine = plan; $("#routine-form").reset(); $("#routine-form .form-error").hidden = true; $("#routine-start").value = localDate();
      $("#choose-routine-description").textContent = `${plan.name} · ${week.length} sessions per week for ${plan.duration_weeks} weeks.`; $("#routine-dialog").showModal();
    });
    card.append(button); container.append(card);
  });
  $("#routine-heading").textContent = active ? active.name : "Let’s find your rhythm.";
  $("#routine-description").textContent = active ? `${active.description} Started ${dateLabel(active.starts_on)}.` : "Your goals and preferences are already saved. Compare a few routines below and choose one that fits your week.";
  $("#change-routine").textContent = active ? "Explore alternative routines ↓" : "Choose a routine ↓";
}

let scheduleRevision = 0;
async function refreshSchedule() {
  const revision = ++scheduleRevision;
  const data = await api(`schedule?from=${localDate()}&to=${addDays(localDate(), Number($("#schedule-range").value) - 1)}`);
  if (revision === scheduleRevision) renderSchedule($("#routine-schedule"), data.schedule);
}
async function refreshPlans() {
  const [workouts, routines] = await Promise.all([api("workouts"), api("routines")]);
  allWorkouts = workouts.workouts; plans = routines.routines; active = routines.current; render(); await refreshSchedule();
}
$("#catalog-search").addEventListener("submit", (event) => { event.preventDefault(); const url = new URL(location.href); url.searchParams.set("q", search.value); history.replaceState({}, "", url); render(); });
search.addEventListener("input", render);
$("#schedule-range").addEventListener("change", () => refreshSchedule().catch(showError));
document.querySelectorAll("[data-scroll]").forEach((button) => button.addEventListener("click", () => document.getElementById(button.dataset.scroll).scrollBy({ left: Number(button.dataset.direction) * 320, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" })));
$("#routine-form").addEventListener("submit", (event) => saveForm(event, async (data) => {
  await api(`routines/${selectedRoutine.id}/select`, "POST", data); $("#routine-dialog").close(); notify("Your routine is saved. Make it your own."); refreshPlans().catch(showError);
}));
document.addEventListener("fitworld:activity", () => refreshSchedule().catch(showError));

async function boot() {
  const { user } = await session;
  const preferences = user.preferences;
  const recap = $("#preference-recap");
  [["Your weekly goal", `${preferences.target_days_per_week} days / week`], ["Time for you", `${preferences.session_minutes} min / session`], ["Your space", { home: "At home", gym: "At the gym", outdoors: "Outdoors" }[preferences.training_location]]].forEach(([label, value]) => { const group = el("div"); group.append(el("span", "", label), el("strong", "", value)); recap.append(group); });
  await refreshPlans(); initWorkoutLogging(allWorkouts);
}
boot().catch(showError);

import {
  $,
  el,
  api,
  session,
  localDate,
  addDays,
  empty,
  saveForm,
  notify,
  showError,
  dateLabel,
} from "./client.js";
import { initWorkoutLogging, renderCards, renderSchedule } from "./workout-ui.js";

let allWorkouts = [],
  allExercises = [],
  plans = [],
  active = null,
  selectedRoutine = null,
  showAllGuides = false;
const weekdays = ["", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const search = $("#workout-search");
search.value = new URLSearchParams(location.search).get("q") || "";

function render() {
  const query = search.value.trim().toLowerCase();
  const workouts = allWorkouts.filter((item) =>
    [item.name, item.description, ...item.exercises.map((exercise) => exercise.name)]
      .join(" ")
      .toLowerCase()
      .includes(query),
  );
  const groups = {
    recommended: workouts.slice(0, 6),
    high: workouts.filter((item) => item.intensity >= 6),
    low: workouts.filter(
      (item) => item.intensity <= 4 && !["recovery", "mobility"].includes(item.category),
    ),
    recovery: workouts.filter((item) => ["recovery", "mobility"].includes(item.category)),
  };
  Object.entries(groups).forEach(([key, items]) => renderCards($(`#${key}-cards`), items));
  const guides = allExercises.filter((item) =>
    [item.name, item.description, item.muscle_group, item.equipment]
      .join(" ")
      .toLowerCase()
      .includes(query),
  );
  const guidesContainer = $("#exercise-guides");
  guidesContainer.replaceChildren();
  const shownGuides = query || showAllGuides ? guides : guides.slice(0, 6);
  shownGuides.forEach((exercise) => {
    const guide = el("article", "panel-card routine-card");
    guide.append(
      el("h3", "", exercise.name),
      el("p", "small muted", `${exercise.muscle_group} · ${exercise.equipment}`),
    );
    const details = el("details");
    details.append(
      el("summary", "", "Movement guide"),
      el("p", "", exercise.description || "No movement notes have been added yet."),
    );
    guide.append(details);
    guidesContainer.append(guide);
  });
  if (!guides.length) empty(guidesContainer, "No exercise guides match this search.");
  $("#show-exercise-guides").hidden = shownGuides.length === guides.length;
  $("#show-exercise-guides").textContent = `Show all ${guides.length} exercise guides`;
  const container = $("#routine-cards");
  container.replaceChildren();
  const routines = plans.filter((plan) =>
    [plan.name, plan.description, ...plan.schedule.map((item) => item.name)]
      .join(" ")
      .toLowerCase()
      .includes(query),
  );
  if (!routines.length)
    empty(container, "No routines match. Try another term or clear your search.");
  routines.forEach((plan) => {
    const card = el("article", "panel-card routine-card");
    const week = plan.schedule.filter((item) => item.week_number === 1);
    card.append(
      el("p", "eyebrow", `${plan.experience_level} · ${plan.duration_weeks} weeks`),
      el("h3", "", plan.name),
      el("p", "", plan.description),
    );
    const details = el("details");
    details.append(el("summary", "", `${week.length} sessions / week · View schedule`));
    const list = el("ul", "row-list");
    week.forEach((item) =>
      list.append(
        el(
          "li",
          "small list-row",
          `${weekdays[item.day_of_week]} · ${item.name} · ${item.estimated_minutes} min`,
        ),
      ),
    );
    details.append(list);
    card.append(details);
    const isCurrent = active?.routine_id === plan.id;
    const button = el(
      "button",
      isCurrent ? "secondary-button" : "primary-button",
      isCurrent ? (active.is_finished ? "Start again ↗" : "Restart routine ↗") : "Choose routine ↗",
    );
    button.type = "button";
    button.addEventListener("click", () => {
      selectedRoutine = plan;
      $("#routine-form").reset();
      $("#routine-form .form-error").hidden = true;
      $("#routine-start").value = localDate();
      $("#choose-routine-description").textContent =
        `${plan.name} · ${week.length} sessions per week for ${plan.duration_weeks} weeks.`;
      $("#routine-dialog").showModal();
    });
    card.append(button);
    container.append(card);
  });
  $("#routine-heading").textContent = active ? active.name : "Let’s find your rhythm.";
  $("#routine-description").textContent = active
    ? `${active.description} ${active.is_finished ? `This plan ended ${dateLabel(active.ends_on)}. Start again whenever you’re ready.` : `Started ${dateLabel(active.starts_on)}.`}`
    : "Your goals and preferences are already saved. Compare a few routines below and choose one that fits your week.";
  $("#change-routine").textContent = active
    ? "Explore alternative routines ↓"
    : "Choose a routine ↓";
}

let scheduleRevision = 0;
async function refreshSchedule() {
  const revision = ++scheduleRevision;
  const data = await api(
    `schedule?from=${localDate()}&to=${addDays(localDate(), Number($("#schedule-range").value) - 1)}`,
  );
  if (revision === scheduleRevision) renderSchedule($("#routine-schedule"), data.schedule);
}
async function refreshPlans() {
  const [workouts, routines, exercises] = await Promise.all([
    api("workouts"),
    api(`routines?today=${localDate()}`),
    api("exercises"),
  ]);
  allWorkouts = workouts.workouts;
  allExercises = exercises.exercises;
  plans = routines.routines;
  active = routines.current;
  render();
  await refreshSchedule();
}
$("#catalog-search").addEventListener("submit", (event) => {
  event.preventDefault();
  const url = new URL(location.href);
  url.searchParams.set("q", search.value);
  history.replaceState({}, "", url);
  render();
});
search.addEventListener("input", render);
$("#show-exercise-guides").addEventListener("click", () => {
  showAllGuides = true;
  render();
});
$("#schedule-range").addEventListener("change", () => refreshSchedule().catch(showError));
document.querySelectorAll("[data-scroll]").forEach((button) =>
  button.addEventListener("click", () =>
    document.getElementById(button.dataset.scroll).scrollBy({
      left: Number(button.dataset.direction) * 320,
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    }),
  ),
);
$("#routine-form").addEventListener("submit", (event) =>
  saveForm(event, async (data) => {
    await api(`routines/${selectedRoutine.id}/select`, "POST", data);
    $("#routine-dialog").close();
    notify("Your routine is saved. Make it your own.");
    refreshPlans().catch(showError);
  }),
);
document.addEventListener("fitworld:activity", () => refreshSchedule().catch(showError));

async function boot() {
  const { user } = await session;
  const preferences = user.preferences;
  const recap = $("#preference-recap");
  [
    ["Your weekly goal", `${preferences.target_days_per_week} days / week`],
    ["Time for you", `${preferences.session_minutes} min / session`],
    [
      "Your space",
      { home: "At home", gym: "At the gym", outdoors: "Outdoors" }[preferences.training_location],
    ],
  ].forEach(([label, value]) => {
    const group = el("div");
    group.append(el("span", "", label), el("strong", "", value));
    recap.append(group);
  });
  await refreshPlans();
  initWorkoutLogging(allWorkouts);
}

// Open/close create exercise dialog
$("#open-create-exercise").addEventListener("click", () => {
  $("#create-exercise-form").reset();
  $("#create-exercise-form .form-error").hidden = true;
  $("#create-exercise-dialog").showModal();
});

// Submit create exercise form
$("#create-exercise-form").addEventListener("submit", (event) =>
  saveForm(event, async (data) => {
    await api("exercises", "POST", data);
    $("#create-exercise-dialog").close();
    notify("Exercise added to your library.");
    refreshPlans().catch(showError);
  }),
);

// Open/close create workout dialog
$("#open-create-workout").addEventListener("click", () => {
  $("#create-workout-form").reset();
  $("#workout-exercises-list").replaceChildren();
  $("#create-workout-form .form-error").hidden = true;
  $("#create-workout-dialog").showModal();
});

// Add exercise row to workout form
$("#add-exercise-row").addEventListener("click", () => {
  const row = el("div", "exercise-row");
  const select = el("select");
  allExercises.forEach((exercise) => {
    const option = document.createElement("option");
    option.value = exercise.id;
    option.textContent = exercise.name;
    select.append(option);
  });
  row.append(
    select,
    Object.assign(el("input"), { type: "number", placeholder: "Sets", min: 1, max: 100 }),
    Object.assign(el("input"), { type: "number", placeholder: "Reps", min: 1, max: 10000 }),
    Object.assign(el("input"), { type: "number", placeholder: "Seconds", min: 1, max: 86400 }),
  );
  $("#workout-exercises-list").append(row);
});

// Submit create workout form
$("#create-workout-form").addEventListener("submit", (event) =>
  saveForm(event, async (data) => {
    const exercises = [...document.querySelectorAll(".exercise-row")].map((row) => {
      const [select, sets, reps, seconds] = row.children;
      return {
        exercise_id: Number(select.value),
        suggested_sets: Number(sets.value),
        suggested_reps: reps.value ? Number(reps.value) : null,
        suggested_seconds: seconds.value ? Number(seconds.value) : null,
      };
    });
    await api("workouts/custom", "POST", { ...data, exercises });
    $("#create-workout-dialog").close();
    notify("Workout saved to your library.");
    refreshPlans().catch(showError);
  }),
);
boot().catch(showError);

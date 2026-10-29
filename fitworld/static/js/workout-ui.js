import { $, el, empty, number, localDate, dateLabel, pounds, saveForm, api, notify, activityChanged, badge } from "./client.js";

let catalog = [], scheduled = null;

export function workoutCard(workout) {
  const button = el("button", "workout-card"); button.type = "button";
  const art = el("img", "workout-art"); art.src = workout.image_path || "/static/art/mixed.svg"; art.alt = ""; art.loading = "lazy";
  const copy = el("span", "workout-copy");
  copy.append(el("span", "workout-category", workout.in_routine ? "Part of your routine" : workout.category), el("strong", "", workout.name));
  const meta = el("span", "workout-meta"); meta.append(el("span", "", `${workout.estimated_minutes} min`), el("span", "", `Intensity ${workout.intensity}/10`)); copy.append(meta); button.append(art, copy);
  button.addEventListener("click", () => showWorkout(workout)); return button;
}

export function renderCards(container, workouts) {
  container.replaceChildren(...workouts.map(workoutCard));
  if (!workouts.length) empty(container, "No workouts match this search. Try a different exercise or clear the search.");
}

export function showWorkout(workout) {
  const content = $("#detail-content"); content.replaceChildren();
  const art = el("img", "detail-art"); art.src = workout.image_path || "/static/art/mixed.svg"; art.alt = "";
  const title = el("h2", "", workout.name); title.id = "detail-title";
  content.append(art, title, el("p", "muted", workout.description), el("p", "badge", `${workout.estimated_minutes} min · Intensity ${workout.intensity}/10`), el("h3", "", "Your workout guide"));
  workout.exercises.forEach((exercise) => {
    const row = el("div", "prescription"); row.append(el("strong", "", exercise.name), el("small", "", `${exercise.suggested_sets} sets · ${exercise.suggested_reps ? `${exercise.suggested_reps} reps` : `${exercise.suggested_seconds} seconds`} · ${exercise.muscle_group}`)); content.append(row);
  });
  $("#detail-log").onclick = () => { $("#workout-detail").close(); openLog(workout.id); };
  $("#workout-detail").showModal();
}

export function openLog(workoutId, date = localDate(), scheduleId = null) {
  const form = $("#workout-log-form"); form.reset(); form.querySelector(".form-error").hidden = true;
  scheduled = scheduleId;
  $("#log-workout").value = workoutId || catalog[0]?.id || "";
  $("#log-workout").disabled = scheduleId !== null;
  $("#performed-on").value = date; $("#performed-on").max = localDate(); $("#performed-on").readOnly = scheduleId !== null;
  renderExerciseFields(); $("#workout-log-dialog").showModal();
}

function renderExerciseFields() {
  const container = $("#exercise-fields"); container.replaceChildren();
  const workout = catalog.find((item) => String(item.id) === $("#log-workout").value);
  if (!workout) return;
  workout.exercises.forEach((exercise) => {
    const fieldset = el("fieldset", "exercise-fields"); fieldset.append(el("legend", "", exercise.name));
    for (let set = 1; set <= exercise.suggested_sets; set++) {
      const row = el("div", "set-fields"); row.dataset.exercise = exercise.exercise_id; row.dataset.set = set;
      row.append(el("span", "small muted", `Set ${set}`));
      const timed = !exercise.suggested_reps;
      [[timed ? "duration_seconds" : "reps", timed ? "Seconds" : "Reps", timed ? 86400 : 10000], ["load", `Load (${pounds ? "lb" : "kg"})`, pounds ? 4409 : 2000]].forEach(([key, label, maximum]) => {
        const group = el("div"); const caption = el("label", "", label); const input = el("input");
        input.type = "number"; input.min = "0"; input.max = maximum; input.step = key === "load" ? "any" : "1";
        input.id = `set-${exercise.exercise_id}-${set}-${key}`; input.dataset.field = key; caption.htmlFor = input.id; group.append(caption, input); row.append(group);
      });
      fieldset.append(row);
    }
    container.append(fieldset);
  });
}

export function initWorkoutLogging(workouts) {
  catalog = workouts;
  const select = $("#log-workout"); select.replaceChildren();
  workouts.forEach((workout) => { const option = el("option", "", workout.name); option.value = workout.id; select.append(option); });
  $("#open-workout-log").disabled = !workouts.length;
  $("#open-workout-log").addEventListener("click", () => openLog());
  select.addEventListener("change", renderExerciseFields);
  $("#workout-log-form").addEventListener("submit", (event) => saveForm(event, async (data) => {
    data.workout_id = select.value; data.scheduled_workout_id = scheduled;
    data.exercises = [];
    document.querySelectorAll("[data-exercise]").forEach((row) => {
      const fields = Object.fromEntries(Array.from(row.querySelectorAll("input")).map((input) => [input.dataset.field, input.value]));
      if (Object.values(fields).every((value) => value === "")) return;
      data.exercises.push({ exercise_id: row.dataset.exercise, set_number: row.dataset.set, reps: fields.reps || null, duration_seconds: fields.duration_seconds || null, load_kg: fields.load === "" ? null : Number(fields.load) * (pounds ? 0.45359237 : 1) });
    });
    await api("activity/workouts", "POST", data); $("#workout-log-dialog").close(); notify("Workout saved. Every bit of movement counts."); activityChanged(data.performed_on);
  }));
}

export function renderSchedule(container, schedule) {
  const visible = schedule.filter((item) => item.status !== "skipped");
  container.replaceChildren();
  if (!visible.length) return empty(container, "No sessions planned in this range. Choose a routine or log a workout at your own pace.");
  const list = el("ul", "row-list");
  visible.forEach((item) => {
    const row = el("li", "list-row"), copy = el("div");
    copy.append(el("strong", "", item.name), el("small", "", `${dateLabel(item.scheduled_on, { weekday: "short", month: "short", day: "numeric" })} · ${item.estimated_minutes} min`)); row.append(copy);
    if (item.status === "planned" && item.scheduled_on <= localDate()) {
      const log = el("button", "secondary-button", "Log session"); log.type = "button"; log.addEventListener("click", () => openLog(item.workout_id, item.scheduled_on, item.id)); row.append(log);
    } else row.append(badge(item.status));
    list.append(row);
  });
  container.append(list);
}

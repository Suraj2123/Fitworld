import { $, el, api, session, localDate, parseDate, dateLabel, addDays, number, mass, pounds, empty, stat, saveForm, notify, showError } from "./client.js";
import { renderWorkouts, renderMeals, renderNutrition } from "./activity-ui.js";

const today = localDate(), picker = $("#month-picker");
const params = new URLSearchParams(location.search);
picker.value = params.get("month") || today.slice(0, 7);
if (!picker.value || picker.value < "1900-01" || picker.value > "2100-12") picker.value = today.slice(0, 7);
let selectedDate = params.get("date") || (picker.value === today.slice(0, 7) ? today : `${picker.value}-01`);
if (!/^\d{4}-\d{2}-\d{2}$/.test(selectedDate) || localDate(parseDate(selectedDate)) !== selectedDate || selectedDate.slice(0, 7) !== picker.value) selectedDate = `${picker.value}-01`;
let monthData, monthRevision = 0, dayRevision = 0;

function updateUrl() {
  const url = new URL(location.href); url.searchParams.set("month", picker.value); url.searchParams.set("date", selectedDate); history.replaceState({}, "", url);
}

function renderCalendar(focus = false) {
  const container = $("#progress-calendar"); container.replaceChildren();
  const offset = (parseDate(monthData.starts_on).getDay() + 6) % 7;
  for (let index = 0; index < offset; index++) container.append(el("span"));
  monthData.days.forEach((day) => {
    const button = el("button", `calendar-day${day.completed || day.partial ? " has-activity" : ""}${day.date === today ? " today" : ""}`);
    button.type = "button"; button.id = `day-${day.date}`; button.dataset.date = day.date;
    button.setAttribute("aria-pressed", String(day.date === selectedDate)); button.tabIndex = day.date === selectedDate ? 0 : -1;
    if (day.date === today) button.setAttribute("aria-current", "date");
    const notes = [day.completed ? `${day.completed} completed` : null, day.partial ? `${day.partial} stopped early` : null].filter(Boolean);
    button.setAttribute("aria-label", `${dateLabel(day.date, { weekday: "long", month: "long", day: "numeric", year: "numeric" })}. ${notes.join(", ") || "No workouts"}. ${day.meals} food entries. ${day.workouts.map((item) => item.name).join(", ")}`);
    const note = el("span", "day-note"); note.setAttribute("aria-hidden", "true");
    note.append(el("span", "day-full-note", notes.join(" · ")), el("span", "day-short-note", [day.completed ? `✓ ${day.completed}` : null, day.partial ? `◐ ${day.partial}` : null].filter(Boolean).join(" · ")));
    button.append(el("span", "day-number", Number(day.date.slice(-2))), note);
    const markers = el("span", "day-markers");
    [[day.completed, "completed-dot"], [day.partial, "partial-dot"], [day.meals, "food-dot"]].forEach(([count, className]) => { if (count) { const dot = el("i", `legend-dot ${className}`); dot.setAttribute("aria-hidden", "true"); markers.append(dot); } });
    button.append(markers);
    button.addEventListener("click", () => selectDay(day.date));
    button.addEventListener("keydown", (event) => {
      const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[event.key];
      let target;
      if (step) target = addDays(day.date, step);
      if (event.key === "Home") target = addDays(day.date, -((parseDate(day.date).getDay() + 6) % 7));
      if (event.key === "End") target = addDays(day.date, 6 - ((parseDate(day.date).getDay() + 6) % 7));
      if (target) { event.preventDefault(); selectDay(target, true); }
    });
    container.append(button);
  });
  container.removeAttribute("aria-busy");
  if (focus) document.getElementById(`day-${selectedDate}`)?.focus();
}

function selectDay(value, focus = false) {
  if (value.slice(0, 7) < "1900-01" || value.slice(0, 7) > "2100-12") return;
  selectedDate = value;
  if (value.slice(0, 7) !== picker.value) { picker.value = value.slice(0, 7); loadMonth(focus).catch(showError); return; }
  updateUrl(); renderCalendar(focus); loadDay().catch(showError);
}

async function loadDay() {
  const revision = ++dayRevision, selected = selectedDate;
  $("#day-heading").textContent = dateLabel(selected, { weekday: "long", month: "long", day: "numeric" });
  $("#day-totals").textContent = "Loading this day…";
  ["#day-workouts", "#day-nutrition", "#day-meals"].forEach((selector) => $(selector).replaceChildren());
  const data = await api(`activity?date=${selected}`);
  if (revision !== dayRevision || selected !== selectedDate) return;
  const summary = data.summary;
  $("#day-totals").textContent = `${number(summary.duration_minutes)} min of movement · ${summary.workouts_missing_calories === data.workouts.length && data.workouts.length ? "Burn not estimated" : `${number(summary.estimated_calories_burned, 0)} kcal burned (estimated)`} · ${number(data.nutrition.calories.known_total, 0)} kcal consumed${summary.workouts_missing_calories && summary.workouts_missing_calories !== data.workouts.length ? " · Some burn estimates missing" : ""}`;
  renderWorkouts($("#day-workouts"), data); renderMeals($("#day-meals"), data); renderNutrition($("#day-nutrition"), data.nutrition);
  $("#day-log-link").href = `/home?date=${selected}`;
  $("#day-log-link").hidden = selected > today;
}

function renderRecords(records) {
  const container = $("#exercise-records"); container.replaceChildren();
  if (!records.length) return empty(container, "Your benchmarks will grow with you. Record actual loads or set durations when you log a completed workout.");
  records.forEach((record) => {
    const card = el("article", `benchmark-card${record.improvement !== null ? " improved" : ""}`);
    const format = (value) => record.metric === "load_kg" ? mass(value) : `${number(value)} sec`;
    card.append(el("span", "workout-category", record.metric === "load_kg" ? "Heaviest recorded load" : "Longest recorded set"), el("h3", "", record.name), el("p", "benchmark-value", format(record.value)));
    card.append(el("p", "small muted", record.improvement !== null ? `↑ ${format(record.improvement)} above your earlier best` : record.previous_best === null ? "Your first recorded benchmark" : `Earlier best: ${format(record.previous_best)}`)); container.append(card);
  });
}

function renderWeight(measurements) {
  const container = $("#weight-history"); container.replaceChildren();
  if (!measurements.length) return empty(container, "No measurements in this part of your story yet.");
  if (measurements.length > 1) {
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg"); svg.setAttribute("viewBox", "0 0 500 160"); svg.classList.add("weight-chart"); svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "Recorded body weight over time. Exact dates and values are in the table below.");
    const values = measurements.map((item) => item.weight_kg), low = Math.min(...values), span = Math.max(...values) - low || 1;
    const first = parseDate(measurements[0].measured_on).getTime(), duration = parseDate(measurements.at(-1).measured_on).getTime() - first || 1;
    const points = measurements.map((item) => [20 + (parseDate(item.measured_on).getTime() - first) / duration * 460, 125 - (item.weight_kg - low) / span * 100]);
    const path = document.createElementNS(namespace, "path"); path.setAttribute("d", points.map(([x, y], index) => `${index ? "L" : "M"}${x},${y}`).join(" ")); path.classList.add("chart-line"); svg.append(path);
    points.forEach(([x, y], index) => { const circle = document.createElementNS(namespace, "circle"); circle.setAttribute("cx", x); circle.setAttribute("cy", y); circle.setAttribute("r", "4"); circle.classList.add("chart-point"); const title = document.createElementNS(namespace, "title"); title.textContent = `${measurements[index].measured_on}: ${mass(measurements[index].weight_kg)}`; circle.append(title); svg.append(circle); });
    container.append(svg);
  }
  const details = el("details"); details.append(el("summary", "", `${measurements.length} recorded check-ins · View exact values`));
  const table = el("table"); const caption = el("caption", "sr-only", "Recorded body measurements"); const header = el("tr"); header.append(el("th", "", "Date"), el("th", "", "Weight")); const head = el("thead"); head.append(header); const body = el("tbody");
  measurements.toReversed().forEach((item) => { const row = el("tr"); row.append(el("td", "", dateLabel(item.measured_on, { month: "short", day: "numeric", year: "numeric" })), el("td", "", mass(item.weight_kg))); body.append(row); }); table.append(caption, head, body); details.append(table); container.append(details);
}

async function loadMonth(focus = false) {
  const revision = ++monthRevision, month = picker.value;
  $("#progress-calendar").setAttribute("aria-busy", "true");
  const data = await api(`progress?month=${month}&today=${today}`);
  if (revision !== monthRevision || month !== picker.value) return;
  monthData = data; updateUrl();
  $("#month-title").textContent = dateLabel(data.starts_on, { month: "long", year: "numeric" });
  $("#previous-month").disabled = month === "1900-01"; $("#next-month").disabled = month === "2100-12";
  const summary = data.summary, improvements = data.records.filter((item) => item.improvement !== null).length;
  $("#progress-stats").replaceChildren(stat("Workouts completed", number(summary.completed_workouts), `${summary.partial_workouts} stopped early · each effort counts`, true), stat("Average per week", number(summary.average_per_week), summary.average_window === "month_to_date" ? "Completed workouts · month to date" : "Completed workouts · full month"), stat("Personal improvements", number(improvements), "New load or duration benchmarks"));
  $("#progress-stats").removeAttribute("aria-busy");
  $("#average-explanation").textContent = `${number(summary.duration_minutes)} minutes of movement over ${summary.active_days} active ${summary.active_days === 1 ? "day" : "days"}. Weekly average = completed workouts × 7 ÷ ${summary.average_window_days} calendar days.`;
  renderCalendar(focus); renderRecords(data.records); renderWeight(data.measurements);
  const milestones = $("#milestones"); milestones.replaceChildren();
  if (!data.milestones.length) empty(milestones, "Keep making room for movement. Saved milestones for this month will appear here.");
  data.milestones.forEach((item) => { const card = el("article", "entry-card"); card.append(el("h3", "", item.title), el("p", "small muted", dateLabel(item.achieved_on)), el("p", "", item.description)); milestones.append(card); });
  $("#page-error").hidden = true;
  await loadDay();
}

function changeMonth(value) {
  picker.value = value; selectedDate = value === today.slice(0, 7) ? today : `${value}-01`; loadMonth().catch(showError);
}
function shiftMonth(amount) { const date = parseDate(`${picker.value}-01`); date.setMonth(date.getMonth() + amount); changeMonth(localDate(date).slice(0, 7)); }
$("#previous-month").addEventListener("click", () => shiftMonth(-1));
$("#next-month").addEventListener("click", () => shiftMonth(1));
$("#current-month").addEventListener("click", () => changeMonth(today.slice(0, 7)));
picker.addEventListener("change", () => { if (picker.validity.valid && picker.value) changeMonth(picker.value); });
document.addEventListener("fitworld:activity", () => loadMonth().catch(showError));

let measurementUnit = pounds ? "imperial" : "metric";
function weightLimits() { const imperial = $("#measurement-unit").value === "imperial"; $("#measurement-weight").min = imperial ? "44.1" : "20"; $("#measurement-weight").max = imperial ? "881.8" : "400"; }
$("#record-weight").addEventListener("click", () => {
  $("#weight-form").reset(); $("#weight-form .form-error").hidden = true;
  $("#measured-on").value = today; $("#measured-on").max = today;
  measurementUnit = pounds ? "imperial" : "metric"; $("#measurement-unit").value = measurementUnit; weightLimits(); $("#weight-dialog").showModal();
});
$("#measurement-unit").addEventListener("change", () => {
  const next = $("#measurement-unit").value, weight = $("#measurement-weight");
  if (weight.value && next !== measurementUnit) weight.value = (Number(weight.value) * (next === "imperial" ? 1 / 0.45359237 : 0.45359237)).toFixed(1);
  measurementUnit = next; weightLimits();
});
$("#weight-form").addEventListener("submit", (event) => saveForm(event, async (data) => {
  await api("progress/measurements", "POST", data); $("#weight-dialog").close(); notify("Your check-in is saved."); selectedDate = data.measured_on; picker.value = selectedDate.slice(0, 7); loadMonth().catch(showError);
}));
session.then(() => loadMonth()).catch(showError);

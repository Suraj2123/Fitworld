"use strict";

const $ = (selector) => document.querySelector(selector);
const stages = ["account", "baseline", "rhythm", "review", "ready"];
const state = { user: null, csrf: "", login: false, busy: false, unit: "metric", stage: 0 };
const goals = { get_active: "Get more active", build_strength: "Build strength", improve_endurance: "Go the distance", improve_mobility: "Move more freely" };
const levels = { beginner: "Finding my feet", intermediate: "Building momentum", advanced: "Raising the bar" };
const locations = { home: "At home", gym: "At the gym", outdoors: "Outdoors" };

async function api(path, method = "GET", data) {
  const response = await fetch(`/api/${path}`, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrf },
    body: data === undefined ? undefined : JSON.stringify(data),
    signal: AbortSignal.timeout(15000),
  });
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error || "Something went wrong. Please try again.");
    error.fields = result.fields || {};
    error.status = response.status;
    throw error;
  }
  if (result.csrf_token) state.csrf = result.csrf_token;
  if (Object.hasOwn(result, "user")) state.user = result.user;
  return result;
}

function highestStage() {
  if (!state.user) return 0;
  if (state.user.onboarding_completed_at) return 4;
  if (state.user.preferences && state.user.profile) return 3;
  if (state.user.profile) return 2;
  return 1;
}

function navigate(stage, replace = false, focus = true) {
  if (state.busy) return;
  const max = highestStage();
  if (!Number.isInteger(stage)) stage = max;
  if (stage > max || stage < 0 || (state.user && stage === 0)) stage = max;
  state.stage = stage;
  const hash = `#${stages[stage]}`;
  if (window.location.hash !== hash) {
    window.history[replace ? "replaceState" : "pushState"]({}, "", hash);
  }
  document.querySelectorAll(".panel").forEach((panel, index) => { panel.hidden = index !== stage; });
  document.querySelectorAll("[data-step]").forEach((button) => {
    const index = Number(button.dataset.step);
    const done = index < max || (index === 3 && max === 4);
    button.disabled = index > max || (index === 0 && Boolean(state.user));
    button.classList.toggle("done", done);
    button.querySelector(".step-number").textContent = done ? "✓" : String(index + 1);
    if (index === Math.min(stage, 3)) button.setAttribute("aria-current", "step");
    else button.removeAttribute("aria-current");
  });
  $("#account-toggle").hidden = Boolean(state.user);
  $("#signout").hidden = !state.user;
  if (stage >= 3) fillSummary(stage === 4 ? "ready" : "review");
  if (stage === 4) $("#ready-name").textContent = state.user.display_name;
  const heading = $(".panel:not([hidden]) h2").innerText.replace(/\s+/g, " ");
  document.title = `${stage === 4 ? "Your starting point" : stages[stage] === "account" ? (state.login ? "Sign in" : "Get started") : heading} · Fitworld`;
  if (focus) $(".panel:not([hidden]) h2").focus({ preventScroll: false });
}

function fillForms() {
  const profile = state.user?.profile;
  const preferences = state.user?.preferences;
  $("#baseline-form").reset();
  $("#rhythm-form").reset();
  state.unit = "metric";
  if (profile) {
    state.unit = profile.unit_system;
    $("#age").value = profile.age;
    $("#unit_system").value = profile.unit_system;
    $("#weight").value = displayedWeight(profile);
    $("#current_workouts_per_week").value = profile.current_workouts_per_week;
    $(`input[name="experience_level"][value="${profile.experience_level}"]`).checked = true;
  }
  if (preferences) {
    $(`input[name="primary_goal"][value="${preferences.primary_goal}"]`).checked = true;
    $(`input[name="training_location"][value="${preferences.training_location}"]`).checked = true;
    $("#target_days_per_week").value = preferences.target_days_per_week;
    $("#session_minutes").value = preferences.session_minutes;
  }
  updateWeightLimits();
}

function displayedWeight(profile) {
  return Number((profile.unit_system === "imperial" ? profile.weight_kg / 0.45359237 : profile.weight_kg).toFixed(1));
}

function fillSummary(prefix) {
  const { profile, preferences } = state.user;
  const container = $(`#${prefix}-summary`);
  container.replaceChildren();
  const top = document.createElement("div");
  top.className = "summary-top";
  const kicker = document.createElement("span");
  kicker.className = "summary-kicker";
  kicker.textContent = "Your next chapter";
  const goal = document.createElement("p");
  goal.className = "summary-goal";
  goal.textContent = goals[preferences.primary_goal];
  top.append(kicker, goal);
  const list = document.createElement("dl");
  const details = [
    ["Your baseline", `${profile.age} years · ${displayedWeight(profile)} ${profile.unit_system === "imperial" ? "lb" : "kg"}`],
    ["Experience", levels[profile.experience_level]],
    ["Current pace", `${profile.current_workouts_per_week} workouts / week`],
    ["Weekly goal", `${preferences.target_days_per_week} ${preferences.target_days_per_week === 1 ? "day" : "days"} / week`],
    ["Workout space", locations[preferences.training_location]],
    ["Time for you", `${preferences.session_minutes} minutes / workout`],
  ];
  details.forEach(([label, value]) => {
    const group = document.createElement("div");
    const term = document.createElement("dt");
    const definition = document.createElement("dd");
    term.textContent = label;
    definition.textContent = value;
    group.append(term, definition);
    list.append(group);
  });
  container.append(top, list);
}

function clearErrors(form) {
  form.querySelectorAll("[aria-invalid]").forEach((field) => field.removeAttribute("aria-invalid"));
  form.querySelectorAll(".field-error").forEach((field) => { field.textContent = ""; });
  const summary = form.querySelector(".error-summary");
  summary.hidden = true;
  summary.replaceChildren();
}

function showErrors(form, error) {
  clearErrors(form);
  const summary = form.querySelector(".error-summary");
  const message = document.createElement("p");
  message.textContent = error.status === 401 && state.user ? "Your session ended. Reload the page to sign in again." : error.message;
  summary.append(message);
  const list = document.createElement("ul");
  Object.entries(error.fields || {}).forEach(([key, text]) => {
    const control = form.elements.namedItem(key);
    if (!control) return;
    const controls = control instanceof RadioNodeList ? Array.from(control) : [control];
    controls.forEach((input) => input.setAttribute("aria-invalid", "true"));
    const fieldError = document.getElementById(`${key}-error`);
    if (fieldError) fieldError.textContent = text;
    const first = controls[0];
    if (!first.id) first.id = `${key}-first`;
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = `#${first.id}`;
    link.textContent = text;
    link.addEventListener("click", (event) => { event.preventDefault(); first.focus(); });
    item.append(link);
    list.append(item);
  });
  if (list.children.length) summary.append(list);
  summary.hidden = false;
  summary.focus();
}

function checkForm(form) {
  const fields = {};
  Array.from(form.elements).forEach((input) => {
    if (input.name && input.willValidate && !input.validity.valid) fields[input.name] = input.validationMessage;
  });
  if (Object.keys(fields).length) {
    showErrors(form, { message: "Check these details before continuing.", fields });
    return false;
  }
  return true;
}

async function submitStep(event, path, method, next) {
  event.preventDefault();
  if (state.busy) return;
  const form = event.currentTarget;
  clearErrors(form);
  if (!checkForm(form)) return;
  const button = form.querySelector('button[type="submit"]');
  const original = button.innerHTML;
  state.busy = true;
  button.disabled = true;
  button.textContent = "Saving your details…";
  form.setAttribute("aria-busy", "true");
  let succeeded = false;
  try {
    const data = Object.fromEntries(new FormData(form));
    await api(path, method, data);
    succeeded = true;
    $("#status").textContent = "Your details have been saved.";
    if (form.id === "account-form") {
      $("#password").value = "";
      fillForms();
    }
  } catch (error) {
    if (error.name === "TimeoutError" || error instanceof TypeError) {
      error.message = "We couldn’t confirm the save. Check your connection, then try again. If you just created an account, you can also sign in.";
    }
    showErrors(form, error);
  } finally {
    state.busy = false;
    button.disabled = false;
    button.innerHTML = original;
    form.removeAttribute("aria-busy");
  }
  if (succeeded && form.id === "account-form" && state.login && state.user?.onboarding_completed_at) window.location.assign("/home");
  else if (succeeded) navigate(next);
}

function updateWeightLimits() {
  const pounds = $("#unit_system").value === "imperial";
  $("#weight").min = pounds ? "44.1" : "20";
  $("#weight").max = pounds ? "881.8" : "400";
  $("#weight").placeholder = pounds ? "e.g. 154" : "e.g. 70";
}

$("#unit_system").addEventListener("change", () => {
  const weight = $("#weight");
  const next = $("#unit_system").value;
  if (weight.value && state.unit !== next && Number.isFinite(Number(weight.value))) {
    weight.value = (Number(weight.value) * (next === "imperial" ? 1 / 0.45359237 : 0.45359237)).toFixed(1);
  }
  state.unit = next;
  updateWeightLimits();
});

$("#password-toggle").addEventListener("click", () => {
  const visible = $("#password").type === "password";
  $("#password").type = visible ? "text" : "password";
  $("#password-toggle").textContent = visible ? "Hide" : "Show";
  $("#password-toggle").setAttribute("aria-label", visible ? "Hide password" : "Show password");
  $("#password-toggle").setAttribute("aria-pressed", String(visible));
});

$("#account-toggle").addEventListener("click", () => {
  if (state.busy) return;
  state.login = !state.login;
  $("#name-field").hidden = state.login;
  $("#display_name").disabled = state.login;
  $("#password").minLength = state.login ? 1 : 8;
  $("#password").autocomplete = state.login ? "current-password" : "new-password";
  $("#password-hint").hidden = state.login;
  $("#account-title").textContent = state.login ? "Good to have you back." : "A fresh start. A stronger you.";
  $("#account-intro").textContent = state.login ? "Sign in to pick up where you left off." : "Create your account, then we’ll find a starting point that feels right for you.";
  $("#account-submit").textContent = state.login ? "Sign in →" : "Create account ↗";
  $("#account-toggle").textContent = state.login ? "New here? Create an account ↗" : "Already a member? Sign in ↗";
  clearErrors($("#account-form"));
  navigate(0, true);
});

$("#account-form").addEventListener("submit", (event) => submitStep(event, state.login ? "login" : "register", "POST", state.login ? undefined : 1));
$("#baseline-form").addEventListener("submit", (event) => submitStep(event, "onboarding/profile", "PUT", 2));
$("#rhythm-form").addEventListener("submit", (event) => submitStep(event, "onboarding/preferences", "PUT", 3));
$("#review-form").addEventListener("submit", (event) => submitStep(event, "onboarding/complete", "POST", 4));

document.querySelectorAll("[data-go], [data-step]").forEach((button) => {
  button.addEventListener("click", () => navigate(Number(button.dataset.go ?? button.dataset.step)));
});

window.addEventListener("hashchange", () => {
  const requested = stages.indexOf(window.location.hash.slice(1));
  navigate(requested < 0 ? highestStage() : requested, true);
});

$("#signout").addEventListener("click", async () => {
  if (state.busy) return;
  const button = $("#signout");
  button.disabled = true;
  state.busy = true;
  try {
    await api("logout", "POST", {});
    window.location.replace("/");
  } catch (error) {
    button.textContent = "Couldn’t sign out. Try again ↗";
    $("#status").textContent = error.message;
  } finally {
    state.busy = false;
    button.disabled = false;
  }
});

async function boot() {
  try {
    await api("session");
    fillForms();
    $("#setup").hidden = false;
    if (!state.user && new URLSearchParams(location.search).get("login") === "1") $("#account-toggle").click();
    const requested = stages.indexOf(window.location.hash.slice(1));
    navigate(requested < 0 ? highestStage() : requested, true, false);
    $("#boot").hidden = true;
  } catch {
    $("#boot").textContent = "We couldn’t load your starting point. Check your connection and reload to try again.";
    const retry = document.createElement("button");
    retry.className = "text-button";
    retry.type = "button";
    retry.textContent = "Try again ↗";
    retry.addEventListener("click", () => window.location.reload());
    $("#boot").append(retry);
  }
}

boot();

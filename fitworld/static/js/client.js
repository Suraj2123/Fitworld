// Shared browser interface: HTTP, dates, safe DOM creation, and form feedback.
let csrf = "";
export const $ = (selector) => document.querySelector(selector);
export const number = (value, digits = 1) => Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
export const localDate = (date = new Date()) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
export const parseDate = (value) => new Date(`${value}T12:00:00`);
export const dateLabel = (value, options = { month: "short", day: "numeric" }) => parseDate(value).toLocaleDateString(undefined, options);
export function addDays(value, days) { const date = parseDate(value); date.setDate(date.getDate() + days); return localDate(date); }
export const pounds = document.body.dataset.units === "imperial";
export const mass = (kg) => `${number(pounds ? kg / 0.45359237 : kg)} ${pounds ? "lb" : "kg"}`;

export function el(tag, className = "", text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export async function api(path, method = "GET", data) {
  const response = await fetch(`/api/${path}`, {
    method, credentials: "same-origin", signal: AbortSignal.timeout(15000),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401) window.location.assign("/?login=1");
    const error = new Error(result.error || "The request could not be completed.");
    error.fields = result.fields || {};
    throw error;
  }
  if (result.csrf_token) csrf = result.csrf_token;
  return result;
}
export const session = api("session");

export function empty(container, message) { container.replaceChildren(el("div", "empty-state", message)); }
export function showError(error, target = $("#page-error"), form) {
  target.replaceChildren(el("strong", "", error.name === "TimeoutError" || error instanceof TypeError ? "We couldn’t confirm the request. Check your connection and refresh before trying the save again." : error.message));
  if (Object.keys(error.fields || {}).length) {
    const list = el("ul");
    Object.entries(error.fields).forEach(([name, message]) => {
      const item = el("li");
      const control = form?.elements.namedItem(name);
      if (control?.id) {
        const link = el("a", "", message); link.href = `#${control.id}`;
        link.addEventListener("click", (event) => { event.preventDefault(); control.closest("details")?.setAttribute("open", ""); control.focus(); });
        item.append(link);
      } else item.textContent = message;
      list.append(item);
    });
    target.append(list);
  }
  target.hidden = false;
  target.focus();
}

export async function saveForm(event, save) {
  event.preventDefault();
  const form = event.currentTarget;
  if (form.dataset.busy === "true") return;
  const button = form.querySelector('[type="submit"]');
  const error = form.querySelector(".form-error");
  const original = button.textContent;
  error.hidden = true; form.dataset.busy = "true"; form.setAttribute("aria-busy", "true"); button.disabled = true; button.textContent = "Saving…";
  try { await save(Object.fromEntries(new FormData(form))); }
  catch (problem) { showError(problem, error, form); }
  finally { button.disabled = false; button.textContent = original; form.removeAttribute("aria-busy"); form.dataset.busy = "false"; }
}

let notification;
export function notify(message) {
  const status = $("#app-status"); status.textContent = message; status.hidden = false;
  clearTimeout(notification); notification = setTimeout(() => { status.hidden = true; }, 5000);
}
export function activityChanged(date) { document.dispatchEvent(new CustomEvent("fitworld:activity", { detail: { date } })); }
export function stat(label, value, note, featured = false) {
  const card = el("div", `stat-card${featured ? " featured" : ""}`);
  card.append(el("span", "stat-label", label), el("strong", "stat-value", value), el("span", "stat-note", note));
  return card;
}
export function badge(status) { return el("span", `badge ${status}`, { completed: "✓ Completed", partial: "◐ Stopped early", planned: "Planned", skipped: "Skipped" }[status] || status); }
export async function removeEntry(kind, id, date, focusTarget) {
  const dialog = $("#delete-dialog"); dialog.returnValue = "cancel";
  const confirmed = new Promise((resolve) => dialog.addEventListener("close", () => resolve(dialog.returnValue === "remove"), { once: true }));
  dialog.showModal();
  if (!await confirmed) return;
  try { await api(`activity/${kind}/${id}`, "DELETE"); notify("Entry removed."); activityChanged(date); if (focusTarget) $(focusTarget)?.focus(); }
  catch (error) { showError(error); }
}

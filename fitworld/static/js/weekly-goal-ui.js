// Both pages render the same server-calculated workout days and target comparison.
import { el, dateLabel, number } from "./client.js";

const dayCount = (count) => `${number(count, 0)} ${count === 1 ? "day" : "days"}`;
const weekLabel = (week) =>
  `${dateLabel(week.starts_on, { month: "short", day: "numeric", year: "numeric" })} – ${dateLabel(week.ends_on, { month: "short", day: "numeric", year: "numeric" })}`;
const progressLink = (date) => `/progress?month=${date.slice(0, 7)}&date=${date}`;

export function weeklyGoalLoading(container) {
  container.setAttribute("aria-busy", "true");
  container.replaceChildren(el("p", "muted", "Loading your weekly progress…"));
}

export function weeklyGoalError(container) {
  container.replaceChildren(
    el("p", "muted", "Weekly progress couldn’t load. Refresh the page to try again."),
  );
  container.removeAttribute("aria-busy");
}

export function renderWeeklyGoal(container, data, { showHistory = false } = {}) {
  const { week, target_days: target } = data;
  const layout = el("div", "weekly-goal-layout");
  const overview = el("div");
  overview.append(
    el(
      "p",
      "small muted",
      `${{ current: "This week", past: "Selected week", future: "Upcoming week" }[week.period]} · ${weekLabel(week)}`,
    ),
    el("strong", "weekly-goal-count", `${number(week.completed_days, 0)} of ${number(target, 0)}`),
    el("p", "weekly-goal-caption", "workout days completed"),
  );
  const progress = el("progress", "weekly-goal-meter");
  progress.max = target;
  progress.value = Math.min(week.completed_days, target);
  progress.setAttribute("aria-label", "Weekly workout-day goal");
  progress.setAttribute(
    "aria-valuetext",
    `${week.completed_days} of ${target} workout days completed`,
  );
  progress.textContent = `${week.completed_days} of ${target}`;
  overview.append(progress);
  const message = week.goal_met
    ? "You reached your current target for this week."
    : week.period === "future"
      ? "This week is ahead of you. Progress appears as you log completed workouts."
      : week.period === "past"
        ? `${dayCount(week.completed_days)} recorded against your current ${target}-day target.`
        : `${dayCount(week.remaining_days)} to reach your target this week.`;
  overview.append(el("p", "small weekly-goal-message", message));

  const daily = el("div");
  const days = el("ol", "weekly-goal-days");
  days.setAttribute("aria-label", "Workout days in the selected week");
  week.days.forEach((day) => {
    const status = day.completed_workouts
      ? "completed"
      : day.partial_workouts
        ? "partial"
        : day.is_future
          ? "future"
          : "empty";
    const label = `${dateLabel(day.date, { weekday: "long", month: "long", day: "numeric", year: "numeric" })}: ${day.is_future ? "Upcoming" : `${day.completed_workouts} completed ${day.completed_workouts === 1 ? "workout" : "workouts"}, ${day.partial_workouts} stopped early`}`;
    const link = el(day.is_supported_date ? "a" : "span", `weekly-goal-day ${status}`);
    if (day.is_supported_date) link.href = progressLink(day.date);
    link.setAttribute("aria-label", label);
    if (day.date === data.as_of) link.setAttribute("aria-current", "date");
    [
      ["weekly-goal-weekday", dateLabel(day.date, { weekday: "short" })],
      ["weekly-goal-date", Number(day.date.slice(-2))],
      ["weekly-goal-marker", { completed: "✓", partial: "◐", future: "…", empty: "—" }[status]],
    ].forEach(([className, text]) => {
      const part = el("span", className, text);
      part.setAttribute("aria-hidden", "true");
      link.append(part);
    });
    const item = el("li");
    item.append(link);
    days.append(item);
  });
  daily.append(
    days,
    el(
      "p",
      "small muted weekly-goal-legend",
      "✓ Completed · ◐ Stopped early · — No workout · … Upcoming",
    ),
    el("p", "small muted", "Choose a day to see its activity."),
  );
  layout.append(overview, daily);
  container.replaceChildren(layout);

  if (showHistory) {
    const history = el("details", "weekly-goal-history");
    history.open = true;
    history.append(el("summary", "", "Previous four weeks"));
    history.append(
      el("p", "small muted", `All weeks are compared with your current ${target}-day target.`),
    );
    const list = el("ul");
    data.history.forEach((earlier) => {
      const item = el("li");
      const link = el("a", "text-link", weekLabel(earlier));
      link.href = progressLink(earlier.starts_on);
      item.append(
        link,
        el("span", "small", `${dayCount(earlier.completed_days)} completed`),
        el(
          "span",
          `badge${earlier.goal_met ? " completed" : ""}`,
          earlier.period === "future"
            ? "Upcoming"
            : earlier.goal_met
              ? "Goal reached"
              : earlier.period === "current"
                ? "In progress"
                : `${dayCount(earlier.remaining_days)} below target`,
        ),
      );
      list.append(item);
    });
    if (!data.history.length)
      list.append(el("li", "small muted", "No earlier weeks in this date range."));
    history.append(list);
    container.append(history);
  }
  container.removeAttribute("aria-busy");
}

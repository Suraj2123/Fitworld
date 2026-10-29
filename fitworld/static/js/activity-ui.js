import { el, empty, number, mass, badge, removeEntry } from "./client.js";

export function renderWorkouts(container, data) {
  container.replaceChildren();
  if (!data.workouts.length) return empty(container, "A fresh page. Log your first workout whenever you’re ready.");
  data.workouts.forEach((workout) => {
    const card = el("article", "entry-card");
    const heading = el("div", "entry-heading"); heading.append(el("h3", "", workout.workout_name), badge(workout.status));
    card.append(heading, el("p", "muted", `${number(workout.duration_seconds / 60)} min · ${workout.estimated_calories === null ? "Calories not estimated" : `${number(workout.estimated_calories)} kcal estimated`}`));
    if (workout.muscle_groups.length) card.append(el("p", "small muted", workout.muscle_groups.join(" · ")));
    if (workout.notes) card.append(el("p", "", workout.notes));
    if (workout.exercises.length) {
      const details = el("details"); details.append(el("summary", "", "Recorded exercise sets"));
      const list = el("ul");
      workout.exercises.forEach((set) => list.append(el("li", "", `${set.exercise_name} · set ${set.set_number}: ${[set.reps === null ? null : `${set.reps} reps`, set.duration_seconds === null ? null : `${set.duration_seconds} sec`, set.load_kg === null ? null : mass(set.load_kg)].filter(Boolean).join(" · ")}`)));
      details.append(list); card.append(details);
    }
    const remove = el("button", "text-button remove-entry", "Remove workout"); remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${workout.workout_name}, ${number(workout.duration_seconds / 60)} min`);
    remove.addEventListener("click", () => removeEntry("workouts", workout.id, data.date, document.body.dataset.page === "home" ? "#workout-name" : "#day-heading")); card.append(remove); container.append(card);
  });
}

export function renderMeals(container, data) {
  container.replaceChildren();
  if (!data.meals.length) return empty(container, "No food logged for this day yet.");
  data.meals.forEach((meal) => {
    const card = el("article", "entry-card"); const heading = el("div", "entry-heading");
    heading.append(el("h3", "", meal.meal_name), el("span", "badge", `${number(meal.calories)} kcal`)); card.append(heading);
    meal.items.forEach((item) => {
      card.append(el("p", "muted", `${item.food_name} · ${number(item.servings)} × ${item.serving_description}`));
      const parts = [["protein_g_per_serving", "g protein"], ["carbs_g_per_serving", "g carbs"], ["fat_g_per_serving", "g fat"], ["sodium_mg_per_serving", "mg sodium"]].map(([key, unit]) => item[key] === null ? `${unit.split(" ")[1]} unknown` : `${number(item.servings * item[key])} ${unit}`);
      card.append(el("p", "small muted", parts.join(" · ")));
    });
    const remove = el("button", "text-button remove-entry", "Remove food entry"); remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${meal.meal_name}, ${number(meal.calories)} kcal`);
    remove.addEventListener("click", () => removeEntry("meals", meal.id, data.date, document.body.dataset.page === "home" ? "#food-name" : "#day-heading")); card.append(remove); container.append(card);
  });
}

export function renderNutrition(container, nutrition) {
  container.replaceChildren();
  [["protein_g", "Protein", "g"], ["carbs_g", "Carbs", "g"], ["fat_g", "Fat", "g"], ["sodium_mg", "Sodium", "mg"]].forEach(([key, label, unit]) => {
    const nutrient = nutrition[key]; const item = el("div");
    item.append(el("strong", "", `${number(nutrient.known_total)} ${unit}`), el("span", "", `${label}${nutrient.missing_items ? " · partial total" : ""}`));
    if (nutrient.missing_items) item.title = `${nutrient.missing_items} food item(s) have unknown ${label.toLowerCase()}.`;
    container.append(item);
  });
}

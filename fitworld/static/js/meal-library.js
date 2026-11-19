import { $, api, el, empty, notify, showError } from "./client.js";

export function initMealLibrary(composer) {
  let revision = 0,
    favoriteRevision = 0;
  async function recent() {
    const current = ++revision;
    const container = $("#recent-foods");
    try {
      const { foods } = await api("foods/recent");
      if (current !== revision) return;
      container.replaceChildren();
      if (!foods.length) empty(container, "Foods you log will appear here for quick reuse.");
      foods.forEach((food) => {
        const button = el(
          "button",
          "secondary-button",
          `${food.food_name} · ${food.serving_description}`,
        );
        button.type = "button";
        button.addEventListener("click", () => composer.addFood(food));
        container.append(button);
      });
    } catch {
      if (current !== revision) return;
      empty(container, "Recent foods couldn’t load.");
      const retry = el("button", "text-button", "Retry recent foods");
      retry.type = "button";
      retry.addEventListener("click", recent);
      container.append(retry);
    }
  }
  async function favorites() {
    const current = ++favoriteRevision;
    const container = $("#favorite-meals");
    try {
      const { meals } = await api("meals/favorites");
      if (current !== favoriteRevision) return;
      container.replaceChildren();
      if (!meals.length)
        empty(container, "Choose Favorite meal on a saved entry to keep a reusable template.");
      meals.forEach((meal) => {
        const row = el("div", "entry-card");
        const use = el("button", "secondary-button", `Use ${meal.meal_name}`);
        use.type = "button";
        use.addEventListener("click", () => composer.reuse(meal));
        const remove = el("button", "text-button", `Remove favorite ${meal.meal_name}`);
        remove.type = "button";
        remove.addEventListener("click", async () => {
          const dialog = $("#delete-dialog");
          dialog.returnValue = "cancel";
          const confirmed = new Promise((resolve) =>
            dialog.addEventListener("close", () => resolve(dialog.returnValue === "remove"), {
              once: true,
            }),
          );
          dialog.showModal();
          if (!(await confirmed)) return;
          remove.disabled = true;
          try {
            await api(`meals/favorites/${meal.id}`, "DELETE");
            await favorites();
            notify("Favorite removed. Saved daily meals are unchanged.");
          } catch (error) {
            showError(error);
            remove.disabled = false;
          }
        });
        row.append(use, remove);
        container.append(row);
      });
    } catch {
      if (current !== favoriteRevision) return;
      empty(container, "Favorite meals couldn’t load.");
      const retry = el("button", "text-button", "Retry favorites");
      retry.type = "button";
      retry.addEventListener("click", favorites);
      container.append(retry);
    }
  }
  return {
    refresh: () => Promise.all([recent(), favorites()]),
    async favorite(meal) {
      try {
        await api("meals/favorites", "POST", { meal_id: meal.id });
        await favorites();
        notify("Favorite saved. Reuse it from Favorite meals.");
      } catch (error) {
        showError(error);
      }
    },
  };
}

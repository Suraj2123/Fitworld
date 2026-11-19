import { $, api, el, empty } from "./client.js";

export function initMealLibrary(composer) {
  let revision = 0;
  async function refresh() {
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
      retry.addEventListener("click", refresh);
      container.append(retry);
    }
  }
  return { refresh };
}

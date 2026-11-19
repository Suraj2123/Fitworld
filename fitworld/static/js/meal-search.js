import { $, api, empty, showError } from "./client.js";
import { renderMeals } from "./activity-ui.js";

export function initMealSearch(composer, library) {
  const form = $("#meal-search-form"),
    results = $("#meal-search-results");
  let page = 1,
    revision = 0,
    filters = new URLSearchParams();
  async function refresh() {
    const current = ++revision;
    const params = new URLSearchParams(filters);
    params.set("page", page);
    results.setAttribute("aria-busy", "true");
    $("#meal-search-previous").disabled = true;
    $("#meal-search-next").disabled = true;
    form.querySelector(".form-error").hidden = true;
    empty(results, "Searching meals…");
    try {
      const data = await api(`activity/meals?${params}`);
      if (current !== revision) return;
      if (page > 1 && !data.meals.length) {
        page = 1;
        return refresh();
      }
      renderMeals(
        results,
        { ...data, showDates: true },
        composer.reuse,
        composer.edit,
        library.favorite,
      );
      $("#meal-search-count").textContent = data.pagination.total
        ? `${data.pagination.total} meals · Page ${page} of ${data.pagination.total_pages}`
        : "No matching meals.";
      $("#meal-search-previous").disabled = page === 1;
      $("#meal-search-next").disabled = !data.pagination.has_next;
    } catch (error) {
      if (current !== revision) return;
      empty(results, "Meals couldn’t load. Search again to retry.");
      $("#meal-search-count").textContent = "";
      showError(error, form.querySelector(".form-error"), form);
    } finally {
      if (current === revision) results.removeAttribute("aria-busy");
    }
  }
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    page = 1;
    filters = new URLSearchParams(new FormData(form));
    refresh();
  });
  $("#meal-search-previous").addEventListener("click", () => {
    page--;
    refresh();
  });
  $("#meal-search-next").addEventListener("click", () => {
    page++;
    refresh();
  });
  return { refresh };
}
